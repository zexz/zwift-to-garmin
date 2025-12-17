#!/usr/bin/env python3
"""Upload modified FIT files from fit/mod/ to Garmin Connect."""

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
import getpass
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from dotenv import load_dotenv
from fitparse import FitFile
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectInvalidFileFormatError,
)


FIT_ROOT = Path("fit")
FIT_MOD_DIR = FIT_ROOT / "mod"
FIT_UPLOADED_DIR = FIT_ROOT / "uploaded"


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


def find_pending_files(input_dir: Path, uploaded_dir: Path) -> List[Path]:
    input_dir.mkdir(parents=True, exist_ok=True)
    uploaded_dir.mkdir(parents=True, exist_ok=True)

    uploaded_names = {path.name for path in uploaded_dir.glob("*.fit")}
    candidates = sorted(
        path for path in input_dir.glob("*.fit") if path.name not in uploaded_names
    )
    return candidates


def upload_files(
    client: Garmin,
    files: Iterable[Path],
    uploaded_dir: Path,
    keep_source: bool = False,
    rename_attempts: int = 3,
    rename_delay: float = 3.0,
    verbose: bool = False,
) -> int:
    uploaded_count = 0
    uploaded_dir.mkdir(parents=True, exist_ok=True)

    for fit_path in files:
        print(f"Uploading {fit_path.name} ...", end=" ")
        signature = extract_activity_signature(fit_path)
        if signature:
            delete_existing_activity_if_present(
                client, signature, verbose=verbose
            )
        try:
            response = client.upload_activity(str(fit_path))
        except GarminConnectInvalidFileFormatError as exc:
            print(f"✗ invalid file: {exc}")
            continue
        except Exception as exc:  # pylint: disable=broad-except
            print(f"✗ failed: {exc}")
            continue

        if verbose:
            log_upload_response(response)

        activity_id = extract_activity_id(response)
        title = format_activity_title(derive_title_from_filename(fit_path))
        renamed = False

        for attempt in range(1, rename_attempts + 1):
            current_id = activity_id
            if not current_id:
                current_id = find_activity_by_signature(client, signature, verbose=verbose)
            if not current_id:
                if attempt == 1:
                    print(
                        "\n  ⚠ Could not determine activity ID from upload response; "
                        "will retry rename after short delay."
                    )
                if attempt < rename_attempts:
                    time.sleep(rename_delay)
                continue

            renamed = rename_activity(client, current_id, title, verbose=verbose)
            if renamed:
                break

            if verbose:
                print(f"\n  ⚠ Rename attempt {attempt} failed; retrying...")
            if attempt < rename_attempts:
                time.sleep(rename_delay)

        destination = uploaded_dir / fit_path.name
        if keep_source:
            destination.write_bytes(fit_path.read_bytes())
        else:
            fit_path.replace(destination)
        uploaded_count += 1
        if renamed:
            print(f"✓ uploaded (renamed to \"{title}\")")
        else:
            print("✓ uploaded (kept Garmin default title)")

    return uploaded_count


def derive_title_from_filename(path: Path) -> str:
    stem = path.stem
    tokens = [token for token in stem.split('_') if token]

    def is_noise(token: str) -> bool:
        token = token.strip()
        if not token:
            return True
        if token.isdigit():
            return True
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:\s+\d{2}-\d{2}-\d{2})?", token):
            return True
        return False

    while tokens and is_noise(tokens[0]):
        tokens.pop(0)

    cleaned_tokens = [tok.strip() for tok in tokens if tok.strip() and tok.strip() != "-"]
    cleaned = " ".join(cleaned_tokens)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or "Activity"


def format_activity_title(base_title: str) -> str:
    base_title = base_title.strip()
    if not base_title:
        return "[G] Activity"

    if " " in base_title:
        first, rest = base_title.split(" ", 1)
        rest = rest.strip()
        if rest:
            return f"[G] {first} - {rest}"
    return f"[G] {base_title}"


def extract_activity_id(response) -> Optional[int]:
    try:
        payload = response.json()
    except Exception:  # pylint: disable=broad-except
        return None

    detail = payload.get("detailedImportResult") or payload
    successes = detail.get("successes") or []
    for success in successes:
        for key in ("activityId", "internalId", "parentSummaryId"):
            value = success.get(key)
            if isinstance(value, int):
                return value
            # Some responses return str
            if isinstance(value, str) and value.isdigit():
                return int(value)
    return None


def log_upload_response(response):
    print("\n  ℹ Upload response payload:")
    try:
        payload = response.json()
    except Exception as exc:  # pylint: disable=broad-except
        print(f"    (failed to decode JSON: {exc})")
        print(f"    Raw text: {response.text[:500]}")
        return

    import json  # local import to avoid top-level dependency

    print("    " + json.dumps(payload, indent=2)[:2000])


def extract_activity_signature(path: Path) -> Optional[Tuple[Optional[datetime], Optional[float], Optional[float]]]:
    try:
        fitfile = FitFile(str(path))
    except Exception:
        return None

    start_time = None
    elapsed = None
    distance = None

    try:
        for record in fitfile.get_messages("session"):
            for field in record:
                if field.value is None:
                    continue
                if field.name == "start_time":
                    start_time = field.value
                elif field.name == "total_elapsed_time":
                    elapsed = float(field.value)
                elif field.name == "total_distance":
                    distance = float(field.value)
            break
    except Exception:
        return None

    return (start_time, elapsed, distance)


