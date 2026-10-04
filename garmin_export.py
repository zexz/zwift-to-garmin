#!/usr/bin/env python3
"""Download activity FIT files from Garmin Connect."""

import warnings

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    try:
        from urllib3.exceptions import NotOpenSSLWarning
    except Exception:  # pragma: no cover - urllib3 missing
        class NotOpenSSLWarning(UserWarning):
            """Fallback warning when urllib3 is unavailable."""

warnings.simplefilter("ignore", NotOpenSSLWarning)
warnings.filterwarnings("ignore", category=UserWarning, module=r"urllib3(\..*)?")

import argparse
import calendar
import getpass
import json
import os
import sys
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

from dotenv import load_dotenv

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
)
from garmin_rate_limit import call_with_rate_limit_retry

CYCLING_TYPE_KEYS = {
    "cycling",
    "road_cycling",
    "mountain_biking",
    "indoor_cycling",
    "virtual_ride",
    "gravel_cycling",
    "e_bike_fitness",
}
TOKEN_ACCOUNT_FILENAME = ".garmin-export-account.json"


def normalize_email(email: str) -> str:
    """Normalize an email address for local token-store ownership checks."""
    return email.strip().lower()


def resolve_tokenstore(tokenstore_arg: str = None, email: str = None) -> str:
    """Return an account-scoped session directory unless one is explicitly set."""
    tokenstore = tokenstore_arg or os.getenv("GARMIN_TOKENSTORE") or os.getenv("GARMINTOKENS")
    if tokenstore:
        return str(Path(tokenstore).expanduser())

    if email:
        return str(Path("~/.garth").expanduser() / normalize_email(email))

    tokenstore = "~/.garth"
    return str(Path(tokenstore).expanduser())


def resolve_credentials(
    email_arg: str = None,
    password_arg: str = None,
    *,
    allow_missing: bool = False,
):
    load_dotenv()

    environment_email = os.getenv("GARMIN_EMAIL")
    email = email_arg or environment_email
    if not email and not allow_missing:
        print("Error: Garmin email is required (use --email or GARMIN_EMAIL env var)")
        sys.exit(1)

    can_use_environment_password = not email_arg or email_arg.lower() == (environment_email or "").lower()
    password = password_arg or (
        os.getenv("GARMIN_PASSWORD") if can_use_environment_password else None
    )
    if not password and email and not allow_missing:
        password = getpass.getpass("Garmin password: ")

    return email, password


def tokenstore_matches_email(tokenstore_path: Path, email: str) -> bool:
    """Return whether app-owned metadata binds a session to the requested email."""
    marker_path = tokenstore_path / TOKEN_ACCOUNT_FILENAME
    try:
        stored_email = json.loads(marker_path.read_text(encoding="utf-8")).get("email")
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(stored_email, str) and normalize_email(stored_email) == normalize_email(email)


def save_tokenstore_account(tokenstore_path: Path, email: str) -> None:
    """Record the account that owns a token store without storing credentials."""
    marker_path = tokenstore_path / TOKEN_ACCOUNT_FILENAME
    marker_path.write_text(
        json.dumps({"email": normalize_email(email)}) + "\n",
        encoding="utf-8",
    )
    marker_path.chmod(0o600)


def connect(email: str, password: str, tokenstore: str) -> Garmin:
    tokenstore_path = Path(tokenstore).expanduser()

    try:
        client = Garmin(
            email,
            password,
            prompt_mfa=lambda: input("Garmin MFA code: ").strip(),
        )

        can_resume_session = tokenstore_path.exists()
        if can_resume_session and email and not tokenstore_matches_email(tokenstore_path, email):
            can_resume_session = False
            print(
                "[FIX] Ignoring saved Garmin session: it is not verified for the requested account."
            )

        if can_resume_session:
            try:
                call_with_rate_limit_retry(
                    lambda: client.login(tokenstore=str(tokenstore_path)),
                    action_label="resume Garmin Connect session",
                )
                print(f"[FIX] Resumed Garmin session for {client.display_name} from {tokenstore_path}")
                return client
            except Exception as exc:  # pylint: disable=broad-except
                print(f"Saved Garmin session could not be resumed: {exc}")
                print("Falling back to full login...")

        if not email:
            email = input("Garmin email: ").strip()
        if not password:
            password = getpass.getpass("Garmin password: ")

        client.username = email
        client.password = password
        call_with_rate_limit_retry(client.login, action_label="log in to Garmin Connect")
        tokenstore_path.mkdir(parents=True, exist_ok=True)
        client.client.dump(str(tokenstore_path))
        if email:
            save_tokenstore_account(tokenstore_path, email)
        print(f"[FIX] Logged in as {client.display_name}; saved session to {tokenstore_path}")
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


