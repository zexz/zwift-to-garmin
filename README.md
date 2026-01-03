# Garmin FIT Workflow

Tools for exporting Zwift rides from Garmin Connect, tweaking them locally, and re‑uploading with custom titles/device metadata.

## Folder Layout

```
fit/
├── export/     (output from garmin_export.py)
├── mod/        (modified files ready for upload)
├── original/   (archive of exported files after modification)
└── uploaded/   (files already imported back to Garmin)
```

> Adjust any script arguments if you prefer different directories, but the defaults above are assumed throughout.

## Prerequisites

```bash
pip install -r requirements.txt
export GARMIN_EMAIL="you@example.com"
export GARMIN_PASSWORD="your_password"
```

Optional: save credentials in a `.env` file (dotenv is loaded automatically).

---

## 1. Download rides — `garmin_export.py`

Fetches the most recent Garmin activities (default cycling only) and saves their FIT files into `fit/export/`.

```bash
python garmin_export.py --limit 50 --output-dir fit/export
```

Key options:

- `--include-type <typeKey>` – append multiple times to allow more activity types.
- `--output-dir` – change export destination.

The script skips any activity whose title already starts with `[G]`, so previously re‑uploaded rides are ignored automatically.

---

## 2. Modify device metadata — `fit_autofix.py`

Copies FIT files from `fit/export/` to `fit/mod/`, updating manufacturer/product fields (defaults to Tacx Neo 2 Smart preset) and archiving originals into `fit/original/`.

```bash
# Convert every new export
python fit_autofix.py --fit-dir fit/export --fit-mod-dir fit/mod

# Convert a single file with a custom preset
python fit_autofix.py fit/export/2127.fit -p 1
```

Highlights:

- Only processes files missing in `fit/mod/`.
- Presets:
  - `1` – Garmin Edge 520
  - `2` – Tacx Neo 2 Smart (default)
  - `3` – Zwift (restore original)
- Automatically recalculates FIT CRC and verifies the result.
- Moves the processed source file to `fit/original/` so the export folder stays tidy.

---

## 3. Upload & rename — `garmin_import.py`

Reads modified files from `fit/mod/`, uploads them to Garmin Connect, and renames each activity using the cleaned filename. Steps performed per file:

1. Derive title from filename and format as `[G] <prefix> - <rest>`.
2. Compute a signature (start time + duration + distance) from the FIT session.
3. Delete any existing activity that matches the signature (ensures atomic replace).
4. Upload the FIT file.
5. Retry locating the new activity and rename it with the generated title.
6. Move the FIT file from `fit/mod/` to `fit/uploaded/`.

```bash
python garmin_import.py \
  --input-dir fit/mod \
  --uploaded-dir fit/uploaded \
  --rename-attempts 3 \
  --rename-delay 3 \
  --verbose
```

Flags:

- `--keep-source` – copy instead of move when archiving to `fit/uploaded/`.
- `--rename-attempts` / `--rename-delay` – tune polling loop for Garmin API slowness.
- `--verbose` – print upload responses, signature matches, and rename diagnostics.

---

## End-to-End Checklist

1. `garmin_export.py --limit 50 --output-dir fit/export`
2. `fit_autofix.py --fit-dir fit/export --fit-mod-dir fit/mod`
3. `garmin_import.py --input-dir fit/mod --uploaded-dir fit/uploaded --verbose`

Everything already renamed with `[G]` stays untouched, original downloads are archived, and uploads are retried until named correctly.

### Run the three steps automatically

If you prefer a single command, use the helper script:

```bash
./run_all.sh
```

It sequentially runs `garmin_export.py`, `fit_autofix.py`, and `garmin_import.py` with their default arguments (fails fast on any error). Make sure it is executable: `chmod +x run_all.sh`.

---

## Troubleshooting

| Issue | Suggested fix |
| --- | --- |
| `NotOpenSSLWarning` | Harmless warning from urllib3 due to macOS LibreSSL. Suppressed inside scripts. |
| `Could not determine activity ID` | Enable `--verbose` on import to confirm Garmin has finished processing the upload; the script automatically retries signature matching. |
| Duplicate uploads | Ensure `fit/mod/` contains only one copy per activity; the importer deletes matching live activities before re-uploading. |

Need deeper FIT inspection? Use `fit_check.py <path>` to dump headers and session stats.

---

## License

MIT – feel free to adapt for personal workflows. Pull requests welcome.
