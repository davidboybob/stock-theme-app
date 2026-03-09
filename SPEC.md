# Stock Theme App — 기능 명세서 & 고도화 계획

> 작성일: 2026-03-09

---

## 1. 시스템 아키텍처 개요

```
[네이버 증권 Polling API]
         ↓ HTTP (인증 불필요)
[Backend: FastAPI + uvicorn :8000]
  ├── themes router     → 테마 강도 계산
  ├── stocks router     → 종목/지수 조회
  ├── alerts router     → 알림 CRUD
  ├── APScheduler       → 1분 주기 알림 체크
  └── WebSocket         → 알림 실시간 푸시
         ↓ REST API / WebSocket
[Frontend: React 19 + TypeScript + Vite :5173]
  ├── Dashboard        → 테마 순위
  ├── ThemeDetail      → 테마 상세
  └── Alerts           → 알림 관리
```

---

## 2. 데이터 모델

### 2.1 테마 (Theme)

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 테마 식별자 (ai, semiconductor, bio, battery, defense, robot, game, eco) |
| `name` | string | 테마명 |
| `description` | string? | 테마 설명 |
| `stocks` | string[] | 종목코드 목록 (현재 테마당 5개) |

### 2.2 테마 강도 (ThemeStrength)

| 필드 | 타입 | 설명 |
|------|------|------|
| `theme_id` | string | 테마 ID |
| `theme_name` | string | 테마명 |
| `avg_change_rate` | float | 테마 내 종목 평균 등락률 (%) |
| `rising_count` | int | 상승 종목 수 |
| `falling_count` | int | 하락 종목 수 |
| `total` | int | 전체 종목 수 |

### 2.3 종목 현재가 (StockPrice)

| 필드 | 타입 | 설명 |
|------|------|------|
| `code` | string | 종목코드 (6자리) |
| `name` | string | 종목명 |
| `current_price` | int | 현재가 (원) |
| `change_price` | int | 전일 대비 등락액 |
| `change_rate` | float | 등락률 (%) |
| `volume` | int | 거래량 |
| `high_price` | int | 당일 고가 |
| `low_price` | int | 당일 저가 |
| `open_price` | int | 시가 |

### 2.4 시장 지수 (IndexPrice)

| 필드 | 타입 | 설명 |
|------|------|------|
| `code` | string | KOSPI / KOSDAQ |
| `name` | string | 지수명 |
| `current_value` | float | 현재 지수값 |
| `change_value` | float | 전일 대비 변동값 |
| `change_rate` | float | 변동률 (%) |

### 2.5 알림 (Alert)

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | UUID |
| `target_type` | "theme" \| "stock" | 알림 대상 유형 |
| `target_id` | string | 테마 ID 또는 종목코드 |
| `target_name` | string | 표시용 이름 |
| `condition` | "above" \| "below" | 조건 방향 |
| `threshold` | float | 임계값 (%) |
| `is_active` | bool | 활성 여부 |
| `created_at` | string | 생성 시각 (ISO 8601) |

---

## 3. 백엔드 API 명세

### 3.1 테마 API

| 메서드 | 경로 | 설명 | 응답 |
|--------|------|------|------|
| GET | `/api/themes` | 전체 테마 강도 목록 (등락률 내림차순 정렬) | `ThemeStrength[]` |
| GET | `/api/themes/{theme_id}` | 특정 테마 상세 (종목별 현재가 포함) | `ThemeDetail` |

**동작 방식:**
- 8개 테마 JSON 파싱 → 각 테마 종목코드로 네이버 API 병렬 호출 (semaphore 10)
- 유효한 응답만 평균 계산 (API 실패 종목 제외)
- 등락률 기준 내림차순 정렬

### 3.2 종목/지수 API

| 메서드 | 경로 | 설명 | 응답 |
|--------|------|------|------|
| GET | `/api/stocks/{code}` | 개별 종목 현재가 조회 | `StockPrice` |
| GET | `/api/indices` | KOSPI, KOSDAQ 지수 조회 | `IndexPrice[]` |

### 3.3 알림 API

| 메서드 | 경로 | 설명 | 응답 |
|--------|------|------|------|
| GET | `/api/alerts` | 전체 알림 목록 | `Alert[]` |
| POST | `/api/alerts` | 알림 생성 | `Alert` |
| DELETE | `/api/alerts/{alert_id}` | 알림 삭제 | 204 |
| WS | `/api/ws/alerts` | 실시간 알림 수신 | `AlertTriggered` 스트림 |

