# Getting Started

Установка, настройка и первый запуск.

## Prerequisites

- Python 3.8+
- pip3
- Аккаунт Garmin Connect

## Установка

```bash
git clone https://github.com/your-repo/garmin-badges.git
cd garmin-badges
pip install -r requirements.txt
```

## Настройка

Создайте файл `.env` в корне проекта:

```bash
GARMIN_EMAIL="you@example.com"
GARMIN_PASSWORD="your_password"
```

Или экспортируйте переменные:

```bash
export GARMIN_EMAIL="you@example.com"
export GARMIN_PASSWORD="your_password"
```

При первом запуске скрипты запросят учётные данные интерактивно, если переменные не заданы. Сессия сохраняется в `~/.garth` (токены Garmin Connect).

## Структура каталогов

```
fit/
├── export/     # FIT файлы после garmin_export.py
├── mod/        # Модифицированные файлы для upload
├── original/   # Архив оригиналов после модификации
└── uploaded/   # Успешно загруженные файлы
```

## Быстрый старт

Полный cycle за три шага:

```bash
python garmin_export.py --limit 10
python fit_autofix.py
python garmin_import.py --verbose
```

Или одной командой:

```bash
./run_all.sh
```

## Первый запуск

1. **Экспорт активностей:**
   ```bash
   python garmin_export.py --limit 5 --output-dir fit/export
   ```
   Скрипт загрузит последние cycling активности из Garmin Connect. Активности уже с префиксом `[G]` пропускаются автоматически.

2. **Модификация device metadata:**
   ```bash
   python fit_autofix.py --fit-dir fit/export --fit-mod-dir fit/mod
   ```
   По умолчанию используется preset Tacx Neo 2 Smart. Оригиналы перемещаются в `fit/original/`.

3. **Загрузка в Garmin:**
   ```bash
   python garmin_import.py --input-dir fit/mod --uploaded-dir fit/uploaded --verbose
   ```
   Файлы загружаются, активности переименовываются с префиксом `[G]`.

## Проверка установки

```bash
python fit_check.py fit/export/<file.fit>
```

Покажет информацию о FIT файле: device info, session data, activity details.

## Next Steps

- [Fit Workflow](fit-workflow.md) — подробнее о каждом шаге
- [Configuration](configuration.md) — все переменные окружения
- [Utilities](utilities.md) — дополнительные скрипты
- [Troubleshooting](troubleshooting.md) — решения частых проблем
