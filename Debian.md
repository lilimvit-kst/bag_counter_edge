# Установка и запуск Bag Counter Edge на Debian 13

Данная инструкция описывает пошаговый процесс установки, настройки и запуска системы **Bag Counter Edge** на операционной системе Debian 13 (Trixie).

## Содержание
1. [Требования к системе](#требования-к-системе)
2. [Подготовка системы](#подготовка-системы)
3. [Установка зависимостей](#установка-зависимостей)
4. [Настройка проекта](#настройка-проекта)
5. [Запуск приложения](#запуск-приложения)
6. [Использование системы](#использование-системы)
7. [Запуск в режиме киоска](#запуск-в-режиме-киоска-kiosk-mode)
8. [Мониторинг Prometheus/Grafana](#мониторинг-prometheusgrafana)
9. [Управление сервисами](#управление-сервисами)
10. [Диагностика проблем](#диагностика-проблем)

---

## Требования к системе

### Минимальные требования:
- ОС: Debian 13 (Trixie)
- Процессор: 4 ядра (рекомендуется 8+)
- ОЗУ: 8 ГБ (рекомендуется 16+ ГБ)
- Диск: 50 ГБ свободного места
- GPU: NVIDIA с поддержкой CUDA (опционально, для ускорения ML)

### Программные требования:
- Python 3.10+
- Docker и Docker Compose (рекомендуемый способ запуска)
- Камера RTSP или USB-камера

---

## Подготовка системы

### 1. Обновление пакетов
```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Установка базовых инструментов
```bash
sudo apt install -y git curl wget build-essential libsqlite3-dev python3-venv python3-pip
```

### 3. Установка Python 3.10+ (если версия ниже)
```bash
sudo apt install -y python3 python3-dev
python3 --version  # Должна быть версия 3.10 или выше
```

---

## Установка зависимостей

### Вариант А: Использование Docker (Рекомендуется)

#### 1. Установка Docker
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
rm get-docker.sh
```

#### 2. Добавление пользователя в группу docker
```bash
sudo usermod -aG docker $USER
newgrp docker
```

#### 3. Установка Docker Compose
```bash
sudo apt install -y docker-compose-plugin
```

Проверка установки:
```bash
docker --version
docker compose version
```

### Вариант Б: Прямая установка (без Docker)

#### 1. Создание виртуального окружения
```bash
cd /opt  # Или другая директория для проектов
git clone <URL-репозитория> bag-counter-edge
cd bag-counter-edge

python3 -m venv venv
source venv/bin/activate
```

#### 2. Установка зависимостей Python
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 3. Установка системных библиотек для OpenCV
```bash
sudo apt install -y libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev \
                    libgomp1 libavcodec-dev libavformat-dev libswscale-dev \
                    libv4l-dev libatlas-base-dev
```

---

## Настройка проекта

### 1. Клонирование репозитория
```bash
cd /opt
git clone <URL-репозитория> bag-counter-edge
cd bag-counter-edge
```

### 2. Создание файла конфигурации `.env`
Скопируйте пример файла окружения:
```bash
cp .env.example .env
```

Или создайте файл вручную:
```bash
cat > .env << EOF
# Основные настройки
ENVIRONMENT=production
DEBUG=false

# База данных
DATABASE_URL=sqlite:///./storage/bag_counter.db

# Redis (для Celery)
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# API настройки
API_HOST=0.0.0.0
API_PORT=8000
API_SECRET_KEY=your-super-secret-key-change-in-production
API_CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000","http://localhost:8501","http://127.0.0.1:8501"]

# Камера
CAMERA_SOURCE=rtsp://admin:password@192.168.1.100:554/stream1
# Или для USB-камеры: CAMERA_SOURCE=0
CAMERA_FPS=30
CAMERA_WIDTH=1920
CAMERA_HEIGHT=1080

# ML модель
YOLO_MODEL_PATH=models/yolov8n.pt
CONFIDENCE_THRESHOLD=0.5
IOU_THRESHOLD=0.45

# Нотификации
ENABLE_EMAIL_NOTIFICATIONS=false
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
SMTP_USER=user@example.com
SMTP_PASSWORD=password
NOTIFICATION_EMAIL=admin@example.com

ENABLE_TELEGRAM_NOTIFICATIONS=false
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id

# Лимиты
RATE_LIMIT_PER_MINUTE=60
MAX_CONCURRENT_STREAMS=4
EOF
```

### 3. Генерация секретного ключа
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```
Замените `your-super-secret-key-change-in-production` в `.env` на сгенерированное значение.

### 4. Создание директорий для данных
```bash
mkdir -p storage/models storage/logs storage/clips storage/db
chmod 755 storage
```

### 5. Скачивание ML модели (если не включена в репозиторий)
```bash
mkdir -p models
# Пример скачивания YOLOv8n
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt -O models/yolov8n.pt
```

---

## Запуск приложения

### Выбор конфигурации Docker Compose

В зависимости от количества ядер процессора выберите соответствующий файл конфигурации:

#### Для систем с 2 ядрами CPU
```bash
docker compose -f docker-compose-2CPU.yml up -d
```
Этот файл оптимизирован для двуядерных систем с ограниченными ресурсами:
- Лимит CPU для edge-cv: 1.8
- Резервирование CPU: 0.5
- Ограниченное потребление памяти

#### Для систем с 4 и более ядрами CPU
```bash
docker compose -f docker-compose-4CPU.yml up -d
```
Этот файл предназначен для систем с четырьмя и более ядрами:
- Лимит CPU для edge-cv: 3.0
- Резервирование CPU: 1.0
- Увеличенное выделение памяти для всех сервисов

#### Стандартный запуск (автоопределение)
```bash
docker compose up -d
```
Использует основной файл `docker-compose.yml` с настройками по умолчанию.

#### Запуск с мониторингом (Prometheus + Grafana)
```bash
# Сначала запустите основные сервисы
docker compose up -d

# Затем запустите стек мониторинга
docker compose -f docker-compose.monitoring.yml up -d
```
Этот вариант добавляет сервисы Prometheus (сбор метрик) и Grafana (визуализация):
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin123)
- Metrics endpoint: http://localhost:8000/metrics

Подробнее см. раздел [Мониторинг Prometheus/Grafana](#мониторинг-prometheusgrafana).

### Вариант А: Через Docker Compose (Рекомендуется)

#### 1. Запуск всех сервисов
```bash
docker compose -f docker-compose-2CPU.yml up -d  # Для 2 ядер
# или
docker compose -f docker-compose-4CPU.yml up -d  # Для 4+ ядер
```

#### 2. Проверка статуса контейнеров
```bash
docker compose ps
```

Ожидаемый вывод:
```
NAME                    STATUS          PORTS
bag-counter-api         Up (healthy)    0.0.0.0:8000->8000/tcp
bag-counter-worker      Up              
bag-counter-redis       Up              6379/tcp
bag-counter-camera      Up              
```

#### 3. Просмотр логов
```bash
# Все логи
docker compose logs -f

# Логи конкретного сервиса
docker compose logs -f api
docker compose logs -f camera
docker compose logs -f worker
```

#### 4. Остановка сервисов
```bash
docker compose down
```

#### 5. Перезапуск
```bash
docker compose restart
```

### Вариант Б: Прямой запуск (без Docker)

#### 1. Активация виртуального окружения
```bash
cd /opt/bag-counter-edge
source venv/bin/activate
```

#### 2. Запуск Redis (требуется для Celery)
```bash
sudo apt install -y redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

#### 3. Инициализация базы данных
```bash
export $(cat .env | xargs)
python3 src/main.py --init-db
```

#### 4. Запуск API сервера
```bash
uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload &
```

#### 5. Запуск Celery Worker
```bash
celery -A src.tasks.celery_app worker --loglevel=info --concurrency=4 &
```

#### 6. Запуск камеры (в отдельном терминале)
```bash
python3 src/capture/camera_stream.py
```

---

## Использование системы

### 1. Доступ к API

Основной эндпоинт: `http://localhost:8000`

Документация Swagger UI: `http://localhost:8000/docs`

#### Проверка здоровья системы
```bash
curl http://localhost:8000/api/health
```

Ответ:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00",
  "services": {
    "api": "ok",
    "database": "ok",
    "camera": "ok",
    "worker": "ok"
  }
}
```

#### Получение статистики
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:8000/api/stats/today
```

#### Управление камерой
```bash
# Старт потока
curl -X POST -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:8000/api/camera/start

# Стоп потока
curl -X POST -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:8000/api/camera/stop

# Статус камеры
curl -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:8000/api/camera/status
```

### 2. Работа с веб-интерфейсом (Kiosk)

Если развернут интерфейс киоска:
```
http://localhost:8501
```

Основные функции:
- Мониторинг в реальном времени через WebSocket (без перезагрузки страницы)
- Просмотр статистики по пакетам с разбивкой по классам (25kg, 50kg, empty)
- Live Video режим для просмотра видео с камеры в реальном времени
- Настройка зон детекции
- Управление уведомлениями
- Индикатор подключения и статус системы

**Новые возможности Dashboard:**
- Real-time обновления счётчиков без моргания страницы
- Анимация изменений (+N since last update)
- Красивый современный UI с градиентами и тенями
- Live режим с пульсирующим индикатором
- Боковая панель с настройками

### 2.1. Мониторинг через Grafana

Для доступа к дашбордам мониторинга:
```
http://localhost:3000
```
Логин: `admin`, Пароль: `admin123`

Доступные дашборды:
- **Bag Counter Operations**: общая статистика, метрики обработки, системные ресурсы
- Метрики в реальном времени: количество мешков, время обработки, ошибки детекции
- Графики: API latency, CPU/Memory usage, WebSocket клиенты

Альтернативно, сырые метрики Prometheus доступны по адресу:
```
http://localhost:8000/metrics
```

### 3. Настройка уведомлений

#### Email уведомления
Отредактируйте `.env`:
```env
ENABLE_EMAIL_NOTIFICATIONS=true
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
NOTIFICATION_EMAIL=admin@example.com
```

Перезапустите worker:
```bash
docker compose restart worker
```

#### Telegram уведомления
1. Создайте бота через @BotFather
2. Узнайте Chat ID через @userinfobot
3. Обновите `.env`:
```env
ENABLE_TELEGRAM_NOTIFICATIONS=true
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHAT_ID=-1001234567890
```

### 4. Просмотр записанных клипов

Клипы сохраняются в директорию `storage/clips/`:
```bash
ls -lh storage/clips/
```

Доступ через API:
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:8000/api/clips?date=2024-01-01
```

---

## Запуск в режиме киоска (Kiosk Mode)

Режим киоска позволяет автоматически запускать веб-интерфейс системы при загрузке компьютера в полноэкранном режиме. Это полезно для развертывания на производственных линиях.

### 1. Установка необходимых пакетов

```bash
sudo apt update
sudo apt install -y chromium-browser xdotool wmctrl openbox
```

### 2. Настройка автозапуска браузера

Создайте файл автозапуска:
```bash
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/kiosk.desktop << EOF
[Desktop Entry]
Type=Application
Name=Bag Counter Kiosk
Exec=/opt/bag-counter-edge/scripts/start-kiosk.sh
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF
```

### 3. Создание скрипта запуска киоска

```bash
sudo mkdir -p /opt/bag-counter-edge/scripts
sudo tee /opt/bag-counter-edge/scripts/start-kiosk.sh > /dev/null << 'EOF'
#!/bin/bash

# Ждем запуска API
echo "Ожидание запуска API..."
until curl -s http://localhost:8000/api/health > /dev/null; do
    sleep 5
done

echo "API доступен, запуск браузера..."

# Запуск Chromium в режиме киоска
chromium-browser \
    --kiosk \
    --no-first-run \
    --disable-checker-imaging-fix \
    --disable-translate \
    --disable-background-networking \
    --disable-default-apps \
    --disable-extensions \
    --disable-sync \
    --noerrdialogs \
    --window-size=1920,1080 \
    --start-fullscreen \
    --app=http://localhost:8501 \
    --user-data-dir=/tmp/chromium-kiosk

# Обработка закрытия
trap "killall chromium-browser" EXIT
EOF

chmod +x /opt/bag-counter-edge/scripts/start-kiosk.sh
```

### 4. Настройка дисплейного менеджера (опционально)

Для автоматического входа в систему и запуска киоска:

```bash
# Для LightDM
sudo apt install -y lightdm lightdm-gtk-greeter
sudo systemctl enable lightdm

# Настройка автоматического входа
sudo mkdir -p /etc/lightdm
sudo tee /etc/lightdm/lightdm.conf > /dev/null << EOF
[Seat:*]
autologin-user=$USER
autologin-user-timeout=0
session-session=openbox
EOF
```

### 5. Конфигурация Openbox для киоска

```bash
mkdir -p ~/.config/openbox
cat > ~/.config/openbox/autostart << 'EOF'
# Отключаем скринсейвер
xset s off
xset -dpms
xset s noblank

# Запуск киоска через 5 секунд
(sleep 5 && /opt/bag-counter-edge/scripts/start-kiosk.sh) &
EOF
```

### 6. Быстрый запуск киоска (ручной режим)

Для быстрого тестирования без настройки автозапуска:

```bash
cd /opt/bag-counter-edge
./scripts/start-kiosk.sh
```

Или вручную откройте браузер в режиме киоска:
```bash
chromium-browser --kiosk --app=http://localhost:8501
```

### 7. Выход из режима киоска

- **Стандартный выход**: `Alt+F4`
- **Закрыть браузер**: `Ctrl+Q`
- **Переключиться в другой workspace**: `Ctrl+Alt+Стрелки`
- **Открыть терминал**: `Ctrl+Alt+T` (если настроен)

### 8. Остановка киоска

```bash
# Принудительное завершение
killall chromium-browser

# Или перезагрузка системы
sudo reboot
```

### 9. Диагностика проблем киоска

```bash
# Проверка запущенных процессов
ps aux | grep chromium

# Логи X сервера
cat /var/log/Xorg.0.log | grep -i error

# Проверка доступности веб-интерфейса
curl -I http://localhost:8501

# Тестирование без режима киоска
chromium-browser http://localhost:8501
```

### 10. Настройка разрешения экрана

Если разрешение не соответствует монитору:

```bash
# Просмотр доступных разрешений
xrandr

# Установка нужного разрешения (пример)
xrandr --output HDMI-1 --mode 1920x1080 --rate 60
```

Добавьте команду `xrandr` в `~/.config/openbox/autostart` перед запуском киоска.

---

## Мониторинг Prometheus/Grafana

Система включает интеграцию с Prometheus и Grafana для мониторинга производительности, метрик обработки и использования ресурсов.

### 1. Запуск мониторинга

```bash
# Запустить сервисы Prometheus и Grafana
docker compose -f docker-compose.monitoring.yml up -d
```

### 2. Доступ к интерфейсам

- **Grafana**: http://localhost:3000
  - Логин: `admin`
  - Пароль: `admin123`
  - Дашборд "Bag Counter Operations" импортируется автоматически

- **Prometheus**: http://localhost:9090
  - Просмотр метрик и выполнение запросов
  - Target status: http://localhost:9090/targets

- **Metrics endpoint**: http://localhost:8000/metrics
  - Сырые метрики в формате Prometheus

### 3. Доступные метрики

#### Метрики подсчёта мешков
- `bag_counter_bags_total{class,wagon_id,shift_id}` — общее количество подсчитанных мешков по классам
- `bag_counter_processing_time_seconds` — время обработки одного кадра/объекта
- `bag_counter_detection_confidence` — уверенность детекции объектов
- `bag_counter_detection_errors_total` — количество ошибок детекции

#### Метрики API
- `bag_counter_api_requests_total{method,endpoint,status}` — количество API запросов
- `bag_counter_api_latency_seconds{method,endpoint}` — задержки API

#### Метрики WebSocket
- `bag_counter_websocket_clients` — количество подключённых WebSocket клиентов
- `bag_counter_websocket_messages_total` — количество отправленных сообщений

#### Системные метрики
- `bag_counter_cpu_usage_percent` — использование CPU
- `bag_counter_memory_usage_bytes` — использование памяти
- `process_resident_memory_bytes` — резидентная память процесса
- `process_cpu_seconds_total` — общее время CPU

### 4. Настройка алертов (опционально)

Создайте файл алертов в `monitoring/prometheus/alerts.yml`:

```yaml
groups:
  - name: bag_counter_alerts
    rules:
      - alert: HighDetectionErrorRate
        expr: rate(bag_counter_detection_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Высокий уровень ошибок детекции"
          description: "Уровень ошибок детекции превышает 10% в течение 5 минут"

      - alert: HighProcessingTime
        expr: histogram_quantile(0.95, rate(bag_counter_processing_time_seconds_bucket[5m])) > 1
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Высокое время обработки"
          description: "P95 времени обработки превышает 1 секунду"
```

### 5. Обновление дашборда Grafana

Для импорта обновлённого дашборда:

```bash
# Копировать файл дашборда
cp monitoring/grafana/dashboards/bag-counter-ops.json /path/to/grafana/provisioning/dashboards/

# Перезапустить Grafana
docker compose -f docker-compose.monitoring.yml restart grafana
```

### 6. Остановка мониторинга

```bash
docker compose -f docker-compose.monitoring.yml down
```

**Примечание**: Данные Prometheus сохраняются в volume `prometheus_data`, данные Grafana — в `grafana_data`. Для полного сброса используйте флаг `-v`.

---

## Управление сервисами

### Создание systemd сервисов (для прямого запуска)

#### 1. Сервис API
```bash
sudo tee /etc/systemd/system/bag-counter-api.service > /dev/null << EOF
[Unit]
Description=Bag Counter API Service
After=network.target redis-server.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/bag-counter-edge
Environment="PATH=/opt/bag-counter-edge/venv/bin"
ExecStart=/opt/bag-counter-edge/venv/bin/uvicorn src.api.app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

#### 2. Сервис Celery Worker
```bash
sudo tee /etc/systemd/system/bag-counter-worker.service > /dev/null << EOF
[Unit]
Description=Bag Counter Celery Worker
After=network.target redis-server.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/bag-counter-edge
Environment="PATH=/opt/bag-counter-edge/venv/bin"
ExecStart=/opt/bag-counter-edge/venv/bin/celery -A src.tasks.celery_app worker --loglevel=info --concurrency=4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

#### 3. Сервис камеры
```bash
sudo tee /etc/systemd/system/bag-counter-camera.service > /dev/null << EOF
[Unit]
Description=Bag Counter Camera Stream
After=network.target bag-counter-api.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/bag-counter-edge
Environment="PATH=/opt/bag-counter-edge/venv/bin"
ExecStart=/opt/bag-counter-edge/venv/bin/python3 src/capture/camera_stream.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

#### 4. Активация сервисов
```bash
sudo systemctl daemon-reload
sudo systemctl enable bag-counter-api bag-counter-worker bag-counter-camera
sudo systemctl start bag-counter-api bag-counter-worker bag-counter-camera
```

#### 5. Управление сервисами
```bash
# Статус
sudo systemctl status bag-counter-api

# Остановка
sudo systemctl stop bag-counter-api

# Запуск
sudo systemctl start bag-counter-api

# Перезапуск
sudo systemctl restart bag-counter-api

# Просмотр логов
sudo journalctl -u bag-counter-api -f
```

---

## Диагностика проблем

### 1. Проверка логов

#### Docker
```bash
docker compose logs -f api
docker compose logs -f camera
docker compose logs -f worker
```

#### Systemd
```bash
sudo journalctl -u bag-counter-api -f
sudo journalctl -u bag-counter-worker -f
sudo journalctl -u bag-counter-camera -f
```

#### Файлы логов
```bash
tail -f storage/logs/app.log
tail -f storage/logs/camera.log
tail -f storage/logs/worker.log
```

### 2. Частые проблемы и решения

#### Проблема: Камера не подключается
**Решение:**
```bash
# Проверка доступности RTSP потока
ffprobe rtsp://admin:password@192.168.1.100:554/stream1

# Проверка USB камеры
ls -l /dev/video*
ffmpeg -f v4l2 -list_formats all -i /dev/video0
```

#### Проблема: Ошибки базы данных
**Решение:**
```bash
# Проверка целостности SQLite
sqlite3 storage/bag_counter.db "PRAGMA integrity_check;"

# Восстановление из бэкапа
cp storage/bag_counter.db.backup storage/bag_counter.db
```

#### Проблема: Worker не обрабатывает задачи
**Решение:**
```bash
# Проверка Redis
redis-cli ping  # Должен вернуть PONG

# Перезапуск Redis
sudo systemctl restart redis-server

# Проверка очереди Celery
celery -A src.tasks.celery_app inspect active
celery -A src.tasks.celery_app inspect registered
```

#### Проблема: Недостаточно памяти
**Решение:**
```bash
# Уменьшение concurrency worker
# В .env или docker-compose.yml:
CELERY_WORKER_CONCURRENCY=2

# Очистка старых клипов
find storage/clips -type f -mtime +7 -delete
```

#### Проблема: GPU не используется
**Решение:**
```bash
# Проверка драйверов NVIDIA
nvidia-smi

# Установка NVIDIA Container Toolkit (для Docker)
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update
sudo apt install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### 3. Мониторинг ресурсов

```bash
# Использование CPU и памяти
htop

# Использование GPU
watch -n 1 nvidia-smi

# Дисковое пространство
df -h

# Сетевая активность
iftop
```

---

## Резервное копирование

### Создание бэкапа
```bash
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
tar -czvf bag-counter-backup-$BACKUP_DATE.tar.gz \
    storage/db \
    storage/models \
    .env
```

### Восстановление из бэкапа
```bash
tar -xzvf bag-counter-backup-20240101_120000.tar.gz -C /opt/bag-counter-edge/
```

---

## Обновление системы

### Docker
```bash
cd /opt/bag-counter-edge
git pull
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Прямая установка
```bash
cd /opt/bag-counter-edge
git pull
source venv/bin/activate
pip install -r requirements.txt --upgrade
sudo systemctl restart bag-counter-api bag-counter-worker
```

---

## Безопасность

### 1. Настройка фаервола
```bash
sudo apt install -y ufw
sudo ufw default deny incoming
sudo ufw allow 22/tcp        # SSH
sudo ufw allow 8000/tcp      # API
sudo ufw allow 3000/tcp      # Grafana Dashboard
sudo ufw allow 8501/tcp      # Kiosk Dashboard (Streamlit)
sudo ufw allow 9090/tcp      # Prometheus (опционально)
sudo ufw enable
```

### 2. Регулярное обновление
```bash
sudo apt update && sudo apt upgrade -y
```

### 3. Аудит безопасности
- Регулярно меняйте `API_SECRET_KEY`
- Используйте HTTPS в production (настройте reverse proxy с nginx + letsencrypt)
- Ограничьте доступ к API по IP
- Включите rate limiting

---

## Дополнительная документация

- [API Documentation](http://localhost:8000/docs)
- [README.md](./README.md)
- [Docs](./docs/)
- [Мониторинг Prometheus/Grafana](./MONITORING.md)
- [Metrics Endpoint](http://localhost:8000/metrics)
- [Grafana Dashboard](http://localhost:3000)
- [Kiosk Dashboard](http://localhost:8501)

## Поддержка

При возникновении проблем:
1. Проверьте логи (`docker compose logs` или `journalctl`)
2. Убедитесь, что все зависимости установлены
3. Проверьте конфигурацию в `.env`
4. Обратитесь к документации API