**알림 체크 로직:**
- APScheduler가 1분마다 `_check_alerts()` 실행
- `target_type == "theme"` → `avg_change_rate` 와 threshold 비교
- `target_type == "stock"` → `change_rate` 와 threshold 비교
- 조건 충족 시 연결된 모든 WebSocket 클라이언트에 브로드캐스트
- **알림 저장:** `backend/app/data/alerts.json` (JSON 파일, 동기 I/O)

---

## 4. 프론트엔드 기능 명세

### 4.1 공통 레이아웃 — IndexBar

- **위치:** 최상단 고정 헤더
- **표시 정보:** KOSPI, KOSDAQ 지수값 / 등락값 / 등락률
- **색상:** 상승 빨간색, 하락 파란색 (한국 증시 관례)
- **갱신 주기:** 30초 자동 refetch (React Query)
- **네비게이션:** Dashboard / 알림 설정 링크

### 4.2 Dashboard (테마 강도 순위)

- **URL:** `/`
- **기능:**
  - 전체 8개 테마를 `avg_change_rate` 내림차순으로 카드 표시
  - ThemeCard 클릭 시 ThemeDetail로 이동
  - 30초 자동 새로고침 + 수동 새로고침 버튼
- **ThemeCard 표시 정보:**
  - 순위 (1위~8위)
  - 테마명
  - 평균 등락률 (%, 색상 코딩)
  - 상승/하락 종목 수
- **상태 처리:** 로딩 텍스트, 에러 메시지

### 4.3 ThemeDetail (테마 상세)

- **URL:** `/theme/:id`
- **기능:**
  - 뒤로가기 버튼 (`navigate(-1)`)
  - 테마 강도 요약 (평균 등락률, 상승/하락/보합 종목 수)
  - 종목 테이블 (등락률 내림차순 정렬)
  - 30초 자동 새로고침
- **StockTable 컬럼:**
  - 종목코드 / 종목명 / 현재가 / 등락액 / 등락률 / 거래량
  - 행 색상: 등락률 양수→빨간색, 음수→파란색

### 4.4 Alerts (알림 설정)

- **URL:** `/alerts`
- **알림 생성 폼:**
  - 대상 유형 선택: 테마(드롭다운 8개) / 종목(6자리 코드 직접 입력)
  - 조건 선택: 이상(above) / 이하(below)
  - 임계값 입력: 소수점 0.1 단위 (%)
- **등록된 알림 목록:**
  - 대상명 / 조건 표시 (≥ / ≤ threshold%)
  - 삭제 버튼
- **실시간 알림 로그 (WebSocket):**
  - 페이지 마운트 시 WS 연결, 언마운트 시 자동 해제
  - 수신 메시지 형식: `[HH:MM:SS] 테마명: X.XX% (임계값 초과/미만 Y%)`
  - 최근 20건 유지

---

## 5. 기술 스택

| 구분 | 기술 | 버전 |
|------|------|------|
| Backend 프레임워크 | FastAPI + uvicorn | 0.110+ |
| HTTP 클라이언트 | httpx (async) | 0.27+ |
| 스케줄러 | APScheduler | 3.10+ |
| 데이터 검증 | Pydantic v2 | - |
| Frontend 프레임워크 | React | 19.2 |
| 라우팅 | React Router | 7.13 |
| 서버 상태 관리 | TanStack Query | 5.90 |
| HTTP 클라이언트 | Axios | 1.13 |
| 번들러 | Vite | 7.3 |
| 외부 데이터 | 네이버 증권 Polling API | - |

---

## 6. 고도화 계획

### 현재 상태 진단 (As-Is)

| 영역 | 현황 | 문제점 |
|------|------|--------|
| 데이터 | 테마당 5종목, JSON 하드코딩 | 대표성 부족, 검증 안 됨 |
| 시각화 | 텍스트 + 테이블만 | 직관성 부족 |
| 안정성 | API 실패 시 재시도 없음, JSON 파일 저장 | 동시성 취약, 데이터 손실 가능 |
| 종목 정보 | 현재가/등락률만 | 투자 판단 정보 부족 |
| 배포 | 로컬 실행만 | 실사용 불가 |

---

### Phase 1 — 데이터 & 안정성 기반 강화 (최우선)

#### 1-1. 종목코드 검증 + 테마 데이터 확대

```
- scripts/validate_codes.py: themes.json 전체 종목코드 API 검증 스크립트
- themes.json: 테마당 종목 5개 → 10~15개로 확대
- 각 종목에 name 필드 추가 (API 의존 제거)
```

