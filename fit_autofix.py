#!/usr/bin/env python3
"""
Automatic FIT file updater.

- Watches the `fit/` directory for new FIT files
- Converts anything not yet present in `fit/mod/`
- Moves processed originals into `fit/original/`
- Defaults to Tacx Neo 2 Smart preset (ID 2)
- Still supports manual single-file conversion
"""

import warnings

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    try:
        from urllib3.exceptions import NotOpenSSLWarning
    except Exception:  # pragma: no cover - urllib3 missing
        class NotOpenSSLWarning(UserWarning):
            """Fallback when urllib3 isn't available."""

warnings.simplefilter("ignore", NotOpenSSLWarning)
warnings.filterwarnings("ignore", category=UserWarning, module=r"urllib3(\..*)?")

import argparse
import struct
import sys
from pathlib import Path

from fitparse import FitFile


FIT_ROOT = Path("fit")
FIT_MOD_DIR = FIT_ROOT / "mod"
FIT_ORIGINAL_DIR = FIT_ROOT / "original"


def verbose_print(message: str, verbose: bool = False):
    if verbose:
        print(message)


warnings.simplefilter("ignore", NotOpenSSLWarning)


# Device presets
PRESETS = {
    '1': {
        'name': 'Garmin Edge 520',
        'manufacturer_id': 1,
        'product_id': 2067,
    },
    '2': {
        'name': 'Tacx Neo 2 Smart',
        'manufacturer_id': 89,
        'product_id': 4266,
    },
    '3': {
        'name': 'Zwift',
        'manufacturer_id': 260,
        'product_id': 0,
    }
}


def find_field_offset(data, message_name, field_name, start_offset=0):
    """
    Find the byte offset of a specific field in a FIT message
    Returns list of (offset, current_value) tuples
    """
    offsets = []
    
    # Parse FIT file to find message definitions and data
    try:
        from io import BytesIO
        fitfile = FitFile(BytesIO(data))
        
        # Track current position in file
        # This is approximate - we'll search around the expected area
        for record in fitfile.get_messages(message_name):
            for field in record.fields:
                if field.name == field_name:
                    # We found the field, now need to find its location in binary data
                    # This is tricky - we'll use the value to search
                    if isinstance(field.value, int):
                        offsets.append((None, field.value))
                    elif isinstance(field.value, str):
                        # String values need special handling
                        offsets.append((None, field.value))
    except:
        pass
    
    return offsets


def move_original_file(source_path: Path, destination_dir: Path, *, verbose: bool = False):
    if not source_path.exists():
        return
    if source_path.parent.resolve() != FIT_ROOT.resolve():
        return
    try:
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / source_path.name
        if destination.exists():
            destination.unlink()
        source_path.replace(destination)
        verbose_print(f"  ↪ Archived original to {destination}", verbose)
    except Exception as exc:  # pylint: disable=broad-except
        print(f"  ⚠ Could not archive {source_path.name}: {exc}")


