import unittest

from fit_autofix import PRESETS, device_profiles


class Field:
    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.raw_value = value


class Record:
    def __init__(self, fields):
        self.fields = fields


class FakeFitFile:
    def __init__(self, messages):
        self.messages = messages

    def get_messages(self, name):
        return self.messages.get(name, [])


class DeviceProfilesTest(unittest.TestCase):
    def test_reads_only_decoded_device_metadata(self):
        fitfile = FakeFitFile(
            {
                "file_id": [
                    Record([Field("manufacturer", 89), Field("product", 4266)])
                ],
                "device_info": [
                    Record([Field("manufacturer", 89), Field("product", 4266)])
                ],
            }
        )

        self.assertEqual(device_profiles(fitfile), [(89, 4266), (89, 4266)])
        self.assertEqual(device_profiles(fitfile)[0], (
            PRESETS["2"]["manufacturer_id"],
            PRESETS["2"]["product_id"],
        ))
