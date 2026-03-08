# 테마주 분석 웹앱

한국 주식 시장의 테마별 종목 정보를 실시간으로 제공하는 웹 애플리케이션.
**네이버 증권 API** 기반으로 동작하며, API 키 없이 바로 사용 가능하다.

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| 백엔드 | Python 3.9+, FastAPI, uvicorn, httpx, APScheduler |
| 프론트엔드 | React 18, TypeScript, Vite, TanStack Query, Axios, Recharts |
| 데이터 소스 | 네이버 금융 polling API (인증 불필요) |
| 배포 | Docker, Docker Compose, nginx |

---

## 프로젝트 구조

```
stock-theme-app/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 앱 진입점, CORS 설정
│   │   ├── core/
│   │   │   └── config.py            # 환경변수 설정 (pydantic-settings)
│   │   ├── api/routes/
│   │   │   ├── themes.py            # GET /api/themes, /api/themes/{id}
│   │   │   ├── stocks.py            # GET /api/stocks/{code}, /api/indices
│   │   │   └── alerts.py            # CRUD /api/alerts + WS /api/ws/alerts
│   │   ├── services/
│   │   │   ├── naver_client.py      # 네이버 증권 HTTP 클라이언트
│   │   │   ├── theme_service.py     # 테마 강도 계산 로직
│   │   │   └── alert_monitor.py     # APScheduler 기반 알림 모니터링
│   │   ├── models/
│   │   │   ├── theme.py             # Pydantic 모델 (Theme, ThemeStrength, Alert)
│   │   │   └── stock.py             # Pydantic 모델 (StockPrice, IndexPrice)
│   │   └── data/
│   │       └── themes.json          # 테마-종목 매핑 데이터 (8개 테마)
│   ├── venv/                        # Python 가상환경
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx                  # React Router, QueryClient 설정
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx        # 테마 강도 순위
│   │   │   ├── ThemeDetail.tsx      # 테마별 종목 상세
│   │   │   └── Alerts.tsx           # 알림 설정 및 실시간 로그
│   │   ├── components/
│   │   │   ├── IndexBar.tsx         # KOSPI/KOSDAQ 상단 표시
│   │   │   ├── ThemeCard.tsx        # 테마 카드 컴포넌트
│   │   │   └── StockTable.tsx       # 종목 테이블 컴포넌트
│   │   └── api/client.ts            # Axios 기반 API 클라이언트 + 타입 정의
│   ├── Dockerfile
│   ├── nginx.conf
│   └── vite.config.ts               # Vite 설정 (프록시 포함)
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/themes` | 전체 테마 목록 + 강도 순위 (등락률 내림차순) |
| GET | `/api/themes/{id}` | 테마 상세 + 소속 종목 현재가 |
| GET | `/api/stocks/{code}` | 종목 현재가 (6자리 종목코드) |
| GET | `/api/indices` | KOSPI / KOSDAQ 지수 |
| GET | `/api/alerts` | 알림 목록 |
| POST | `/api/alerts` | 알림 생성 |
| DELETE | `/api/alerts/{id}` | 알림 삭제 |
| WS | `/api/ws/alerts` | 실시간 알림 WebSocket |
| GET | `/api/health` | 서버 상태 확인 |

---

## 테마 목록

| ID | 테마명 | 대표 종목 |
|----|--------|----------|
| `ai` | 인공지능(AI) | 삼성전자, SK하이닉스, NAVER 등 |
| `semiconductor` | 반도체 | 삼성전자, SK하이닉스, 한미반도체 등 |
| `bio` | 바이오/제약 | 셀트리온, 삼성바이오로직스 등 |
| `battery` | 2차전지 | LG에너지솔루션, 삼성SDI 등 |
| `defense` | 방산 | 한화에어로스페이스, LIG넥스원 등 |
| `robot` | 로봇 | ROBOTIS, 레인보우로보틱스 등 |
| `game` | 게임 | NC소프트, 카카오게임즈 등 |
| `eco` | 친환경/ESG | 한국전력, OCI 등 |

> 종목 변경: `backend/app/data/themes.json` 파일 직접 수정

---

## 실행 방법

### 로컬 개발

```bash
# 1. 저장소 클론
git clone https://github.com/davidboybob/stock-theme-app.git
cd stock-theme-app

# 2. 백엔드 실행
cd backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/uvicorn app.main:app --reload --port 8000

# 3. 프론트엔드 실행 (별도 터미널)
cd frontend
npm install
npm run dev
```

| 서비스 | URL |
|--------|-----|
| 프론트엔드 | http://localhost:5173 |
| API 문서 (Swagger) | http://localhost:8000/docs |

### Docker Compose

```bash
docker-compose up --build
```

---

## 데이터 소스

**네이버 금융 polling API** (`https://polling.finance.naver.com`)

- 주식 현재가: `/api/realtime/domestic/stock/{종목코드}`
- 지수: `/api/realtime/domestic/index/{KOSPI|KOSDAQ}`
- 인증 없이 접근 가능 (공개 API)
- 장 운영 시간(09:00~15:30) 중 실시간 데이터 제공

---

## 주요 설계 결정

### 테마-종목 매핑을 JSON으로 관리
네이버 증권은 KIS API와 달리 테마 코드 API를 제공하지 않으므로,
`data/themes.json`에 테마와 종목 코드를 직접 정의한다.

### 테마 강도 계산
테마 소속 종목들의 **평균 등락률**을 테마 강도로 정의한다.

```
테마 강도 = mean(각 종목의 등락률)
```

### 알림 저장
별도 DB 없이 `data/alerts.json` 파일에 저장한다.
APScheduler로 1분 간격 모니터링 후 조건 충족 시 WebSocket으로 브라우저에 푸시한다.

---

## 작업 이력

| 날짜 | 내용 |
|------|------|
| 2026-03-09 | 프로젝트 초기 구현 (FastAPI + React, KIS Open API 기반) |
| 2026-03-09 | 데이터 소스 변경: KIS API → 네이버 증권 API (API 키 제거) |
| 2026-03-09 | GitHub 저장소 연동 및 배포 |

---

## 환경변수

`.env.example` 참고. 현재 네이버 증권 API는 인증이 필요 없어 별도 설정 없이 바로 실행 가능하다.

```env
# 필요 시 타임아웃 조정 (기본값: 10초)
REQUEST_TIMEOUT=10.0
```