def modify_fit_precise(input_path, preset_id, output_path=None, *, verbose: bool = False):
    """
    Precisely modify only manufacturer and product fields
    """
    if preset_id not in PRESETS:
        print(f"Error: Invalid preset ID '{preset_id}'. Must be 1, 2, or 3")
        return False
    
    preset = PRESETS[preset_id]
    
    if output_path is None:
        input_file = Path(input_path)
        output_dir = FIT_MOD_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / input_file.name
    
    verbose_print(f"Target device: {preset['name']}", verbose)
    verbose_print(f"  Manufacturer ID: {preset['manufacturer_id']}", verbose)
    verbose_print(f"  Product ID: {preset['product_id']}", verbose)
    verbose_print(f"\nReading: {input_path}", verbose)
    
    # Read binary data
    with open(input_path, 'rb') as f:
        data = bytearray(f.read())
    
    # Parse header
    header_size = data[0]
    data_size = struct.unpack('<I', data[4:8])[0]
    data_start = header_size
    data_end = data_start + data_size
    
    verbose_print(f"FIT file: {len(data)} bytes, data section: {data_size} bytes", verbose)
    
    # Strategy: Find file_id message (message type 0) and device_info (message type 23)
    # FIT messages have a header byte that indicates message type
    # We'll look for specific patterns
    
    modifications = []
    
    # Search for Zwift manufacturer ID (260 = 0x0104 in little-endian)
    # But ONLY in the first 500 bytes (file_id and first device_info)
    zwift_bytes = struct.pack('<H', 260)
    target_bytes = struct.pack('<H', preset['manufacturer_id'])
    
    verbose_print(
        "\nSearching for manufacturer field (Zwift ID 260) in first 1200 bytes...",
        verbose,
    )
    
    # File_id message is typically in first 100 bytes
    # Device_info message is around 800-900 bytes
    # We only want to replace the FIRST TWO occurrences (file_id and first device_info)
    mfg_count = 0
    for i in range(data_start, min(data_start + 1200, data_end - 1)):
        if data[i:i+2] == zwift_bytes:
            # Only replace first 2 occurrences
            if mfg_count < 2:
                old_val = struct.unpack('<H', data[i:i+2])[0]
                data[i:i+2] = target_bytes
                modifications.append(('manufacturer', i, old_val, preset['manufacturer_id']))
                verbose_print(
                    f"  Found manufacturer at offset {i}, changed {old_val} -> {preset['manufacturer_id']}",
                    verbose,
                )
                mfg_count += 1
            else:
                verbose_print(f"  Skipping manufacturer at offset {i} (keeping original)", verbose)
    
    # Also look for product field (0) right after manufacturer
    # Product is uint16, value 0 for Zwift
    verbose_print("\nSearching for product field (0) after manufacturer...", verbose)
    product_target = struct.pack('<H', preset['product_id'])
    
    for mod_type, offset, old_val, new_val in modifications:
        if mod_type == 'manufacturer':
            # Check if next uint16 is product (value 0)
            product_offset = offset + 2
            if product_offset + 2 <= data_end:
                current_product = struct.unpack('<H', data[product_offset:product_offset+2])[0]
                if current_product == 0:
                    data[product_offset:product_offset+2] = product_target
                    verbose_print(
                        f"  Found product at offset {product_offset}, changed 0 -> {preset['product_id']}",
                        verbose,
                    )
                    modifications.append(('product', product_offset, 0, preset['product_id']))
    
    verbose_print(f"\nTotal modifications: {len(modifications)}", verbose)
    
    # Recalculate CRC
    def calculate_crc(data, start, end):
        crc_table = [
            0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
            0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400
        ]
        crc = 0
        for byte in data[start:end]:
            tmp = crc_table[crc & 0xF]
            crc = (crc >> 4) & 0x0FFF
            crc = crc ^ tmp ^ crc_table[byte & 0xF]
            tmp = crc_table[crc & 0xF]
            crc = (crc >> 4) & 0x0FFF
            crc = crc ^ tmp ^ crc_table[(byte >> 4) & 0xF]
        return crc
    
    new_crc = calculate_crc(data, 0, data_end)
    data[data_end:data_end+2] = struct.pack('<H', new_crc)
    verbose_print(f"New CRC: {new_crc}", verbose)
    
    # Write modified file
    with open(output_path, 'wb') as f:
        f.write(data)
    
    verbose_print(f"\n✓ Modified file saved to: {output_path}", verbose)
    
    # Verify
    try:
        verbose_print("\nVerifying...", verbose)
        fitfile = FitFile(str(output_path))
        
        verbose_print("File ID:", verbose)
        for record in fitfile.get_messages('file_id'):
            for field in record.fields:
                if field.name in ['manufacturer', 'product', 'garmin_product'] and field.value is not None:
                    verbose_print(f"  {field.name}: {field.value}", verbose)
            break
        
        verbose_print("\nDevice Info:", verbose)
        for record in fitfile.get_messages('device_info'):
            for field in record.fields:
                if field.name in ['manufacturer', 'product', 'garmin_product', 'device_index'] and field.value is not None:
                    verbose_print(f"  {field.name}: {field.value}", verbose)
            break
        
        verbose_print("\n✓ Verification complete!", verbose)
    
    except Exception as e:
        print(f"\nVerification note: {e}")
        print("File should still be usable.")
    
    move_original_file(Path(input_path), FIT_ORIGINAL_DIR, verbose=verbose)
    return True


