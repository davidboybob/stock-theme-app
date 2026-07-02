#!/bin/bash
# 테마주 트레이딩 앱 로컬 실행 스크립트 (백엔드 + 프론트엔드)
cd "$(dirname "$0")"

echo "=== 기존 프로세스 정리 (포트 8000, 5173) ==="
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:5173 | xargs kill -9 2>/dev/null
sleep 1

echo "=== 백엔드 시작 (포트 8000) ==="
cd backend
if [ ! -d venv ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt
# 루트 .env 로드
set -a; source ../.env; set +a
uvicorn app.main:app --port 8000 &
BACKEND_PID=$!
cd ..

echo "=== 프론트엔드 시작 (포트 5173) ==="
cd frontend
[ -d node_modules ] || npm install
npm run dev &
FRONTEND_PID=$!
cd ..

sleep 3
open http://localhost:5173/portfolio

echo ""
echo "실행 중 — 종료하려면 이 창에서 Ctrl+C"
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
