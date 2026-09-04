#!/bin/bash
# Entrypoint script for Dashboard service

set -e

echo "Starting Bag Counter Edge Dashboard..."

# Запускаем Streamlit в фоне, явно указывая адрес и порт
# Перенаправляем вывод в лог-файл для отладки
streamlit run src/kiosk/dashboard.py \
    --server.address 0.0.0.0 \
    --server.port 8501 \
    --server.headless true \
    --server.enableCORS false \
    --server.enableXsrfProtection true \
    --browser.gatherUsageStats false \
    > /tmp/streamlit.log 2>&1 &

STREAMLIT_PID=$!

# Ждем пока порт откроется (максимум 30 секунд)
echo "Waiting for Streamlit to start on port 8501..."
for i in {1..30}; do
    if python -c "import socket; s = socket.socket(); result = s.connect_ex(('127.0.0.1', 8501)); exit(0 if result == 0 else 1)" 2>/dev/null; then
        echo "✓ Dashboard is ready on port 8501!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "⚠ Dashboard may not have started correctly. Check logs:"
        cat /tmp/streamlit.log
        exit 1
    fi
    sleep 1
done

# Держим процесс в фоне
wait $STREAMLIT_PID
