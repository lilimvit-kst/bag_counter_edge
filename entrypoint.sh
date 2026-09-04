#!/bin/bash
# Entrypoint script to run both CV pipeline and FastAPI server

set -e

echo "Starting Bag Counter Edge services..."

# Start FastAPI server in background
echo "Starting FastAPI server on port 8000..."
uvicorn src.api.app:app --host 0.0.0.0 --port 8000 &
FASTAPI_PID=$!

# Wait for API server to be ready (max 10 seconds)
echo "Waiting for API server to start..."
for i in {1..10}; do
    if python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" 2>/dev/null; then
        echo "✓ API server is ready!"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "⚠ API server starting (may need more time)..."
        break
    fi
    sleep 1
done

# Start CV pipeline in foreground (replaces this shell process)
echo "Starting CV pipeline..."
exec python -m src.main
