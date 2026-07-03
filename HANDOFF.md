# 세션 인수인계 문서 (2026-07-02, 최종 갱신 2026-07-03)

> 토스증권 Open API 트레이딩 업그레이드 작업 기록. 다음 세션에서 이 문서부터 읽고 이어서 진행.
> 전체 설계/로드맵은 `TRADING_PLAN.md` 참조.

## 완료된 작업

### Phase 1 — 토스 연동 기반 ✅
- deprecated `kis_auth.py`, `kis_client.py` 삭제
- `backend/app/core/toss_auth.py` — OAuth2 토큰 발급/캐싱/만료 60초 전 자동갱신
- `backend/app/services/toss_client.py` — REST 래퍼 (그룹별 토큰버킷 rate limiter, 429 Retry-After 백오프, 401 시 토큰 재발급 1회 재시도, 에러 envelope → TossApiError)
- `backend/app/models/portfolio.py` — Account/HoldingItem/PortfolioSummary
- `backend/app/api/routes/account.py` — GET /api/account, /api/account/holdings
- `main.py`: `TRADING_ENABLED=true`일 때만 트레이딩 라우터 등록 (공개 배포 보호)
- 프론트: `pages/Portfolio.tsx` + "내 계좌" 네비 (30초 자동갱신)

### Phase 2 — 수동 주문 ✅
- `toss_client.py`에 주문 메서드 추가 (create/modify/cancel/open목록/상세/buying-power/sellable-quantity/commissions)
- `models/trading.py` — OrderCreateIn(KRX 6자리 검증, LIMIT price 필수), OrderModifyIn, OrderOut
- `services/order_service.py` — 주문 실행 + Supabase `orders_log` 기록(실패해도 주문 흐름 유지), clientOrderId 멱등성 키 자동생성
- `api/routes/orders.py` — POST/GET /api/orders, /{id}/modify, /{id}/cancel, /log, /buying-power, /sellable-quantity
- 프론트: `components/OrderPanel.tsx`(지정가/시장가, 2단계 확인, 1억↑ confirmHighValueOrder 자동), `StockModal`에 매수/매도 버튼, `pages/Orders.tsx`(대기중 주문 취소 + 이력), `hooks/useTradingAccount.ts`
- `supabase_schema.sql`에 orders_log DDL 추가됨 (**아직 Supabase에서 실행 안 됨** — 아래 참조)
- 검증: TRADING_ENABLED on/off 라우트 등록, tsc 통과 (기존 recharts 타입 에러도 수정함)

### Phase 3 — 자동매매 봇 ✅ (2026-07-03)
- `services/trading/strategy.py` — Strategy 추상 인터페이스
- `services/trading/strategies/theme_momentum.py` — 테마 모멘텀 전략: 테마 평균 등락률 ≥ 임계(기본 +2%) & 상승비율 ≥ 60% → 테마 내 등락률 1위 종목 BUY, 종목당 60분 쿨다운
- `services/trading/engine.py` — BotEngine: APScheduler 주기 실행(기본 5분, 시작 즉시 1회), 장운영시간 체크(토스 market-calendar `today.integrated.regularMarket` 창 1일 캐시, 실패 시 평일 09:00~15:30 휴리스틱), 일일 시그널 한도, 시그널 메모리 200개 + Supabase `trade_signals` 기록(fail-soft), `bot_runs` 시작/중지 이력
- **안전 게이트**: dry-run 기본. 실주문 전환은 `BOT_LIVE_TRADING=true` env + 런타임 토글 **둘 다** 필요 (env 없이 전환 시도 → 403 확인). live 주문은 지정가만, 종목당 예산 `BOT_ORDER_BUDGET`(기본 10만원)
- `api/routes/trading.py` — GET/POST /api/trading/{status,start,stop,mode,signals}
- `order_service.create_order`에 source 파라미터 추가 (봇 주문은 orders_log에 source='bot')
- 프론트: `pages/Bot.tsx`(상태 카드, 시작/중지, dry-run 토글, 시그널 테이블) + "봇" 네비
- 검증: 스모크 전체 통과(시작→즉시 실행→"장 운영시간 아님 — 스킵", mode 403, 중지 200), tsc·vitest 13개 통과

### Phase 4 — 안전장치 ✅ (2026-07-03)
- `services/trading/risk.py` — RiskManager: 건당 상한(기본 20만원)·일일 주문액 상한(50만원)·일 손실 한도(5만원, live 전용 계좌 손익 기반)·연속 실패 3회 자동 kill switch. **dry-run에서도 체크해 시그널에 `blocked` 사유 기록** (실전 전 한도 검증용)
- kill switch: 활성화 시 모든 봇 주문 차단(시그널 기록은 계속), 해제는 수동. `POST /api/trading/kill {activate, reason}`
- `GET /api/trading/report` — 오늘 시그널/차단/실행/실패/주문누적액 요약. 봇 실행 중이면 15:35 KST에 REPORT가 bot_runs에 자동 기록 (detail 칼럼, JSON)
- 엔진 통합: run_once에서 live 손실 한도 체크, _handle_signal에서 주문 전 리스크 체크, 주문 성공/실패를 리스크에 반영
- Bot 페이지: 리스크 현황 라인(주문액/한도·차단·연속실패), 🛑 긴급 주문차단/해제 버튼, 시그널 테이블 차단 사유 표시
- 검증: 한도 초과 시나리오 7종 통과(건당/일일/연속실패/kill 차단/해제/손실한도/엔진통합), kill·report API 스모크 통과, tsc·vitest 13개 통과