def find_new_fit_files(input_dir=None, output_dir=None):
    """
    Compare exported (`fit/`) and modified (`fit/mod/`) directories to find pending files.
    """
    input_dir = Path(input_dir or FIT_ROOT)
    output_dir = Path(output_dir or FIT_MOD_DIR)
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    candidates = sorted(
        [
            file_path
            for file_path in input_dir.iterdir()
            if file_path.is_file() and file_path.suffix.lower() == '.fit'
        ]
    )
    return [
        file_path for file_path in candidates if not (output_dir / file_path.name).exists()
    ]


def autofix_new_files(preset_id='2', input_dir=None, output_dir=None, *, verbose: bool = False):
    """
    Automatically convert every FIT file in input_dir that is missing in output_dir.
    """
    input_dir = Path(input_dir or FIT_ROOT)
    output_dir = Path(output_dir or FIT_MOD_DIR)

    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    new_files = find_new_fit_files(input_dir, output_dir)

    if not new_files:
        print("No new FIT files detected. Everything is up to date ✅")
        return True

    if verbose:
        print(f"Found {len(new_files)} new file(s) to convert:")
        for file in new_files:
            print(f"  • {file.name}")
    else:
        print(f"Found {len(new_files)} new file(s) to convert.")

    all_successful = True
    converted_files = []
    for fit_file in new_files:
        target_path = output_dir / fit_file.name
        if verbose:
            print(f"\nProcessing {fit_file.name} ...")
        else:
            print(f"{fit_file.name} → {target_path}", end=" ")
        try:
            success = modify_fit_precise(
                fit_file,
                preset_id,
                target_path,
                verbose=verbose,
            )
        except Exception as exc:
            if verbose:
                print(f"✗ Failed to convert {fit_file.name}: {exc}")
            else:
                print(f"✗ {exc}")
            success = False
        else:
            if success:
                converted_files.append(fit_file.name)
                if verbose:
                    print(f"✓ Completed {fit_file.name}")
                else:
                    print("✓")
        all_successful = all_successful and success

    print(
        f"\nSummary: {len(converted_files)}/{len(new_files)} file(s) converted successfully."
    )
    if len(converted_files) < len(new_files):
        failed = sorted(set(file.name for file in new_files) - set(converted_files))
        print("  ⚠ Failed to convert:")
        for fname in failed:
            print(f"    - {fname}")

    if all_successful:
        print("✓ All conversions succeeded.")
    else:
        print("⚠ Some files failed. See messages above.")

    return all_successful


def main():
    parser = argparse.ArgumentParser(
        description="Automatically convert new FIT files using preset device profiles."
    )
    parser.add_argument(
        'input_fit',
        nargs='?',
        help="Optional direct path to a FIT file. If omitted, the script scans the fit directory.",
    )
    parser.add_argument(
        '-p',
        '--preset',
        default='2',
        choices=list(PRESETS.keys()),
        help="Preset ID to use (default: 2 - Tacx Neo 2 Smart).",
    )
    parser.add_argument(
        '--fit-dir',
        default='fit',
        help="Directory with original FIT files (default: fit).",
    )
    parser.add_argument(
        '--fit-mod-dir',
        default=FIT_MOD_DIR,
        help="Directory where converted FIT files are stored (default: fit/mod).",
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help="Show detailed per-file diagnostics.",
    )
    args = parser.parse_args()

    if args.input_fit:
        input_file = Path(args.input_fit)
        if not input_file.exists():
            print(f"Error: File not found: {input_file}")
            sys.exit(1)

        try:
            success = modify_fit_precise(
                input_file,
                args.preset,
                Path(args.fit_mod_dir) / input_file.name,
                verbose=args.verbose,
            )
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
            success = False
    else:
        success = autofix_new_files(
            args.preset,
            args.fit_dir,
            args.fit_mod_dir,
            verbose=args.verbose,
        )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()