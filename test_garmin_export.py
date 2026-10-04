"""Tests for Garmin activity export date-range helpers."""

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from garmin_export import (
    activity_items,
    fetch_activities_since,
    months_ago,
    resolve_credentials,
    save_tokenstore_account,
    tokenstore_matches_email,
)


class FakeGarminClient:
    """Minimal paginated Garmin client used by export tests."""

    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get_activities(self, start, limit):
        self.calls.append((start, limit))
        return self.pages.get(start, [])


class MonthsAgoTests(unittest.TestCase):
    def test_clamps_to_last_day_of_shorter_month(self):
        result = months_ago(1, datetime(2026, 3, 31, 10, 30))

        self.assertEqual(result, datetime(2026, 2, 28, 10, 30))


class FetchActivitiesSinceTests(unittest.TestCase):
    def test_fetches_pages_until_the_cutoff_is_reached(self):
        client = FakeGarminClient(
            {
                0: [
                    {"activityId": 3, "startTimeLocal": "2026-08-15 12:00:00"},
                    {"activityId": 2, "startTimeLocal": "2026-07-15 12:00:00"},
                ],
                2: [
                    {"activityId": 1, "startTimeLocal": "2026-02-01 12:00:00"},
                    {"activityId": 0, "startTimeLocal": "2026-01-31 12:00:00"},
                ],
            }
        )

        activities = list(
            fetch_activities_since(client, datetime(2026, 2, 1), page_size=2)
        )

        self.assertEqual([activity["activityId"] for activity in activities], [3, 2, 1])
        self.assertEqual(client.calls, [(0, 2), (2, 2)])

    def test_accepts_wrapped_activity_list_response(self):
        activities = activity_items({"activityList": [{"activityId": 123}]})

        self.assertEqual(activities, [{"activityId": 123}])


class TokenStoreOwnershipTests(unittest.TestCase):
    def test_matches_only_the_account_recorded_with_the_token_store(self):
        with TemporaryDirectory() as temp_directory:
            tokenstore = Path(temp_directory)
            save_tokenstore_account(tokenstore, "lev.mosco@gmail.com")

            self.assertTrue(tokenstore_matches_email(tokenstore, "LEV.MOSCO@gmail.com"))
            self.assertFalse(tokenstore_matches_email(tokenstore, "dmitri.mosco@gmail.com"))

    def test_does_not_use_environment_password_for_a_different_cli_email(self):
        with patch("garmin_export.load_dotenv"), patch.dict(
            "os.environ",
            {
                "GARMIN_EMAIL": "dmitri.mosco@gmail.com",
                "GARMIN_PASSWORD": "unrelated-password",
            },
            clear=True,
        ):
            email, password = resolve_credentials(
                "lev.mosco@gmail.com", allow_missing=True
            )

        self.assertEqual(email, "lev.mosco@gmail.com")
        self.assertIsNone(password)


if __name__ == "__main__":
    unittest.main()