#### 1-2. 네이버 API 재시도 로직

```
- tenacity 라이브러리 추가
- naver_client.py: @retry 데코레이터 적용
  └── 최대 3회 재시도, 지수 백오프 (1초 → 2초 → 4초)
  └── httpx.HTTPError, asyncio.TimeoutError 시 재시도
```

#### 1-3. 알림 저장소 SQLite 마이그레이션

```
- aiosqlite 추가
- backend/app/db.py 신규 작성
  └── alerts 테이블
  └── alert_history 테이블 (알림 이력)
- alert_monitor.py: JSON I/O → aiosqlite async I/O 전환
```

---

### Phase 2 — 시각화 강화

#### 2-1. Dashboard 차트

```
- Recharts 라이브러리 추가
- 테마 강도 수평 막대 차트 (등락률 기준, 색상 그라데이션)
- ThemeCard 그리드와 차트 탭 전환 UI
```

#### 2-2. ThemeDetail 차트

```
- 종목별 등락률 수평 바 차트
- 시가 대비 현재가 진행률 표시
```

#### 2-3. 히스토리 데이터 + 라인 차트

```
- backend: 10분마다 테마 강도 스냅샷 DB 저장 (APScheduler 추가 job)
- GET /api/themes/{id}/history?period=1d 엔드포인트 신규
- ThemeDetail: 당일 테마 강도 추이 라인 차트
```

---

### Phase 3 — 기능 확장

#### 3-1. 종목 검색

```
- backend: GET /api/stocks/search?q={keyword}
  └── 네이버 증권 자동완성 API 활용
- frontend: 글로벌 검색바 (디바운스 300ms) + 결과 모달
```

#### 3-2. 즐겨찾기

```
- useFavorites() 훅: localStorage 저장
- ThemeCard: 즐겨찾기 토글 버튼 (★)
- Dashboard: "즐겨찾기" / "전체" 탭 분리
```

#### 3-3. 종목 상세 정보 확장

```
- naver_client.py: get_stock_detail() 추가
  └── BeautifulSoup4로 52주 최고/최저가, PER, PBR, 시가총액 파싱
- GET /api/stocks/{code}/detail 엔드포인트 신규
- StockTable: 종목 클릭 시 상세 모달
```

#### 3-4. 알림 고도화

```
- 조건 추가: "change_5min" (5분 내 등락률 변화량)
- 알림 이력 페이지: /alerts/history
- 알림 활성/비활성 토글
```

---

### Phase 4 — UX & UI 품질

#### 4-1. 모바일 반응형

```
- theme-grid: 모바일 1열, 태블릿 2열, 데스크탑 4열
- StockTable: 모바일 가로 스크롤 또는 카드형 전환
- IndexBar: 모바일 컴팩트 레이아웃
```

#### 4-2. 다크모드

```
- CSS 변수 기반 컬러 시스템 구축
- useTheme() 훅: localStorage 저장 + prefers-color-scheme 감지
- 헤더 토글 버튼
```

#### 4-3. 로딩 & 에러 UX

```
- ThemeCard 스켈레톤 UI
- React ErrorBoundary 컴포넌트 (App.tsx 최상위 래핑)
- 토스트 알림 (알림 생성/삭제 피드백)
```

---

### Phase 5 — 배포

#### 5-1. Docker 정비

```
- frontend/nginx.conf: /api/* 프록시 + SPA 라우팅
- docker-compose.yml: nginx 서비스 추가, DB 볼륨 영속성 보장
```

#### 5-2. CI/CD

```
- .github/workflows/ci.yml
  └── backend pytest + frontend ESLint/build 자동화
```

---

### 고도화 로드맵

```
Week 1: Phase 1 (안정성)
  ├── 종목코드 검증 + themes.json 정비
  ├── 네이버 API 재시도 로직 (tenacity)
  └── SQLite 마이그레이션

Week 2: Phase 2 (시각화)
  ├── Dashboard 수평 막대 차트 (Recharts)
  ├── ThemeDetail 종목 차트
  └── 히스토리 스냅샷 수집 시작

Week 3: Phase 3 (기능)
  ├── 종목 검색 (자동완성 + 모달)
  ├── 즐겨찾기
  └── 종목 상세 정보 (52주, PER 등)

Week 4: Phase 4+5 (UX + 배포)
  ├── 모바일 반응형
  ├── 다크모드
  └── Docker + nginx 배포 완성
```
