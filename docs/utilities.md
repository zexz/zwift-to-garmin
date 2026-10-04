[← Fit Workflow](fit-workflow.md) · [Back to README](../README.md) · [Next Page →](configuration.md)

# Utilities

Дополнительные скрипты, не входящие в основной workflow.

## `fit_check.py` — анализ FIT файла

Показывает структурную информацию из FIT файла.

```bash
python fit_check.py fit/export/20861519609_ACTIVITY.fit
```

### Вывод

- **File ID** — manufacturer, product, serial number
- **Device Info** — информация о устройстве(ях)
- **Session** — sport, distance, time, speed, heart rate, cadence, power
- **Activity** — время начала, timezone
- **Record Count** — количество data records

### Пример использования

```bash
# Проверить оригинальный файл после export
python fit_check.py fit/export/123456789_ACTIVITY.fit

# Проверить модифицированный файл
python fit_check.py fit/mod/123456789_ACTIVITY.fit

# Сравнить device info в оригинале и модификации
```

## `fit_device_change.py` — низкоуровневая модификация

То же что `fit_autofix.py`, но для одного файла без автообнаружения.

```bash
python fit_device_change.py <input.fit> <preset_id>
```

### Preset IDs

| ID | Device | Manufacturer ID | Product ID |
|----|--------|-----------------|------------|
| `1` | Garmin Edge 520 | 1 | 2067 |
| `2` | Tacx Neo 2 Smart | 89 | 4266 |
| `3` | Zwift | 260 | 0 |

### Пример

```bash
python fit_device_change.py fit/export/2127.fit 1
```

Это заменит manufacturer/product на Garmin Edge 520.

### Отличие от `fit_autofix.py`

| feature | `fit_autofix.py` | `fit_device_change.py` |
|---------|------------------|----------------------|
| Один файл | Да | Да |
| Много файлов | Да | Нет |
| Автообнаружение новых | Да | Нет |
| Preset selection | Интерактивная | Аргумент командной строки |
| Архивирование оригинала | Да | Нет |

## `garminbadges-updater.py` — sync badges

Синхронизирует earned badges и challenges с [garminbadges.com](https://garminbadges.com).

```bash
python garminbadges-updater.py
```

При первом запуске запрашивает:
1. Garmin Badges username
2. Garmin Badges email
3. Garmin Connect credentials

### Опции

| Flag | Description |
|------|-------------|
| `--clear` | Удалить сохранённые credentials и ввести заново |
| `--open-badges` | Открыть страницу badges после update |
| `--open-challenges` | Открыть страницу challenges после update |
| `--version` | Показать версию |
| `--V` | Verbose/debug mode |

### Требования

```bash
pip install garth
```

## Rate Limiting

Все скрипты, взаимодействующие с Garmin Connect API, используют `garmin_rate_limit.py`:

```python
from garmin_rate_limit import call_with_rate_limit_retry

call_with_rate_limit_retry(
    lambda: client.some_api_call(),
    action_label="fetch recent activities",
    max_attempts=5,
    base_delay=5.0,
    max_delay=120.0,
)
```

При HTTP 429 (rate limit) автоматически:
1. Парсит `Retry-After` header
2. Или использует exponential backoff с jitter
3. Повторяет до `max_attempts` раз

## See Also

- [Fit Workflow](fit-workflow.md) — основной workflow
- [Getting Started](getting-started.md) — установка
- [Configuration](configuration.md) — настройка