def find_activity_by_signature(
    client: Garmin,
    signature: Optional[Tuple[Optional[datetime], Optional[float], Optional[float]]],
    *,
    verbose: bool = False,
    purpose: str = "rename",
) -> Optional[int]:
    if not signature:
        return None

    start_time, elapsed, distance = signature
    try:
        activities = client.get_activities(0, 20)
    except Exception as exc:  # pylint: disable=broad-except
        print(f"\n  ⚠ Could not fetch recent activities for rename: {exc}")
        return None

    if verbose:
        print(
            f"\n  ℹ Signature: start_time={start_time}, elapsed={elapsed}, distance={distance}"
        )

    for activity in activities:
        activity_id = activity.get("activityId")
        if not activity_id:
            continue

        if start_time:
            start_match = compare_times(start_time, activity)
        else:
            start_match = False

        distance_match = compare_numeric(distance, activity.get("distance"), tolerance=200)
        duration_match = compare_numeric(
            elapsed, activity.get("duration"), tolerance=30
        )

        if start_match or (distance_match and duration_match):
            print(
                f"\n  ℹ Matched activity for {purpose} by "
                f"{'start time' if start_match else 'distance/duration'}: {activity_id}"
            )
            return activity_id

    if verbose:
        print("\n  ℹ No matching activity found among recent uploads.")

    return None


def delete_existing_activity_if_present(
    client: Garmin,
    signature: Optional[Tuple[Optional[datetime], Optional[float], Optional[float]]],
    *,
    verbose: bool = False,
) -> None:
    if not signature:
        return

    existing_id = find_activity_by_signature(
        client, signature, verbose=verbose, purpose="delete"
    )
    if not existing_id:
        return

    path = f"{client.garmin_connect_activity}/{existing_id}"
    if verbose:
        print(f"\n  ℹ Deleting existing activity {existing_id} before re-upload")
    try:
        client.garth.request(
            "DELETE",
            "connectapi",
            path,
            api=True,
        )
        print(f"\n  ℹ Removed prior activity {existing_id} to keep upload atomic.")
    except Exception as exc:  # pylint: disable=broad-except
        print(f"\n  ⚠ Failed to delete existing activity {existing_id}: {exc}")


def compare_times(source_time: datetime, activity: dict) -> bool:
    target_time = (
        activity.get("startTimeGMT")
        or activity.get("startTimeLocal")
        or activity.get("startTime")
    )
    if not target_time:
        return False

    parsed_target = parse_garmin_time(target_time)
    if not parsed_target:
        return False

    delta = abs((parsed_target - source_time).total_seconds())
    return delta <= 10


def parse_garmin_time(value: str) -> Optional[datetime]:
    value = value.replace("Z", "").replace("T", " ")
    formats = [
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def compare_numeric(source: Optional[float], target: Optional[float], tolerance: float) -> bool:
    if source is None or target is None:
        return False
    try:
        target_val = float(target)
    except (TypeError, ValueError):
        return False
    return abs(target_val - source) <= tolerance


def rename_activity(
    client: Garmin,
    activity_id: int,
    name: str,
    *,
    verbose: bool = False,
) -> bool:
    name = name[:100]
    path = f"{client.garmin_connect_activity}/{activity_id}"

    try:
        activity = client.connectapi(path)
    except Exception as exc:  # pylint: disable=broad-except
        print(f"\n  ⚠ Failed to fetch activity {activity_id}: {exc}")
        return False

    if not isinstance(activity, dict):
        print(f"\n  ⚠ Unexpected activity payload for {activity_id}, skipping rename.")
        if verbose:
            print(f"    Payload type: {type(activity)} value: {activity}")
        return False

    if activity.get("activityName") == name:
        if verbose:
            print(f"\n  ℹ Activity {activity_id} already named \"{name}\".")
        return True

    payload = {"activityName": name}

    if verbose:
        print(f"\n  ℹ Renaming activity {activity_id} to \"{name}\"")

    try:
        client.garth.request(
            "PUT",
            "connectapi",
            path,
            api=True,
            json=payload,
        )
        if verbose:
            print(f"  ✓ Rename request accepted for {activity_id}")
        return True
    except Exception as exc:  # pylint: disable=broad-except
        print(f"\n  ⚠ Failed to rename activity {activity_id}: {exc}")
        return False


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Upload FIT files from fit_mod/ to Garmin Connect.",
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
        "--input-dir",
        default=FIT_MOD_DIR,
        help="Directory with modified FIT files (default: fit/mod)",
    )
    parser.add_argument(
        "--uploaded-dir",
        default=FIT_UPLOADED_DIR,
        help="Directory where successfully uploaded files are moved (default: fit/uploaded)",
    )
    parser.add_argument(
        "--keep-source",
        action="store_true",
        help="Keep a copy in input-dir instead of moving to uploaded-dir",
    )
    parser.add_argument(
        "--rename-attempts",
        type=int,
        default=3,
        help="How many times to try locating/renaming the uploaded activity (default: 3)",
    )
    parser.add_argument(
        "--rename-delay",
        type=float,
        default=3.0,
        help="Delay in seconds between rename attempts (default: 3.0)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed debug information (upload responses, matching diagnostics)",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()
    email, password = resolve_credentials(args.email, args.password)
    client = connect(email, password)

    input_dir = Path(args.input_dir)
    uploaded_dir = Path(args.uploaded_dir)
    files = find_pending_files(input_dir, uploaded_dir)

    if not files:
        print("No pending FIT files to upload. ✅")
        return

    print(f"Found {len(files)} file(s) ready for upload:")
    for path in files:
        print(f"  • {path.name}")

    uploaded_count = upload_files(
        client,
        files,
        uploaded_dir,
        keep_source=args.keep_source,
        rename_attempts=max(1, args.rename_attempts),
        rename_delay=max(0.5, args.rename_delay),
        verbose=args.verbose,
    )

    print(
        f"\nCompleted: {uploaded_count}/{len(files)} files uploaded. "
        f"Moved to {uploaded_dir}"
    )


if __name__ == "__main__":
    main()
