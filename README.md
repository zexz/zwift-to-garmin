# Garmin FIT Workflow

> Export Zwift rides from Garmin Connect, spoof device metadata, re-upload with custom titles.

## Quick Start

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
export GARMIN_EMAIL="you@example.com"
export GARMIN_PASSWORD="your_password"
./run_all.sh
```

`run_all.sh` uses `.venv/bin/python` when available, otherwise `python3` from
your shell. Install dependencies into the same environment used by the launcher.

## What It Does

1. **Export** — downloads cycling activities as FIT files from Garmin Connect
2. **Modify** — patches manufacturer/product fields (Zwift → Tacx Neo 2)
3. **Import** — uploads to Garmin Connect, renames with `[G]` prefix

Files already tagged `[G]` are skipped automatically.

## Key Features

- **Device spoofing** — changes Zwift manufacturer ID (260) to Tacx Neo 2 Smart (89)
- **Atomic re-upload** — deletes existing activity before re-upload to avoid duplicates
- **Auto-rename** — activity titled `[G] {activity}` for easy filtering
- **Rate limit handling** — exponential backoff with jitter for Garmin API
- **Session persistence** — Garmin tokens cached in `~/.garth`

## Folder Layout

```
fit/
├── export/     # downloaded from Garmin
├── mod/        # device metadata patched
├── original/   # archived originals
├── failed/     # rejected by Garmin; .error.txt contains the API error
└── uploaded/   # successfully re-uploaded
```

## Example

```bash
# Export last 10 cycling rides
python garmin_export.py --limit 10

# Patch device info (defaults to Tacx Neo 2 Smart)
python fit_autofix.py

# Upload and rename
python garmin_import.py --verbose
```

Or run all three at once:

```bash
./run_all.sh
```

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/getting-started.md) | Installation, setup, first steps |
| [Fit Workflow](docs/fit-workflow.md) | Detailed workflow walkthrough |
| [Utilities](docs/utilities.md) | fit_check.py, garminbadges-updater.py |
| [Configuration](docs/configuration.md) | Environment variables |
| [Troubleshooting](docs/troubleshooting.md) | Common issues and fixes |

## License

MIT
