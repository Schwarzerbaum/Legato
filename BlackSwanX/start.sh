#!/bin/bash
# BlackSwanX — Start Script (Flask version)
cd "$(dirname "$0")"

echo "Starting BlackSwanX..."

# Start backend (Flask, no pydantic)
echo "[1/2] Starting backend on port 9100..."
PYTHONPATH=. .venv/bin/python backend/app_simple.py &
BACKEND_PID=$!

sleep 2

# Start frontend on port 9200
echo "[2/2] Starting frontend on port 9200..."
cd frontend
npx vite --port 9200 --strictPort &
FRONTEND_PID=$!
cd ..

echo ""
echo "=================================="
echo "  BlackSwanX is running!"
echo "  Frontend: http://localhost:9200"
echo "  Backend:  http://localhost:9100"
echo "=================================="
echo ""
echo "Press Ctrl+C to stop"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
