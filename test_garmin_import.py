"""Offline checks against the installed Garmin client's public API."""
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from garminconnect import Garmin
from garmin_import import (
    connect,
    extract_activity_id,
    find_activity_by_signature,
    find_pending_files,
    is_permanent_upload_rejection,
    mark_failed_upload,
    log_upload_response,
    delete_existing_activity_if_present,
    rename_activity,
)


class GarminApiTests(unittest.TestCase):
    def setUp(self):
        self.client = Garmin('test@example.com', 'test')
        self.client.client.request = Mock(return_value={})
        self.client.client.put = Mock(return_value={})

    def test_deletes_matching_activity(self):
        with patch('garmin_import.find_activity_by_signature', return_value=123):
            deleted_id = delete_existing_activity_if_present(self.client, (None, 1, 1))
        self.client.client.request.assert_called_once_with(
            'DELETE', 'connectapi',
            f'{self.client.garmin_connect_delete_activity_url}/123', api=True,
        )
        self.assertEqual(deleted_id, 123)

    def test_ignores_deleted_activity_while_finding_reuploaded_activity(self):
        self.client.get_activities = Mock(return_value=[
            {'activityId': 123, 'startTimeGMT': '2026-10-03 14:24:15'},
            {'activityId': 456, 'startTimeGMT': '2026-10-03 14:24:15'},
        ])

        activity_id = find_activity_by_signature(
            self.client,
            (datetime(2026, 10, 3, 14, 24, 15), None, None),
            excluded_activity_ids={123},
        )

        self.assertEqual(activity_id, 456)

    def test_does_not_match_another_ride_by_distance_when_start_time_exists(self):
        self.client.get_activities = Mock(return_value=[
            {
                'activityId': 123,
                'startTimeGMT': '2026-10-03 14:24:15',
                'distance': 1000,
                'duration': 60,
            },
        ])

        activity_id = find_activity_by_signature(
            self.client,
            (datetime(2026, 10, 4, 14, 24, 15), 60, 1000),
        )

        self.assertIsNone(activity_id)

    def test_extracts_activity_id_from_garmin_client_dictionary_response(self):
        response = {
            'detailedImportResult': {
                'successes': [{'activityId': '456'}],
            },
        }

        self.assertEqual(extract_activity_id(response), 456)

    def test_logs_garmin_client_dictionary_response(self):
        response = {'detailedImportResult': {'successes': [{'activityId': 456}]}}
        log_upload_response(response)

    def test_renames_activity(self):
        self.client.connectapi = Mock(return_value={'activityName': 'old'})
        self.assertTrue(rename_activity(self.client, 123, '[G] Ride'))
        self.client.client.put.assert_called_once_with(
            'connectapi', f'{self.client.garmin_connect_activity}/123',
            json={'activityId': '123', 'activityName': '[G] Ride'}, api=True,
        )

    def test_fresh_login_saves_session(self):
        self.client.login = Mock()
        self.client.client.dump = Mock()
        with TemporaryDirectory() as directory:
            tokenstore = str(Path(directory) / 'tokens')
            with patch('garmin_import.Garmin', return_value=self.client):
                self.assertIs(connect('test@example.com', 'test', tokenstore), self.client)
            self.client.login.assert_called_once_with()
            self.client.client.dump.assert_called_once_with(tokenstore)

    def test_marks_api_400_rejection_in_failed_directory(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'ride.fit'
            failed_dir = root / 'failed'
            source.write_bytes(b'FIT')

            mark_failed_upload(
                source,
                failed_dir,
                Exception('API Error 400 - file data could not be processed'),
                keep_source=False,
            )

            self.assertFalse(source.exists())
            self.assertEqual((failed_dir / 'ride.fit').read_bytes(), b'FIT')
            self.assertIn('API Error 400', (failed_dir / 'ride.fit.error.txt').read_text())

    def test_keeps_marked_files_out_of_pending_queue(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir = root / 'mod'
            uploaded_dir = root / 'uploaded'
            failed_dir = root / 'failed'
            input_dir.mkdir()
            failed_dir.mkdir()
            (input_dir / 'rejected.fit').write_bytes(b'FIT')
            (failed_dir / 'rejected.fit').write_bytes(b'FIT')
            (input_dir / 'ready.fit').write_bytes(b'FIT')

            pending = find_pending_files(input_dir, uploaded_dir, failed_dir)

            self.assertEqual([path.name for path in pending], ['ready.fit'])

    def test_detects_only_garmin_permanent_rejections(self):
        self.assertTrue(is_permanent_upload_rejection(Exception('API Error 400 - rejected')))
        self.assertTrue(is_permanent_upload_rejection(Exception('HTTP 400 Bad Request')))
        self.assertFalse(is_permanent_upload_rejection(Exception('HTTP 503 unavailable')))


if __name__ == '__main__':
    unittest.main()
