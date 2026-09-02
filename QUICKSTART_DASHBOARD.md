# 🚀 Быстрый старт: Обновленный Dashboard

## Что изменилось?

### ✅ Исправлено мерцание страницы
Раньше страница полностью перезагружалась каждые 5 секунд через `<meta refresh>`.  
Теперь используется `streamlit-autorefresh` - данные обновляются без перезагрузки страницы.

### ✅ Добавлен Live Video режим
Dashboard показывает видео с камеры в реальном времени с наложенной детекцией мешков.

### ✅ Современный дизайн
- Градиентный заголовок
- Карточки с тенями и hover-эффектами  
- Элегантные кнопки
- Скрыты стандартные элементы Streamlit

---

## 🔧 Установка

```bash
# 1. Установить зависимости
pip install -r requirements.txt

# Или вручную новые пакеты:
pip install streamlit-autorefresh requests
```

---

## 📹 Настройка Live Video

### Шаг 1: В detection service добавьте обновление кадра

В вашем файле обработки видео (например, `src/detection/detector.py`):

```python
from src.api.app import update_last_frame

class BagDetector:
    def process(self, frame):
        # Ваша логика детекции
        results = self.model(frame)
        frame_with_boxes = self.draw_boxes(frame, results)
        
        # 👇 ДОБАВИТЬ ЭТУ СТРОКУ 👇
        update_last_frame(frame_with_boxes)
        
        return frame_with_boxes
```

### Шаг 2: Запустите API сервис

```bash
cd /workspace
python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

API endpoint для live видео: `http://localhost:8000/api/v1/live/frame`

### Шаг 3: Запустите Dashboard

```bash
streamlit run src/kiosk/dashboard.py --server.port 8501
```

Откройте в браузере: `http://localhost:8501`

---

## 🎯 Как использовать

### Для операторов:

1. **Мониторинг**: 
   - Слева - live видео с конвейера
   - Справа - статистика по вагону
   
2. **Управление**:
   - "New Wagon" - начать новый вагон
   - "Close Wagon" - завершить текущий
   - "End Shift" - закрыть смену

3. **События**:
   - Таблица внизу показывает последние 30 детекций
   - Время, класс мешка, объем

### Для разработчиков:

#### Изменить интервал обновления:
```python
# В dashboard.py строка ~464
count = st_autorefresh(interval=5000, ...)  # 5 секунд вместо 3
```

#### Добавить кастомные стили:
```python
# В dashboard.py функция load_custom_css()
# Добавьте свои CSS правила в <style> блок
```

#### Настроить API endpoint:
```python
# В dashboard.py функция get_latest_frame_url()
api_url = f"http://{settings.API_HOST}:{settings.API_PORT}/api/v1/live/frame"
```

---

## 🐛 Troubleshooting

### "Waiting for video stream..."
1. Проверьте, что API запущен
2. Убедитесь, что `update_last_frame()` вызывается в detection loop
3. Проверьте логи API

### Dashboard не обновляется
```bash
# Переустановить streamlit-autorefresh
pip uninstall streamlit-autorefresh
pip install streamlit-autorefresh

# Перезапустить dashboard
streamlit run src/kiosk/dashboard.py
```

### Ошибки импорта
```bash
# Установить все зависимости
pip install -r requirements.txt
```

---

## 📊 Архитектура

```
┌─────────────────┐      ┌──────────────┐      ┌─────────────┐
│  Detection Svc  │─────▶│  FastAPI     │─────▶│  Dashboard  │
│  (YOLO+Track)   │      │  /live/frame │      │  (Streamlit)│
└─────────────────┘      └──────────────┘      └─────────────┘
         │                       │                      │
         │ update_last_frame()   │ GET /api/v1/         │ st_autorefresh
         ▼                       │ live/frame           │ (3 sec)
┌─────────────────┐      ┌───────┴──────┐      ┌─────────────┐
│  Last Frame     │      │              │      │             │
│  (in memory)    │      │              │      │             │
└─────────────────┘      └──────────────┘      └─────────────┘
```

---

## 📝 Changelog

### v2.0 - Текущая версия
- ✅ Нет мерцания страницы
- ✅ Live video режим
- ✅ Современный UI
- ✅ Helper функции `update_last_frame()` / `get_last_frame()`
- ✅ API endpoint `/api/v1/live/frame`

### v1.0 - Предыдущая версия
- ❌ Мерцание от meta refresh
- ❌ Нет live видео
- ❌ Простой UI без стилей

---

## 📞 Поддержка

Документация: `/workspace/docs/DASHBOARD_IMPROVEMENTS.md`

Исходный код:
- Dashboard: `/workspace/src/kiosk/dashboard.py`
- API: `/workspace/src/api/app.py`
