# Улучшения Dashboard (Kiosk UI)

## Обзор изменений

Были внесены значительные улучшения в пользовательский интерфейс оператора (Streamlit Dashboard):

### ✨ Основные улучшения

1. **Устранено мерцание страницы** - Используется `streamlit-autorefresh` для обновления данных без перезагрузки всей страницы
2. **Live режим видео** - Добавлена поддержка отображения видео в реальном времени с камеры
3. **Современный дизайн** - Полностью переработанный UI с градиентами, тенями и анимациями

---

## 🎨 Новый дизайн

### Визуальные улучшения:
- **Градиентный заголовок** с современным стилем
- **Карточки статусов** с hover-эффектами и тенями
- **Элегантные кнопки** с плавными переходами
- **Скрытые декорации Streamlit** (меню, footer)
- **Адаптивная компоновка** с использованием колонок

### Цветовая схема:
```css
Градиент: #667eea → #764ba2 (фиолетово-синий)
Карточки: Белый с тенями
Акценты: Emoji для классов мешков
```

---

## 📹 Live Video Режим

### Как это работает:

1. **API Endpoint**: `/api/v1/live/frame` возвращает последний кадр с детекцией
2. **Обновление**: Dashboard запрашивает кадр каждые 3 секунды через `st_autorefresh`
3. **Fallback**: Если нет live-потока, показывается последний записанный клип

### Интеграция с Detection Service:

Для работы live режима detection service должен обновлять последний кадр:

```python
from src.api.app import update_last_frame

# В вашем detection loop:
frame_with_detections = detector.process(frame)
update_last_frame(frame_with_detections)  # Сохранить для dashboard
```

### Пример использования в коде детекции:

```python
# В src/detection/detector.py или основном цикле
import cv2
from src.api.app import update_last_frame

class BagDetector:
    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        # ... ваша логика детекции ...
        frame_with_boxes = self.draw_detections(frame, results)
        
        # Обновить кадр для dashboard
        update_last_frame(frame_with_boxes)
        
        return frame_with_boxes
```

---

## 🔄 Auto-Refresh без мерцания

### Старый подход (проблематичный):
```html
<meta http-equiv="refresh" content="5">
```
❌ Перезагружает всю страницу, вызывает мерцание

### Новый подход (правильный):
```python
from streamlit_autorefresh import st_autorefresh

count = st_autorefresh(interval=3000, limit=None, key="datarefresh")
```
✅ Обновляет только данные, страница не моргает

### Интервал обновления:
- **3 секунды** - баланс между актуальностью и нагрузкой
- Можно настроить через параметр `interval` (в миллисекундах)

---

## 🚀 Установка зависимостей

```bash
# Установить новые зависимости
pip install streamlit-autorefresh>=0.1.0
pip install requests>=2.31.0

# Или через requirements.txt
pip install -r requirements.txt
```

---

## 📊 Структура Dashboard

### Компоненты:

1. **Header** - Градиентный заголовок с названием системы
2. **Live Video** (слева, 2/3 ширины) - Видеопоток с детекцией
3. **Status Cards** (справа, 1/3 ширины):
   - 👤 Operator - имя оператора
   - 🚂 Wagon - номер вагона
   - 📦 Total Bags - всего мешков + время последнего
   - ⚖️ Est. Weight - общий вес

4. **Bag Classification** - Разбивка по классам:
   - 🟡 25kg bags
   - 🟠 50kg bags
   - ⚪ Empty/defective bags

5. **Control Panel** - Кнопки управления:
   - 🚪 Close Wagon
   - 🔄 New Wagon
   - 🌙 End Shift

6. **Event Log** - Таблица последних событий

7. **System Info** - Техническая информация (в сворачиваемом блоке)

---

## 🔧 Настройка API для Live Video

### FastAPI endpoint уже добавлен:

```python
# src/api/app.py

@app.get("/api/v1/live/frame")
async def get_live_frame():
    """Get the latest video frame with detection overlay."""
    global _last_frame
    
    if _last_frame is None:
        # Fallback to last clip
        ...
    
    # Encode frame as JPEG
    _, buffer = cv2.imencode('.jpg', _last_frame)
    
    return Response(
        content=buffer.tobytes(),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache"}
    )
```

### Helper функции:

```python
# Обновить кадр из detection service
update_last_frame(frame: np.ndarray)

# Получить текущий кадр
get_last_frame() -> Optional[np.ndarray]
```

---

## 🎯 Рекомендации по использованию

### Для операторов:

1. **Мониторинг в реальном времени**: 
   - Откройте dashboard на планшете/мониторе
   - Live видео показывает текущую ситуацию на конвейере
   - Статистика обновляется автоматически каждые 3 сек

2. **Управление вагонами**:
   - Используйте кнопку "New Wagon" для начала загрузки нового вагона
   - "Close Wagon" завершает текущий вагон
   - "End Shift" закрывает смену и начинает новую

3. **Отслеживание событий**:
   - Таблица событий показывает последние 30 детекций
   - Время, класс мешка, объем, наличие клипа

### Для разработчиков:

1. **Интеграция live video**:
   ```python
   from src.api.app import update_last_frame
   
   # В основном цикле обработки видео
   for frame in video_stream:
       processed = detector.process(frame)
       update_last_frame(processed)  # <-- Добавить эту строку
   ```

2. **Настройка refresh interval**:
   ```python
   # В dashboard.py изменить интервал
   count = st_autorefresh(interval=5000, ...)  # 5 секунд вместо 3
   ```

3. **Кастомизация дизайна**:
   - CSS стили в функции `load_custom_css()`
   - Можно добавить темы, изменить цвета и т.д.

---

## 🐛 Troubleshooting

### Проблема: "Waiting for video stream..."

**Решение:**
1. Проверьте, что detection service запущен
2. Убедитесь, что вызывается `update_last_frame()` в цикле обработки
3. Проверьте логи API на ошибки

### Проблема: Dashboard не обновляется

**Решение:**
1. Проверьте установку `streamlit-autorefresh`:
   ```bash
   pip show streamlit-autorefresh
   ```
2. Перезапустите Streamlit server
3. Очистите кэш браузера

### Проблема: Мерцание всё ещё есть

**Решение:**
1. Убедитесь, что используется `st_autorefresh`, а не `<meta refresh>`
2. Проверьте, что в коде нет `st.rerun()` в цикле обновления
3. `st.rerun()` должен вызываться только при действиях пользователя

---

## 📈 Будущие улучшения

Возможные дальнейшие улучшения:

1. **WebSocket для real-time updates** - мгновенное обновление при детекции
2. **История производительности** - графики counts по времени
3. **Экспорт отчетов** - CSV/PDF экспорты смен
4. **Мульти-камера** - поддержка нескольких камер одновременно
5. **Alert система** - уведомления об аномалиях

---

## 📝 Changelog

### v2.0 (Текущая версия)
- ✅ Устранено мерцание страницы
- ✅ Добавлен live video режим
- ✅ Современный UI дизайн
- ✅ Улучшенная компоновка (video + stats side-by-side)
- ✅ Новые helper функции в API
- ✅ session state для форм

### v1.0 (Предыдущая версия)
- ❌ Мета-тег refresh вызывал мерцание
- ❌ Нет live видео
- ❌ Базовый UI без стилей
- ❌ Вертикальная компоновка