### 2026-07-03 추가 수정
- **toss_client rate limiter 치명 버그 수정**: 토큰버킷 상한이 `min(rate, ...)`여서 rate<1인 ACCOUNT(0.8)는 토큰이 영원히 1이 안 됨 → `/api/account` 무한 대기. 상한을 `max(rate, 1)`로 교정. (이전 세션들의 "샌드박스라 검증 불가" 결론 중 일부는 사실 이 버그였음)
- **실계좌 읽기 전용 검증 완료**: 계좌 1개(seq=1, BROKERAGE), 보유 7종목, 매수가능금액 정상 응답 — 0.3초. 주문 실행은 미실시(사용자 몫)
- main 브랜치 데모 성능 개선(테마 상세 캐시·SWR·지수 야후 폴백) 배포 완료 + wip에 머지됨. 상세: 클릭당 4~10초 → 캐시 0.1초대

## 사용자 환경 (중요)

- **로컬 Python = 3.9** (backend/venv). `str | None` 등 3.10 문법이 FastAPI/Pydantic 런타임 평가에서 터짐 → 라우트/모델은 `Optional[]` 사용할 것 (이미 수정 완료)
- `.env`는 프로젝트 루트 (backend 아님). TOSS_CLIENT_ID/SECRET 사용자가 입력 완료, TRADING_ENABLED=true
- `.env`는 git 미추적 (안전 확인됨)
- 클로드 샌드박스: 기본 Bash는 외부망 차단이지만 **샌드박스 해제 포그라운드 명령으로는 실연동 검증 가능** (백그라운드 실행은 해제 플래그와 무관하게 차단됨 주의). uvicorn을 `(uvicorn ... &)` 형태로 포그라운드 명령 안에서 띄우면 실네트워크 동작
- 토스 API: 응답 `{"result": ...}` envelope, 계좌/주문엔 `X-Tossinvest-Account` 헤더, 종료주문 목록 API 미지원(OPEN만), 문서 developers.tossinvest.com/llms.txt

## ⚠️ 미해결 이슈 (다음 세션 첫 작업)

1. ~~**포트 8000 점유**~~ ✅ **해결 (2026-07-03)** — 점유 주체는 이 앱의 옛 프로세스가 아니라 **04-meditation-uni 프로젝트의 uvicorn**이었음 (그래서 kill해도 의미가 없었고, health에 `trading` 키도 없었던 것). 사용자 선택에 따라 이 앱 백엔드를 **포트 8001로 이전**: `start_app.command`, vite proxy, 프론트 API/WS 기본값, README/SPEC 일괄 수정. 8001에서 새 코드 기동 → `/api/health` = `{"status":"ok","trading":true}` 확인 완료. meditation-uni는 8000 그대로 두 프로젝트 동시 운영 가능.
2. **Supabase 프로젝트 일시정지 (여전히)** — 2026-07-03 기준 DNS도 안 풀림(정지 상태). MCP 연결 계정에는 이 프로젝트(jopyeznvqildrumpwqti)가 없어 원격 복구 불가 → **사용자가 대시보드에서 Resume** 후 SQL Editor에서 `backend/supabase_schema.sql` 실행 (orders_log + trade_signals + bot_runs 추가분 포함). Supabase 없어도 잔고/주문/봇 동작, 이력·시그널 영속 저장만 안 됨
3. ~~**실계좌 연동 미검증**~~ ✅ **읽기 전용 검증 완료 (2026-07-03)** — 남은 것: 소액 1주 지정가 매수 → 주문 탭에서 취소 실거래 테스트 (⚠️ 실주문 실행은 사용자가 직접)

## 실행 방법

`start_app.command` 더블클릭 (백엔드 **8001** + 프론트 5173 + 브라우저 자동 오픈), 종료는 터미널에서 Ctrl+C.
백엔드 8001 기동·health 확인 완료(2026-07-03), 프론트 tsc 통과. 남은 검증은 실계좌 연동(이슈 3)뿐.

## 다음 단계 (로드맵)

- **dry-run 운영**: 최소 1주일 시그널 품질 관찰 (⚠️ Supabase 복구 전엔 시그널이 메모리에만 남아 백엔드 재시작 시 소실 — Resume이 최우선)
- SELL 시그널 로직 (현재 전략은 BUY만) — 보유종목 테마 하락 반전 시 매도 등
- dry-run 검증 후 `BOT_LIVE_TRADING=true` 전환 검토 (한도 설정은 blocked 기록으로 사전 검증)
- 수동 주문 실거래 테스트 (소액 1주 매수→취소)는 여전히 사용자 직접 몫
