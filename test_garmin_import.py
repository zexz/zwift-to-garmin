"""Offline checks against the installed Garmin client's public API."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from garminconnect import Garmin
from garmin_import import connect, delete_existing_activity_if_present, rename_activity


class GarminApiTests(unittest.TestCase):
    def setUp(self):
        self.client = Garmin('test@example.com', 'test')
        self.client.client.request = Mock(return_value={})
        self.client.client.put = Mock(return_value={})

    def test_deletes_matching_activity(self):
        with patch('garmin_import.find_activity_by_signature', return_value=123):
            delete_existing_activity_if_present(self.client, (None, 1, 1))
        self.client.client.request.assert_called_once_with(
            'DELETE', 'connectapi',
            f'{self.client.garmin_connect_delete_activity_url}/123', api=True,
        )

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


if __name__ == '__main__':
    unittest.main()
