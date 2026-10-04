#!/usr/bin/env python3
"""Copy timed Garmin activities from a full Garmin data export."""

import argparse
import calendar
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from fitparse import FitFile


def months_ago(months: int, now: Optional[datetime] = None) -> datetime:
    """Return the timestamp at the same local day ``months`` calendar months ago."""
    now = now or datetime.now()
    month_index = now.year * 12 + now.month - 1 - months
    year, month_zero_based = divmod(month_index, 12)
    month = month_zero_based + 1
    day = min(now.day, calendar.monthrange(year, month)[1])
    return now.replace(year=year, month=month, day=day)


def activity_start_time(path: Path) -> Optional[datetime]:
    """Return a FIT activity's session start time, or None for non-activities."""
    try:
        sessions = FitFile(str(path)).get_messages("session")
        session = next(sessions, None)
    except Exception as exc:  # pylint: disable=broad-except
        print(f"[WARN] Skipping unreadable FIT file {path.name}: {exc}")
        return None

    if session is None:
        return None

    for field in session:
        if field.name == "start_time" and isinstance(field.value, datetime):
            return field.value
    return None


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Copy timed activities from a Garmin Data Export FIT folder.",
    )
    parser.add_argument("source_dir", type=Path, help="Garmin UploadedFiles_* folder")
    parser.add_argument("output_dir", type=Path, help="Directory for copied activity FIT files")
    parser.add_argument(
        "--since-months",
        type=int,
        default=6,
        help="Keep activities from the last N calendar months (default: 6)",
    )
    args = parser.parse_args()
    if args.since_months < 1:
        parser.error("--since-months must be at least 1")
    return args


def main():
    args = parse_arguments()
    if not args.source_dir.is_dir():
        raise SystemExit(f"Source directory does not exist: {args.source_dir}")

    cutoff = months_ago(args.since_months)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    activity_files = 0

    for path in sorted(args.source_dir.glob("*.fit")):
        start_time = activity_start_time(path)
        if start_time is None:
            continue
        activity_files += 1
        if start_time < cutoff:
            continue

        destination = args.output_dir / path.name
        if destination.exists():
            continue
        shutil.copy2(path, destination)
        copied += 1

    print(
        f"Activities found: {activity_files}; copied since {cutoff:%Y-%m-%d}: "
        f"{copied} → {args.output_dir}"
    )


if __name__ == "__main__":
    main()
