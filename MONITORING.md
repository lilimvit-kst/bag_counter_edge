# Мониторинг Bag Counter Edge с Prometheus и Grafana

## Обзор

Добавлена полная интеграция мониторинга на базе Prometheus/Grafana для отслеживания:
- Количества подсчитанных мешков (по классам, вагонам, сменам)
- Производительности системы (время обработки, latency API)
- Использования ресурсов (CPU, память)
- WebSocket подключений
- Ошибок детекции

## Быстрый старт

### 1. Запуск мониторинга

```bash
# Запустить Prometheus и Grafana
docker-compose -f docker-compose.monitoring.yml up -d

# Проверить статус
docker-compose -f docker-compose.monitoring.yml ps
```

### 2. Доступ к сервисам

| Сервис | URL | Логин/Пароль |
|--------|-----|--------------|
| Grafana | http://localhost:3000 | admin / admin123 |
| Prometheus | http://localhost:9090 | - |
| Metrics Endpoint | http://localhost:8000/metrics | - |

### 3. Импорт дашборда в Grafana

1. Откройте Grafana: http://localhost:3000
2. Перейдите в **Dashboards** → **Import**
3. Вставьте JSON из `monitoring/grafana/dashboards/bag-counter-ops.json`
4. Или используйте предустановленный дашборд "Bag Counter Edge - Operations Dashboard"

## Метрики Prometheus

### Counter (Счётчики)

| Метрика | Описание | Labels |
|---------|----------|--------|
| `bag_counter_bags_total` | Всего подсчитано мешков | `class`, `wagon_id`, `shift_id` |
| `bag_counter_detection_errors_total` | Ошибки детекции | `error_type` |
| `bag_counter_api_requests_total` | API запросы | `method`, `endpoint`, `status_code` |
| `bag_counter_notifications_sent_total` | Отправленные уведомления | `channel`, `type` |

### Gauge (Измерители)

| Метрика | Описание | Labels |
|---------|----------|--------|
| `bag_counter_active_wagon` | Текущий активный вагон | - |
| `bag_counter_active_shift` | Текущая активная смена | - |
| `bag_counter_websocket_clients` | Подключённые WebSocket клиенты | - |
| `bag_counter_camera_status` | Статус камеры (1/0) | `camera_id` |
| `bag_counter_memory_usage_bytes` | Использование памяти | - |
| `bag_counter_cpu_usage_percent` | Загрузка CPU | - |
| `bag_counter_celery_queue_size` | Размер очереди Celery | `queue_name` |

### Histogram (Гистограммы)

| Метрика | Описание | Buckets |
|---------|----------|---------|
| `bag_counter_processing_time_seconds` | Время обработки кадров | 10ms - 1s |
| `bag_counter_api_latency_seconds` | Latency API запросов | 1ms - 1s |
| `bag_counter_detection_confidence` | Уверенность детекции | 0.5 - 0.99 |

## Примеры PromQL запросов

```promql
# Общее количество мешков
sum(bag_counter_bags_total)

# Мешки по классам
sum by (class) (bag_counter_bags_total)

# P95 время обработки
histogram_quantile(0.95, rate(bag_counter_processing_time_seconds_bucket[5m]))

# Ошибки в секунду (5 мин)
sum(rate(bag_counter_detection_errors_total[5m]))

# Вес груза (кг)
sum(bag_counter_bags_total{class="25kg"}) * 25 + sum(bag_counter_bags_total{class="50kg"}) * 50
```

## Интеграция с основным приложением

Метрики автоматически экспортируются через endpoint `/metrics`.

Для записи событий в коде:

```python
from src.monitoring.metrics import (
    record_bag_detected,
    record_detection_confidence,
    record_detection_error,
    update_connected_clients,
)

# Запись детекции мешка
record_bag_detected(bag_class="50kg", wagon_id=1, shift_id=1)

# Запись уверенности детекции
record_detection_confidence(confidence=0.92)

# Запись ошибки
record_detection_error(error_type="occlusion")

# Обновление числа клиентов
update_connected_clients(count=5)
```

## Конфигурация

### Prometheus (`monitoring/prometheus.yml`)

- Интервал скрапинга: 15s
- Целевой сервис: `edge-cv:8000`
- Путь к метрикам: `/metrics`

### Grafana (`monitoring/grafana/`)

- Предустановленный datasource Prometheus
- Авто-импорт дашбордов из папки
- Refresh interval: 10s

## Production рекомендации

1. **Безопасность**: Смените пароль Grafana admin
2. **Alerting**: Настройте алерты в Prometheus на критичные метрики
3. **Retention**: Увеличьте retention period для долгосрочного хранения
4. **HA**: Для production рассмотрите кластер Prometheus

## Troubleshooting

### Prometheus не видит метрики

```bash
# Проверить доступность endpoint
curl http://localhost:8000/metrics

# Проверить логи Prometheus
docker logs bag_counter_prometheus
```

### Grafana не показывает данные

1. Проверьте datasource (Prometheus URL: `http://prometheus:9090`)
2. Убедитесь что Prometheus скрапит метрики
3. Проверьте временной диапазон на дашборде

## Дополнительные ресурсы

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [PromQL Cheat Sheet](https://promlabs.com/promql-cheat-sheet/)
