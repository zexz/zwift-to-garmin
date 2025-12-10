# FIT File Source Changer

Tool for changing data source (manufacturer and product) in FIT files for uploading to Garmin Connect.

## 🚀 Quick Start

### Installation

```bash
pip install fitparse
```

### Usage

**Auto-convert every new file in `fit/` (default preset: Tacx Neo 2 Smart):**
```bash
python fit_autofix.py
```

**Auto-convert using a different preset (e.g., Garmin Edge 520):**
```bash
python fit_autofix.py -p 1
```

**Convert a specific FIT file and save to `fit_mod/`:**
```bash
python fit_autofix.py fit/your_activity.fit -p 2
```

**Change Zwift to Garmin Edge 520:**
```bash
python fit_device_change.py fit/your_activity.fit 1
```

**Change Zwift to Tacx Neo 2 Smart:**
```bash
python fit_device_change.py fit/your_activity.fit 2
```

**Revert back to Zwift:**
```bash
python fit_device_change.py fit/your_activity.fit 3
```

**Check the result:**
```bash
python fit_check.py fit_mod/your_activity.fit
```

## 📋 Device Presets

| ID | Device | Manufacturer ID | Product ID |
|----|--------|-----------------|------------|
| 1  | Garmin Edge 520 | 1 | 2067 |
| 2  | Tacx Neo 2 Smart | 89 | 4266 |
| 3  | Zwift | 260 | 0 |

## 🔧 Scripts

### fit_autofix.py

Automation wrapper that scans the `fit/` directory and converts only the files that are missing in `fit_mod/`.

**Syntax:**
```bash
python fit_autofix.py [<input_fit>] [-p <preset_id>] [--fit-dir DIR] [--fit-mod-dir DIR]
```

**Key features:**
- ✅ Detects new FIT files automatically
- ✅ Uses preset 2 (Tacx Neo 2 Smart) by default
- ✅ Allows manual single-file conversion when a path is provided
- ✅ Prints detailed per-file logs plus a summary of all converted files

**Examples:**
```bash
# Convert every new file in fit/ with the default preset
python fit_autofix.py

# Convert everything using Garmin Edge 520 preset
python fit_autofix.py -p 1

# Convert a single file and force output directory
python fit_autofix.py fit/20937000784_ACTIVITY.fit --fit-mod-dir custom_dir
```

### fit_device_change.py

Main script for precise modification of manufacturer and product fields.

**Syntax:**
```bash
python fit_device_change.py <input_fit_file> <preset_id>
```

**What it does:**
- ✅ Modifies only 2 fields: `manufacturer` and `product`
- ✅ Modifies `file_id` and `device_info` messages
- ✅ Preserves all workout data (session, activity, records)
- ✅ Automatically recalculates CRC
- ✅ Saves file to `fit_mod/` directory
- ✅ File reads without errors

**Examples:**
```bash
# Change to Garmin Edge 520
python fit_device_change.py fit/20937000784_ACTIVITY.fit 1

# Change to Tacx Neo 2 Smart
python fit_device_change.py fit/20869954939_ACTIVITY.fit 2

# Revert to Zwift
python fit_device_change.py fit/20861519609_ACTIVITY.fit 3
```

### fit_check.py

Script for checking and displaying information from FIT file.

**Syntax:**
```bash
python fit_check.py <fit_file>
```

**What it shows:**
- 📄 File ID (manufacturer, product, time_created, type)
- 🔧 Device Information (all devices with details)
- 📊 Session Information (time, distance, calories, power, heart rate)
- 🏃 Activity Information (timestamp, event type)
- 📈 Data Records (number of records)

**Example:**
```bash
python fit_check.py fit_mod/20937000784_ACTIVITY.fit
```

## 📊 Example Output

### Before modification:
```
📄 FILE ID INFORMATION:
  manufacturer        : zwift
  product             : 0

🔧 DEVICE INFORMATION:
  Device #1:
    manufacturer        : zwift
    product             : 0
```

