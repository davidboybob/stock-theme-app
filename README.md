# 테마주 분석 웹앱 (Stock Theme App)

한국 주식 시장의 테마별 종목 정보를 실시간으로 제공하는 웹 애플리케이션.
**네이버 증권 API** 기반으로 동작하며, API 키 없이 바로 사용 가능하다.

---

## 배포 URL

| 서비스 | URL |
|--------|-----|
| **프론트엔드** (Vercel) | https://stock-theme-app.vercel.app |
| **백엔드** (Render) | https://stock-theme-app.onrender.com |
| **API 문서** (Swagger) | https://stock-theme-app.onrender.com/docs |

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| 백엔드 | Python 3.11, FastAPI, uvicorn, httpx, APScheduler, tenacity |
| 프론트엔드 | React 19, TypeScript, Vite, TanStack Query, Axios, Recharts |
| 데이터베이스 | Supabase (PostgreSQL) |
| 데이터 소스 | 네이버 금융 polling API (인증 불필요) |
| 배포 | Render (백엔드), Vercel (프론트엔드) |
| CI/CD | GitHub Actions |

---

## 구현 기능

### 핵심 기능
- **테마 강도 순위**: 8개 테마의 평균 등락률을 실시간으로 비교 (30초 자동 갱신)
- **테마 상세**: 테마 소속 종목별 현재가, 등락률, 거래량 테이블
- **시장 지수**: KOSPI / KOSDAQ 상단 실시간 표시
- **알림 설정**: 테마/종목 등락률 임계값 도달 시 WebSocket 실시간 알림

### 시각화
- Dashboard 수평 막대 차트 (Recharts, 카드/차트 탭 전환)
- ThemeDetail 종목 등락률 바 차트 + 당일 가격 범위 표시
- 테마 강도 히스토리 라인 차트 (10분 주기 수집)

### 부가 기능
- 종목 검색 (네이버 자동완성 API, 디바운스 300ms)
- 종목 상세 모달 (52주 최고/최저, PER, PBR, 시가총액)
- 테마 즐겨찾기 (localStorage)
- 알림 활성/비활성 토글 + 알림 발생 이력
- 스켈레톤 로딩 UI, React ErrorBoundary, Toast 알림
- 모바일 반응형 (1열/2열/4열 그리드)
- 다크모드 (CSS 변수 시스템, prefers-color-scheme 감지)

---

## 프로젝트 구조

```
stock-theme-app/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 앱 진입점, CORS 설정
│   │   ├── db.py                    # Supabase 클라이언트 싱글턴
│   │   ├── api/routes/
│   │   │   ├── themes.py            # GET /api/themes, /api/themes/{id}, /history
│   │   │   ├── stocks.py            # GET /api/stocks/{code}, /search, /detail, /indices
│   │   │   └── alerts.py            # CRUD /api/alerts + WS /api/ws/alerts
│   │   ├── services/
│   │   │   ├── naver_client.py      # 네이버 증권 HTTP 클라이언트 (tenacity 재시도)
│   │   │   ├── theme_service.py     # 테마 강도 계산 로직
│   │   │   └── alert_monitor.py     # APScheduler 알림 모니터링 + 히스토리 스냅샷
│   │   ├── models/
│   │   │   ├── theme.py             # Pydantic 모델 (Theme, ThemeStrength, Alert 등)
│   │   │   └── stock.py             # Pydantic 모델 (StockPrice, StockDetail, IndexPrice)
│   │   └── data/
│   │       └── themes.json          # 테마-종목 매핑 (8개 테마, 테마당 10종목)
│   ├── supabase_schema.sql          # Supabase 테이블 DDL
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx                  # React Router, QueryClient, ErrorBoundary
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx        # 테마 강도 순위 (카드/차트 탭, 즐겨찾기 필터)
│   │   │   ├── ThemeDetail.tsx      # 테마 상세 + 차트 + 히스토리
│   │   │   └── Alerts.tsx           # 알림 설정, 토글, 이력, WebSocket 로그
│   │   ├── components/
│   │   │   ├── IndexBar.tsx         # KOSPI/KOSDAQ + 다크모드 토글
│   │   │   ├── ThemeCard.tsx        # 테마 카드 (즐겨찾기 버튼 포함)
│   │   │   ├── StockTable.tsx       # 종목 테이블 (클릭 시 모달)
│   │   │   ├── SearchBar.tsx        # 종목 검색 (자동완성 드롭다운)
│   │   │   ├── StockModal.tsx       # 종목 상세 모달
│   │   │   ├── SkeletonCard.tsx     # 로딩 스켈레톤
│   │   │   ├── ErrorBoundary.tsx    # React 에러 바운더리
│   │   │   └── Toast.tsx            # 토스트 알림
│   │   ├── hooks/
│   │   │   ├── useFavorites.ts      # 즐겨찾기 (localStorage)
│   │   │   ├── useTheme.ts          # 다크모드
│   │   │   └── useToast.ts          # 토스트 상태 관리
│   │   └── api/client.ts            # Axios API 클라이언트 + TypeScript 타입
│   ├── vercel.json                  # Vercel 배포 설정 (SPA 라우팅)
│   ├── Dockerfile
│   └── nginx.conf                   # API 프록시 + SPA 라우팅
├── scripts/
│   └── validate_codes.py            # 종목코드 유효성 검증 스크립트
├── render.yaml                      # Render 배포 설정
├── docker-compose.yml               # 로컬 Docker 배포
├── .github/workflows/ci.yml         # GitHub Actions CI/CD
├── .env.example
└── SPEC.md                          # 기능 명세서 + 고도화 계획
```

