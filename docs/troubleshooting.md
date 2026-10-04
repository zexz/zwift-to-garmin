[← Configuration](configuration.md) · [Back to README](../README.md)

# Troubleshooting

Решения частых проблем.

## NotOpenSSLWarning

```
NotOpenSSLWarning: ... urllib3 v1.26 or later ...
```

Это безобидное предупреждение от urllib3 на macOS из-за LibreSSL. Подавляется внутри всех скриптов. Игнорируйте его.

## "Could not determine activity ID"

Garmin API медленно обрабатывает upload. Включите `--verbose` чтобы увидеть детали:

```bash
python garmin_import.py --verbose
```

Скрипт автоматически повторяет matching по signature (start time + duration + distance). Увеличьте количество попыток:

```bash
python garmin_import.py --rename-attempts 5 --rename-delay 5
```

## Duplicate uploads

Перед каждым upload скрипт удаляет существующую активность с тем же signature. Если дубли всё ещё появляются:

1. Проверьте что в `fit/mod/` только один файл на каждую активность
2. Убедитесь что signature корректно вычисляется
3. Включите `--verbose` — будут показаны signature matching decisions

## Rate limiting (HTTP 429)

Скрипты автоматически обрабатывают rate limiting через `garmin_rate_limit.py`. Если получаете 429:

1. Подождите before retry (exponential backoff with jitter)
2. Убедитесь что не запускаете одновременно несколько скриптов с одним аккаунтом
3. Garmin может временно блокировать при частых запросах

## Authentication failed

```bash
# Очистить сохранённую сессию
rm -rf ~/.garth

# Перелогиниться
python garmin_export.py
```

Введите credentials заново.

## FIT file verification failed

`fit_autofix.py` проверяет modified file через fitparse. Если verification failed but file still usable:

```
Verification note: [error]
File should still be usable.
```

Это обычно безобидно — файл будет работать несмотря на warning.

## Debug mode

Для максимально детального вывода:

```bash
python garmin_export.py --verbose  # если поддерживается
python garmin_import.py --verbose
python fit_autofix.py --verbose
```

Для `garminbadges-updater.py`:

```bash
python garminbadges-updater.py --V
```

## See Also

- [Getting Started](getting-started.md) — установка
- [Fit Workflow](fit-workflow.md) — основной workflow
- [Configuration](configuration.md) — настройка
- [Utilities](utilities.md) — дополнительные скрипты