def months_ago(months: int, now: Optional[datetime] = None) -> datetime:
    """Return the local timestamp at the same day ``months`` months ago."""
    if months < 1:
        raise ValueError("months must be at least 1")

    now = now or datetime.now()
    month_index = now.year * 12 + now.month - 1 - months
    year, month_zero_based = divmod(month_index, 12)
    month = month_zero_based + 1
    day = min(now.day, calendar.monthrange(year, month)[1])
    return now.replace(year=year, month=month, day=day)


def activity_start_time(activity: Dict) -> Optional[datetime]:
    """Read Garmin's local or GMT activity timestamp without timezone conversion."""
    raw_time = (
        activity.get("startTimeLocal")
        or activity.get("startTimeGMT")
        or activity.get("startTime")
    )
    if not raw_time or not isinstance(raw_time, str):
        return None

    normalized = raw_time.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    return parsed.replace(tzinfo=None)


def fetch_activities_since(
    client: Garmin,
    cutoff: datetime,
    page_size: int,
) -> Iterator[Dict]:
    """Yield activities on or after ``cutoff``, fetching Garmin pages as needed."""
    start = 0
    while True:
        activities = activity_items(call_with_rate_limit_retry(
            lambda: client.get_activities(start, page_size),
            action_label=f"fetch activities starting at {start}",
        ))
        if not activities:
            return

        oldest_start: Optional[datetime] = None
        for activity in activities:
            start_time = activity_start_time(activity)
            if start_time is None:
                print(
                    f"Skipping {activity.get('activityId', 'activity without ID')}: "
                    "missing or invalid start time"
                )
                continue

            oldest_start = start_time if oldest_start is None else min(oldest_start, start_time)
            if start_time >= cutoff:
                yield activity

        if len(activities) < page_size or (oldest_start and oldest_start < cutoff):
            return
        start += len(activities)


def activity_items(response) -> List[Dict]:
    """Normalize activity-list responses returned by supported API versions."""
    if isinstance(response, list):
        return response
    if not isinstance(response, dict):
        return []

    activities = response.get("activityList") or response.get("activities") or []
    return activities if isinstance(activities, list) else []


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
            data = call_with_rate_limit_retry(
                lambda: client.download_activity(
                    activity_id, Garmin.ActivityDownloadFormat.ORIGINAL
                ),
                action_label=f"download activity {activity_id}",
            )
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
        description="Download activity FIT files from Garmin Connect.",
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
        "--tokenstore",
        help="Directory where Garmin session tokens are stored (default: ~/.garth)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="How many recent activities to inspect (default: 10)",
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
    parser.add_argument(
        "--all-activities",
        action="store_true",
        help="Export every activity type instead of cycling activities only",
    )
    parser.add_argument(
        "--since-months",
        type=int,
        help="Export activities from the last N calendar months; fetches all result pages",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=100,
        help="Activities to request per Garmin page with --since-months (default: 100)",
    )
    args = parser.parse_args()
    if args.since_months is not None and args.since_months < 1:
        parser.error("--since-months must be at least 1")
    if args.page_size < 1:
        parser.error("--page-size must be at least 1")
    return args


def main():
    args = parse_arguments()
    email, password = resolve_credentials(
        args.email,
        args.password,
        allow_missing=True,
    )
    tokenstore = resolve_tokenstore(args.tokenstore, email)
    tokenstore_exists = Path(tokenstore).exists()

    if not email and not tokenstore_exists:
        print("Error: Garmin email is required (use --email or GARMIN_EMAIL env var)")
        sys.exit(1)
    if email and not password and not tokenstore_exists:
        password = getpass.getpass("Garmin password: ")

    if args.include_type:
        CYCLING_TYPE_KEYS.update(t.lower() for t in args.include_type)

    client = connect(email, password, tokenstore)

    try:
        if args.since_months is not None:
            cutoff = months_ago(args.since_months)
            print(f"Fetching activities since {cutoff:%Y-%m-%d}...")
            activities = list(fetch_activities_since(client, cutoff, args.page_size))
        else:
            activities = activity_items(call_with_rate_limit_retry(
                lambda: client.get_activities(0, args.limit),
                action_label="fetch recent activities",
            ))
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Could not fetch activities: {exc}")
        sys.exit(1)

    selected_activities = [
        activity
        for activity in activities
        if args.all_activities
        or (is_cycling_activity(activity) and not is_marked_generated(activity))
    ]
    if not selected_activities:
        scope = "activities" if args.all_activities else "cycling activities"
        print(f"No {scope} found in the requested range.")
        sys.exit(0)

    saved_files = download_activities(client, selected_activities, Path(args.output_dir))

    print(
        f"\nCompleted: {len(saved_files)}/{len(selected_activities)} activities saved to {args.output_dir}"
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExport cancelled.")
        sys.exit(130)