### After modification (Garmin Edge 520):
```
📄 FILE ID INFORMATION:
  manufacturer        : garmin
  garmin_product      : edge520

🔧 DEVICE INFORMATION:
  Device #1:
    manufacturer        : garmin
    garmin_product      : edge520
```

### After modification (Tacx Neo 2 Smart):
```
📄 FILE ID INFORMATION:
  manufacturer        : tacx
  product             : 4266

🔧 DEVICE INFORMATION:
  Device #1:
    manufacturer        : tacx
    product             : 4266
```

## 🎯 How It Works

The script performs precise byte replacement in FIT file:

1. **Find Zwift ID** - locates manufacturer ID (260) in first 1200 bytes
2. **Limit replacement** - replaces only first 2 occurrences (file_id and device_info)
3. **Replace product** - finds product (0) right after manufacturer and replaces it
4. **Recalculate CRC** - automatically recalculates checksum
5. **Save** - saves modified file to `fit_mod/`

**Important:** The script does NOT touch other data in the file, so all workout data is preserved.

## 📁 File Structure

```
garmin-badges/
├── fit/                          # Original FIT files
│   ├── 20861519609_ACTIVITY.fit
│   ├── 20869954939_ACTIVITY.fit
│   └── 20937000784_ACTIVITY.fit
├── fit_mod/                      # Modified FIT files
│   ├── 20861519609_ACTIVITY.fit
│   ├── 20869954939_ACTIVITY.fit
│   └── 20937000784_ACTIVITY.fit
├── fit_autofix.py                # Automatic converter script
├── fit_device_change.py          # Manual modification script
├── fit_check.py                  # Verification script
├── devices.js                    # Device database
├── requirements.txt              # Python dependencies
└── README.md                     # This documentation
```

## ⚙️ Technical Details

### FIT File Format

FIT (Flexible and Interoperable Data Transfer) - binary file format from Garmin:
- Header (12-14 bytes)
- Data section (messages)
- CRC checksum (2 bytes)

### Messages

- **file_id** (message type 0) - file information, usually in first 100 bytes
- **device_info** (message type 23) - device information, usually in first 1000 bytes
- **session** - workout session data
- **activity** - activity information
- **record** - data records (GPS, heart rate, power, etc.)

### Fields

- **manufacturer** - uint16, manufacturer ID (Zwift=260, Garmin=1, Tacx=89)
- **product** - uint16, product ID (Edge 520=2067, Tacx Neo 2=4266)
- **garmin_product** - enum, Garmin product name (displayed instead of product for Garmin)

## ⚠️ Important Notes

### What Works
- ✅ Precise replacement of manufacturer and product
- ✅ Preservation of all workout data
- ✅ Automatic CRC recalculation
- ✅ Files read without errors
- ✅ Ready for upload to Garmin Connect

### Limitations
- ⚠️ Works only with FIT files from Zwift (manufacturer ID 260)
- ⚠️ Replaces only first 2 occurrences of manufacturer ID
- ⚠️ Does not modify other fields (serial_number, software_version, etc.)

### Recommendations
- 📌 Always verify result using `fit_check.py`
- 📌 Keep original files in `fit/` directory
- 📌 Modified files are saved to `fit_mod/`
- 📌 For professional editing use specialized tools

## 🛠️ Alternative Tools

For more complex tasks we recommend:
- **FitFileTools** - https://www.fitfiletools.com/
- **Golden Cheetah** - https://www.goldencheetah.org/
- **Garmin FIT SDK** - https://developer.garmin.com/fit/

## 📝 Requirements

- Python 3.6+
- fitparse >= 1.2.0

## 🐛 Troubleshooting

### Error: "Invalid struct format"
This is a warning from fitparse, not a critical error. The file still works.

### Error: "No such dev_data_index"
This is a warning about unknown fields, does not affect file functionality.

### File won't upload to Garmin Connect
- Check that file reads without critical errors
- Ensure all workout data is preserved
- Try a different device preset

## 📄 License

MIT License - use freely for personal purposes.

## 🤝 Contributing

If you found a bug or want to add a new device to presets, create an issue or pull request.

---

**Version:** 2.0  
**Date:** 2025-11-10  
**Author:** FIT Tools Team
