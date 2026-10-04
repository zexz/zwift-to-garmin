[← Getting Started](getting-started.md) · [Back to README](../README.md) · [Next Page →](utilities.md)

# Fit Workflow

Детальное описание трёхэтапного workflow: export → modify → import.

## Overview

```
garmin_export.py     →  fit/export/     (скачивание FIT файлов)
       ↓
fit_autofix.py       →  fit/mod/        (модификация device metadata)
       ↓
garmin_import.py     →  fit/uploaded/   (upload + rename)
                     →  fit/failed/     (Garmin rejected the FIT file)
```

## 1. Export — `garmin_export.py`

Скачивает FIT файлы из Garmin Connect.

```bash
python garmin_export.py --limit 10 --output-dir fit/export
```

### Опции

| Flag | Default | Description |
|------|---------|-------------|
| `--limit` | `3` | Сколько последних активностей проверять |
| `--output-dir` | `fit` | Папка для сохранения FIT файлов |
| `--include-type` | — | Добавить тип активности (можно указать несколько) |

### Фильтрация

- По умолчанию только cycling типы: `cycling`, `road_cycling`, `mountain_biking`, `indoor_cycling`, `virtual_ride`, `gravel_cycling`, `e_bike_fitness`
- Активности с именем, начинающимся с `[G]`, автоматически пропускаются

### Формат файлов

```
{activityId}_{startTime}_{sanitizedActivityName}.fit
```

## 2. Modify — `fit_autofix.py`

Модифицирует manufacturer/product поля в FIT файлах.

```bash
# Все новые файлы из fit/export/
python fit_autofix.py --fit-dir fit/export --fit-mod-dir fit/mod

# Один файл с конкретным preset
python fit_autofix.py fit/export/2127.fit -p 1
```

### Presets

| ID | Device | Manufacturer ID | Product ID |
|----|--------|-----------------|------------|
| `1` | Garmin Edge 520 | 1 | 2067 |
| `2` | Tacx Neo 2 Smart (default) | 89 | 4266 |
| `3` | Zwift (restore) | 260 | 0 |

### Что делает

1. Копирует файл в `fit/mod/`
2. Заменяет manufacturer ID (Zwift → target device) в первых 1200 байтах
3. Также заменяет product ID если он был 0
4. Пересчитывает FIT CRC
5. Перемещает оригинал в `fit/original/`

### Опции

| Flag | Description |
|------|-------------|
| `--fit-dir` | Исходная директория (default: `fit`) |
| `--fit-mod-dir` | Директория для модифицированных файлов (default: `fit/mod`) |
| `-p, --preset` | ID пресета устройства (default: `2`) |
| `--verbose` | Детальный вывод |

## 3. Import — `garmin_import.py`

Загружает модифицированные файлы в Garmin Connect и переименовывает активности.

```bash
python garmin_import.py \
  --input-dir fit/mod \
  --uploaded-dir fit/uploaded \
  --rename-attempts 3 \
  --rename-delay 3 \
  --verbose
```

### Что делает

1. **Signature matching** — вычисляет signature (start time + duration + distance) из FIT session
2. **Delete existing** — удаляет существующую активность с таким же signature (atomic replace)
3. **Upload** — загружает FIT файл
4. **Rename** — переименовывает активность в `[G] {title}` с retry логикой

### Опции

| Flag | Default | Description |
|------|---------|-------------|
| `--input-dir` | `fit/mod` | Директория с модифицированными файлами |
| `--uploaded-dir` | `fit/uploaded` | Куда перемещать успешно загруженные |
| `--failed-dir` | `fit/failed` | Куда перемещать файлы, отклонённые Garmin |
| `--rename-attempts` | `3` | Количество попыток rename |
| `--rename-delay` | `3.0` | Задержка между попытками (сек) |
| `--keep-source` | `False` | Копировать вместо move в uploaded |
| `--verbose` | `False` | Детальный вывод |

Если Garmin возвращает ошибку формата файла или API 400, файл переносится в
`fit/failed/`, а рядом создаётся `{filename}.error.txt` с ответом Garmin. Такие
файлы исключаются из следующих запусков; после исправления их можно вернуть в
`fit/mod/`. Временные ошибки сети и API 5xx остаются в очереди для повторной попытки.

### Retry логика rename

Если Garmin не сразу возвращает activity ID, скрипт:
1. Ждёт `--rename-delay` секунд
2. Повторяет попытку до `--rename-attempts` раз
3. signature matching по start time / distance / duration

## Автоматизация — `run_all.sh`

```bash
./run_all.sh
```

Последовательно выполняет все три шага. Fail-fast при любой ошибке.

```bash
chmod +x run_all.sh  # если ещё не исполняемый
```

## See Also

- [Getting Started](getting-started.md) — установка и быстрый старт
- [Configuration](configuration.md) — переменные окружения
- [Utilities](utilities.md) — дополнительные скрипты
- [Troubleshooting](troubleshooting.md) — решения проблем
