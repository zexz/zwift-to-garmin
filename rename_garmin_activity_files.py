#!/usr/bin/env python3
"""Rename Garmin FIT activity files from their embedded session metadata."""

import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from fitparse import FitFile


def session_values(path: Path) -> Optional[Dict]:
    """Return metadata from the first session message in a FIT activity."""
    session = next(FitFile(str(path)).get_messages("session"), None)
    if session is None:
        return None
    return {field.name: field.value for field in session}


def format_duration(seconds: object) -> str:
    total_seconds = int(float(seconds or 0))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h{minutes:02}m{seconds:02}s" if hours else f"{minutes}m{seconds:02}s"


def format_activity_filename(values: Dict) -> str:
    """Create a sortable filename from a Garmin FIT session."""
    start_time = values.get("start_time")
    if not isinstance(start_time, datetime):
        raise ValueError("session has no start_time")

    sport = str(values.get("sport") or "activity")
    sub_sport = str(values.get("sub_sport") or "")
    type_part = sport if sub_sport in ("", "generic") else f"{sport}-{sub_sport}"
    type_part = re.sub(r"[^a-z0-9-]+", "-", type_part.lower()).strip("-")
    distance_km = float(values.get("total_distance") or 0) / 1000
    duration = format_duration(values.get("total_timer_time"))
    return (
        f"{start_time:%Y-%m-%d_%H-%M-%S}_{type_part}_"
        f"{distance_km:.2f}km_{duration}.fit"
    )


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Preview or apply readable names to Garmin activity FIT files.",
    )
    parser.add_argument("activity_dir", type=Path, help="Directory containing activity FIT files")
    parser.add_argument("--apply", action="store_true", help="Rename files; otherwise preview only")
    return parser.parse_args()


def main():
    args = parse_arguments()
    if not args.activity_dir.is_dir():
        raise SystemExit(f"Directory does not exist: {args.activity_dir}")

    renames = []
    destinations = set()
    for source in sorted(args.activity_dir.glob("*.fit")):
        values = session_values(source)
        if values is None:
            print(f"[WARN] Skipping non-activity FIT file: {source.name}")
            continue
        destination = source.with_name(format_activity_filename(values))
        if destination.name in destinations:
            raise SystemExit(f"Duplicate generated filename: {destination.name}")
        destinations.add(destination.name)
        renames.append((source, destination))

    for source, destination in renames:
        print(f"{source.name}\n  → {destination.name}")
        if args.apply and source != destination:
            if destination.exists():
                raise SystemExit(f"Destination already exists: {destination}")
            source.rename(destination)

    action = "Renamed" if args.apply else "Previewed"
    print(f"{action} {len(renames)} activity file(s).")


if __name__ == "__main__":
    main()
