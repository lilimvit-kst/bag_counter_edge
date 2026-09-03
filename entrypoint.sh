#!/bin/bash
# Entrypoint script to run both CV pipeline and FastAPI server

set -e

echo "Starting Bag Counter Edge services..."

# Start FastAPI server in background
echo "Starting FastAPI server on port 8000..."
uvicorn src.api.app:app --host 0.0.0.0 --port 8000 &
FASTAPI_PID=$!

# Give API server time to start
sleep 2

# Start CV pipeline in foreground
echo "Starting CV pipeline..."
python -m src.main

# Cleanup on exit
echo "Stopping services..."
kill $FASTAPI_PID 2>/dev/null || true
wait $FASTAPI_PID 2>/dev/null || true
