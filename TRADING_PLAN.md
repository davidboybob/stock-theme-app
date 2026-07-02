# 토스증권 Open API 트레이딩 업그레이드 계획

> 작성일: 2026-07-02 · 대상: stock-theme-app (기존 테마 대시보드 → 트레이딩 통합 앱)

## 1. 방향

기존 앱을 확장한다 (신규 프로젝트 X). 이유:

- FastAPI + React 19 + TS + Supabase + APScheduler + WebSocket 알림 인프라를 그대로 재사용
- 테마 강도/알림 로직이 자동매매 시그널의 입력으로 바로 연결 가능
- deprecated된 `kis_client.py` / `kis_auth.py`는 삭제하고 토스 클라이언트로 대체

**단, 보안 원칙**: 주문 기능이 켜진 백엔드는 공개 배포(Render) 금지. 트레이딩 기능은 `TRADING_ENABLED` 환경변수로 게이트하고, 로컬/개인 서버에서만 활성화. 기존 공개 배포본은 시세 대시보드 전용 유지.

## 2. 토스증권 Open API 요약

- Base: `https://openapi.tossinvest.com` · 문서: developers.tossinvest.com
- 인증: OAuth 2.0 Client Credentials → `POST /oauth2/token`, `Authorization: Bearer`
- 계좌/주문 API는 `X-Tossinvest-Account: {accountSeq}` 헤더 추가 필요
- REST만 제공 (웹소켓 실시간 시세 없음) → 실시간성은 폴링으로
- Rate limit (초당, 클라이언트×그룹): AUTH 5 / ACCOUNT 1 / ASSET 5 / MARKET_DATA 10 / 캔들 5 / ORDER 6 (09:00~09:10엔 3) / ORDER_HISTORY 5
- 1억원 이상 주문은 `confirmHighValueOrder: true` 필요
- 주요 엔드포인트: `/api/v1/prices` `/orderbook` `/candles` `/accounts` `/holdings` `/orders`(생성·정정·취소) `/buying-power` `/sellable-quantity` `/commissions` `/market-calendar/KR`

## 3. 아키텍처

```
backend/app/
├── core/
│   ├── config.py            # + TOSS_CLIENT_ID/SECRET, TRADING_ENABLED, 리스크 한도
│   └── toss_auth.py         # 토큰 발급·캐싱·만료 자동갱신 (기존 kis_auth 대체)
├── services/
│   ├── toss_client.py       # REST 래퍼: 그룹별 rate limiter + 429 지수백오프(tenacity)
│   ├── naver_client.py      # 유지 — 시세/검색/지수는 네이버 계속 사용 (rate limit 절약)
│   ├── portfolio_service.py # 잔고·손익 집계
│   ├── order_service.py     # 주문 생성/정정/취소 + Supabase 주문 로그
│   └── trading/
│       ├── engine.py        # 봇 루프 (APScheduler, 장운영시간 체크)
│       ├── strategy.py      # Strategy 인터페이스 (signal → BUY/SELL/HOLD)
│       ├── strategies/      # 예: 테마모멘텀, 이동평균 크로스
│       └── risk.py          # 일 손실 한도, 종목당 최대 금액, kill switch
├── api/routes/
│   ├── account.py           # GET /api/account, /api/account/holdings
│   ├── orders.py            # POST/GET /api/orders, 정정/취소
│   └── trading.py           # 봇 시작/중지, 상태, dry-run 토글, 거래 로그
frontend/src/pages/
├── Portfolio.tsx            # 잔고·평가손익·보유종목
├── Trade.tsx                # 주문 폼(지정가/시장가) + 대기/체결 내역
└── Bot.tsx                  # 전략 on/off, dry-run 스위치, 실행 로그
```

데이터 소스 분담: **시세·검색·지수 = 네이버(현행 유지)**, **계좌·주문·캔들·장운영시간 = 토스**. 토스 rate limit을 주문에 아껴 쓰는 구조.

Supabase 신규 테이블: `orders_log`(모든 주문 기록), `bot_runs`(봇 실행 이력), `trade_signals`(시그널 기록 — dry-run 검증용).

## 4. 단계별 로드맵

### Phase 1 — 토스 연동 기반 (1~2일)
- kis_* 삭제, `toss_auth.py` + `toss_client.py` 작성 (토큰 캐싱, rate limiter, 에러 envelope 파싱)
- `.env`에 키 추가, `/api/account` `/api/holdings` 연동
- Portfolio 페이지: 잔고/보유종목/손익 표시
- ✅ 검증: 실계좌 잔고가 화면에 정확히 뜨는지

### Phase 2 — 수동 주문 (2~3일)
- order_service + `/api/orders` 라우트 (생성·정정·취소·내역)
- 매수가능금액/판매가능수량/수수료 조회 연동
- Trade 페이지: 종목 검색 → 호가 확인 → 주문 폼 → 확인 모달(2단계 확인)
- 모든 주문 Supabase 로그
- ✅ 검증: 소액 1주 지정가 매수→취소 실거래 테스트

### Phase 3 — 자동매매 엔진 (3~5일)
- Strategy 인터페이스 + 첫 전략: 기존 테마 강도 활용 "테마 모멘텀" (테마 등락률 임계 돌파 시 대표 종목 매수)
- **dry-run 모드 기본값** — 주문 대신 trade_signals 기록만
- 장운영시간(market-calendar) 체크, 기존 WebSocket 알림으로 체결/시그널 푸시
- Bot 페이지: 전략 설정, dry-run/실전 토글, 로그 뷰
- ✅ 검증: 최소 1주일 dry-run 시그널 품질 확인 후 실전 전환

### Phase 4 — 안전장치·운영 (2일)
- risk.py: 일 최대 손실 한도, 종목당/일일 최대 주문 금액, 연속 실패 시 자동 정지, kill switch API
- 429/토큰만료/점검(maintenance) 대응 회복 로직
- 주문 실패 알림, 일일 거래 리포트
- ✅ 검증: 한도 초과 시나리오 테스트

## 5. 리스크 & 주의사항

- **키 보안**: client_secret은 `.env`만, 프론트 절대 노출 금지, `.gitignore` 확인 (현재 `.env`가 git 추적 중인지 확인 필요)
- **REST only**: 실시간 체결 스트림이 없어 초단타 전략 부적합 → 분 단위 이상 전략 권장
- **rate limit**: ORDER 6 TPS·장 초반 3 TPS → 봇 주문 큐에 스로틀 필수
- **시장가 주문 주의**: 급등락 시 슬리피지 — 봇은 지정가 기본
- 반대 방향 대기 주문 존재 시 주문 거부(`opposite-pending-order-exists`) 등 409/422 케이스 처리 필요