---

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/themes` | 전체 테마 강도 목록 (등락률 내림차순) |
| GET | `/api/themes/{id}` | 테마 상세 + 소속 종목 현재가 |
| GET | `/api/themes/{id}/history` | 테마 강도 히스토리 (`?period=1d`) |
| GET | `/api/stocks/{code}` | 종목 현재가 |
| GET | `/api/stocks/{code}/detail` | 종목 상세 (52주, PER, PBR, 시가총액) |
| GET | `/api/stocks/search` | 종목 검색 (`?q=검색어`) |
| GET | `/api/indices` | KOSPI / KOSDAQ 지수 |
| GET | `/api/alerts` | 알림 목록 |
| POST | `/api/alerts` | 알림 생성 |
| PATCH | `/api/alerts/{id}` | 알림 활성/비활성 토글 |
| DELETE | `/api/alerts/{id}` | 알림 삭제 |
| GET | `/api/alerts/history` | 알림 발생 이력 |
| WS | `/api/ws/alerts` | 실시간 알림 WebSocket |
| GET | `/api/health` | 서버 상태 확인 |

---

## 테마 목록

| ID | 테마명 | 종목 수 |
|----|--------|---------|
| `ai` | 인공지능(AI) | 10 |
| `semiconductor` | 반도체 | 10 |
| `bio` | 바이오/제약 | 10 |
| `battery` | 2차전지 | 10 |
| `defense` | 방산 | 10 |
| `robot` | 로봇 | 10 |
| `game` | 게임 | 10 |
| `eco` | 친환경/ESG | 10 |

> 종목 변경: `backend/app/data/themes.json` 직접 수정

---

## 로컬 개발

### 환경변수 설정

```bash
cp .env.example .env
# .env 파일에 Supabase 정보 입력
```

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
ALLOWED_ORIGINS=http://localhost:5173
```

### 백엔드 실행

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev
```

| 서비스 | URL |
|--------|-----|
| 프론트엔드 | http://localhost:5173 |
| API 문서 (Swagger) | http://localhost:8000/docs |

### Docker Compose (로컬)

```bash
docker compose up --build
```

---

## 데이터베이스 (Supabase)

### 테이블 구조
- `alerts`: 알림 설정 저장
- `alert_history`: 알림 발생 이력
- `theme_history`: 테마 강도 스냅샷 (10분 주기)

### 초기 테이블 생성
Supabase 대시보드 SQL Editor에서 `backend/supabase_schema.sql` 실행

---

## 배포 구조

```
GitHub
  ├── push → GitHub Actions CI (backend lint/test, frontend build)
  ├── Render → 백엔드 자동 배포 (main 브랜치)
  └── Vercel → 프론트엔드 자동 배포 (main 브랜치)
```

### Render 환경변수
| Key | 설명 |
|-----|------|
| `SUPABASE_URL` | Supabase 프로젝트 URL |
| `SUPABASE_KEY` | Supabase anon key |
| `ALLOWED_ORIGINS` | CORS 허용 도메인 (Vercel URL) |

---

## 데이터 소스

**네이버 금융 polling API** (`https://polling.finance.naver.com`)
- 주식 현재가: `/api/realtime/domestic/stock/{종목코드}`
- 지수: `/api/realtime/domestic/index/{KOSPI|KOSDAQ}`
- 인증 없이 접근 가능 (공개 API)
- 장 운영 시간(09:00~15:30) 중 실시간 데이터

---

## 작업 이력

| 날짜 | 내용 |
|------|------|
| 2026-03-09 | 프로젝트 초기 구현 (FastAPI + React, 네이버 증권 API) |
| 2026-03-09 | GitHub 저장소 연동 |
| 2026-03-10 | 전체 고도화 (Phase 1~5) |
| 2026-03-10 | SQLite → Supabase 마이그레이션 |
| 2026-03-10 | Render + Vercel 클라우드 배포 완료 |
