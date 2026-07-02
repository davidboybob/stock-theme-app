# 세션 인수인계 문서 (2026-07-02)

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

## 사용자 환경 (중요)

- **로컬 Python = 3.9** (backend/venv). `str | None` 등 3.10 문법이 FastAPI/Pydantic 런타임 평가에서 터짐 → 라우트/모델은 `Optional[]` 사용할 것 (이미 수정 완료)
- `.env`는 프로젝트 루트 (backend 아님). TOSS_CLIENT_ID/SECRET 사용자가 입력 완료, TRADING_ENABLED=true
- `.env`는 git 미추적 (안전 확인됨)
- 클로드 샌드박스에서 외부 API(토스/네이버/Supabase) 직접 호출 불가 — 실연동 검증은 사용자 로컬에서만 가능
- 토스 API: 응답 `{"result": ...}` envelope, 계좌/주문엔 `X-Tossinvest-Account` 헤더, 종료주문 목록 API 미지원(OPEN만), 문서 developers.tossinvest.com/llms.txt

## ⚠️ 미해결 이슈 (다음 세션 첫 작업)

1. **포트 8000을 오래된 uvicorn 프로세스가 점유 중** — 예전(수개월 전)에 띄운 uvicorn이 옛 코드로 응답하고 있어서 새 백엔드가 `Errno 48 address already in use`로 못 뜸. `start_app.command`에 `lsof -ti:8000 | xargs kill -9`를 넣었지만 이 프로세스가 안 죽었음 (권한/세션 문제 추정).
   - 해결: 터미널에서 `sudo lsof -ti:8000 | xargs sudo kill -9` 또는 Mac 재부팅 후 start_app.command 재실행
   - 판별법: `curl localhost:8000/api/health` 응답에 `"trading"` 키가 있으면 새 코드, 없으면 옛 프로세스
2. **Supabase 프로젝트 일시정지 + Supabase 자체 장애** — 무료 플랜 auto-pause 상태인데 장애("No backups found")로 Resume 버튼이 안 뜸. 복구 후: 대시보드에서 Resume → SQL Editor에서 `backend/supabase_schema.sql`의 orders_log 부분 실행. (Supabase 없어도 잔고/주문은 동작, 주문 이력만 안 남음)
3. **실계좌 연동 미검증** — 백엔드가 정상으로 뜨면 http://localhost:5173/portfolio 에서 잔고 확인 → 소액 1주 지정가 매수 → 주문 탭에서 취소 테스트 (⚠️ 실주문 실행은 사용자가 직접)

## 실행 방법

`start_app.command` 더블클릭 (백엔드 8000 + 프론트 5173 + 브라우저 자동 오픈), 종료는 터미널에서 Ctrl+C.
프론트는 정상 동작 확인됨 (Vite 5173). 백엔드만 위 이슈 1 해결 필요.

## 다음 단계 (로드맵)

- **Phase 3 — 자동매매 봇**: Strategy 인터페이스 + 테마 모멘텀 전략(기존 테마 강도 활용), dry-run 기본값(trade_signals 기록만), 장운영시간 체크(market-calendar/KR), Bot 페이지(전략 on/off, dry-run 토글). 최소 1주일 dry-run 후 실전 전환.
- **Phase 4 — 안전장치**: 일 손실 한도, 종목당/일일 주문 금액 상한, 연속 실패 자동 정지, kill switch, 일일 리포트.
