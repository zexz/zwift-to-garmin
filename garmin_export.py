#!/usr/bin/env python3
"""Download recent cycling activities from Garmin Connect."""

import argparse
import getpass
import os
import sys
import zipfile
import warnings
from io import BytesIO
from pathlib import Path
from typing import Dict, Iterable, List

from dotenv import load_dotenv

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
)
from urllib3.exceptions import NotOpenSSLWarning


warnings.simplefilter("ignore", NotOpenSSLWarning)

CYCLING_TYPE_KEYS = {
    "cycling",
    "road_cycling",
    "mountain_biking",
    "indoor_cycling",
    "virtual_ride",
    "gravel_cycling",
    "e_bike_fitness",
}


def resolve_credentials(email_arg: str = None, password_arg: str = None):
    load_dotenv()

    email = email_arg or os.getenv("GARMIN_EMAIL")
    if not email:
        print("Error: Garmin email is required (use --email or GARMIN_EMAIL env var)")
        sys.exit(1)

    password = password_arg or os.getenv("GARMIN_PASSWORD")
    if not password:
        password = getpass.getpass("Garmin password: ")

    return email, password


def connect(email: str, password: str) -> Garmin:
    try:
        client = Garmin(email, password)
        client.login()
        return client
    except GarminConnectAuthenticationError as exc:
        print(f"Authentication failed: {exc}")
        sys.exit(1)
    except GarminConnectConnectionError as exc:
        print(f"Connection error: {exc}")
        sys.exit(1)


def is_cycling_activity(activity: Dict) -> bool:
    activity_type = activity.get("activityType") or {}
    type_key = activity_type.get("typeKey") or ""
    return type_key.lower() in CYCLING_TYPE_KEYS


def is_marked_generated(activity: Dict) -> bool:
    name = (activity.get("activityName") or "").strip()
    return name.startswith("[G]")


def sanitize_filename(text: str) -> str:
    import re

    cleaned = re.sub(r"[^A-Za-z0-9\-]+", "_", text).strip("_")
    return cleaned or "activity"


def format_activity_name(activity: Dict) -> str:
    activity_name = activity.get("activityName") or "ride"
    start_time = activity.get("startTimeGMT", "").replace(":", "-").replace("T", "_")[:19]
    slug = sanitize_filename(activity_name)
    return "_".join(filter(None, [start_time, slug]))


def extract_fit_payload(data: bytes) -> bytes:
    """
    Garmin often returns FIT files wrapped in a ZIP archive even when requesting ORIGINAL.
    Detect and extract the first .fit entry if needed.
    """
    buffer = BytesIO(data)
    if not zipfile.is_zipfile(buffer):
        return data

    with zipfile.ZipFile(buffer) as archive:
        fit_members = [name for name in archive.namelist() if name.lower().endswith(".fit")]
        if not fit_members:
            raise ValueError("Downloaded archive does not contain a .fit file.")
        return archive.read(fit_members[0])


def download_activities(client: Garmin, activities: Iterable[Dict], output_dir: Path) -> List[Path]:
    saved_files = []
    output_dir.mkdir(parents=True, exist_ok=True)

    for activity in activities:
        activity_id = activity.get("activityId")
        if not activity_id:
            continue

        file_name = f"{activity_id}_{format_activity_name(activity)}.fit"
        destination = output_dir / file_name
        if destination.exists():
            print(f"Skipping {activity_id} (already exists)")
            continue

        try:
            data = client.download_activity(activity_id, Garmin.ActivityDownloadFormat.ORIGINAL)
        except Exception as exc:  # pylint: disable=broad-except
            print(f"Failed to download {activity_id}: {exc}")
            continue

        try:
            fit_bytes = extract_fit_payload(data)
        except ValueError as exc:
            print(f"Skipping {activity_id}: {exc}")
            continue

        destination.write_bytes(fit_bytes)
        saved_files.append(destination)
        print(f"Saved {destination}")

    return saved_files


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Download recent cycling FIT files from Garmin Connect.",
    )
    parser.add_argument(
        "--email",
        help="Garmin Connect account email (or set GARMIN_EMAIL)",
    )
    parser.add_argument(
        "--password",
        help="Garmin Connect password (or set GARMIN_PASSWORD)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="How many recent activities to inspect (default: 3)",
    )
    parser.add_argument(
        "--output-dir",
        default="fit",
        help="Directory where FIT files will be saved (default: fit)",
    )
    parser.add_argument(
        "--include-type",
        action="append",
        help="Additional Garmin activity type keys to treat as cycling",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    email, password = resolve_credentials(args.email, args.password)

    if args.include_type:
        CYCLING_TYPE_KEYS.update(t.lower() for t in args.include_type)

    client = connect(email, password)

    try:
        activities = client.get_activities(0, args.limit)
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Could not fetch activities: {exc}")
        sys.exit(1)

    cycling = [
        activity
        for activity in activities
        if is_cycling_activity(activity) and not is_marked_generated(activity)
    ]
    if not cycling:
        print("No cycling activities found in the requested range.")
        sys.exit(0)

    saved_files = download_activities(client, cycling, Path(args.output_dir))

    print(
        f"\nCompleted: {len(saved_files)}/{len(cycling)} cycling activities saved to {args.output_dir}"
    )


if __name__ == "__main__":
    main()
