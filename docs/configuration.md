[← Utilities](utilities.md) · [Back to README](../README.md) · [Next Page →](troubleshooting.md)

# Configuration

Все переменные окружения и опции конфигурации.

## Environment Variables

### Garmin Connect credentials

| Variable | Required | Description |
|----------|----------|-------------|
| `GARMIN_EMAIL` | Да* | Email от Garmin Connect аккаунта |
| `GARMIN_PASSWORD` | Да* | Пароль (необязательно если уже в env) |
| `GARMIN_TOKENSTORE` | Нет | Путь к директории токенов (default: `~/.garth`) |
| `GARMINTOKENS` | Нет | Алиас для `GARMIN_TOKENSTORE` (совместимость) |

*\*Требуется либо переменная, либо интерактивный ввод при первом запуске*

### .env файл

Проект загружает `.env` через `python-dotenv`. Создайте в корне:

```bash
GARMIN_EMAIL="you@example.com"
GARMIN_PASSWORD="your_password"
# GARMIN_TOKENSTORE="~/.garth"  # опционально
```

`.env` уже в `.gitignore`.

## Gar Garmin Connect Session

Сессия Garmin Connect хранится в `~/.garth/` между запусками.

```bash
# Очистить сессию и залогиниться заново
rm -rf ~/.garth

# Или через аргумент
python garmin_export.py --clear  # только если поддерживается
```

## FIT Directory Structure

```bash
fit/              # корень (можно изменить через аргументы)
├── export/       # сюда сохраняются скачанные FIT файлы
├── mod/          # модифицированные файлы
├── original/     # оригиналы после модификации
└── uploaded/     # успешно загруженные
```

Все директории создаются автоматически при первом запуске.

## Activity Type Filtering

`garmin_export.py` фильтрует по типу активности. По умолчанию:

| Type Key | Description |
|----------|-------------|
| `cycling` | Generic cycling |
| `road_cycling` | Road cycling |
| `mountain_biking` | Mountain biking |
| `indoor_cycling` | Indoor cycling |
| `virtual_ride` | Virtual ride (Zwift и др.) |
| `gravel_cycling` | Gravel cycling |
| `e_bike_fitness` | E-bike |

Добавить дополнительные типы:

```bash
python garmin_export.py --include-type virtual_ride --include-type cycling
```

Это обновляет множество CYCLING_TYPE_KEYS.

## Presets для device spoofing

`fit_autofix.py` и `fit_device_change.py` используют preset ID:

| ID | Device | Manufacturer | Product |
|----|--------|-------------|---------|
| `1` | Garmin Edge 520 | 1 | 2067 |
| `2` | Tacx Neo 2 Smart | 89 | 4266 |
| `3` | Zwift (original) | 260 | 0 |

Default preset — `2` (Tacx Neo 2 Smart).

## Скрипты и их аргументы

### garmin_export.py

```bash
python garmin_export.py \
  --email "you@example.com" \
  --password "your_password" \
  --tokenstore "~/.garth" \
  --limit 10 \
  --output-dir fit/export \
  --include-type virtual_ride
```

### fit_autofix.py

```bash
python fit_autofix.py \
  --fit-dir fit/export \
  --fit-mod-dir fit/mod \
  --preset 2 \
  --verbose
```

### garmin_import.py

```bash
python garmin_import.py \
  --email "you@example.com" \
  --password "your_password" \
  --tokenstore "~/.garth" \
  --input-dir fit/mod \
  --uploaded-dir fit/uploaded \
  --rename-attempts 3 \
  --rename-delay 3.0 \
  --keep-source \
  --verbose
```

## See Also

- [Getting Started](getting-started.md) — установка
- [Fit Workflow](fit-workflow.md) — основной workflow
- [Utilities](utilities.md) — дополнительные скрипты
- [Troubleshooting](troubleshooting.md) — решения проблем
