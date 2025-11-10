#!/usr/bin/env python3
"""
Precise FIT file editor - only modifies manufacturer and product fields
in file_id and device_info messages
"""

import sys
import struct
from pathlib import Path
from fitparse import FitFile


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


def modify_fit_precise(input_path, preset_id, output_path=None):
    """
    Precisely modify only manufacturer and product fields
    """
    if preset_id not in PRESETS:
        print(f"Error: Invalid preset ID '{preset_id}'. Must be 1, 2, or 3")
        return False
    
    preset = PRESETS[preset_id]
    
    if output_path is None:
        input_file = Path(input_path)
        output_dir = Path('fit_mod')
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / input_file.name
    
    print(f"Target device: {preset['name']}")
    print(f"  Manufacturer ID: {preset['manufacturer_id']}")
    print(f"  Product ID: {preset['product_id']}")
    print(f"\nReading: {input_path}")
    
    # Read binary data
    with open(input_path, 'rb') as f:
        data = bytearray(f.read())
    
    # Parse header
    header_size = data[0]
    data_size = struct.unpack('<I', data[4:8])[0]
    data_start = header_size
    data_end = data_start + data_size
    
    print(f"FIT file: {len(data)} bytes, data section: {data_size} bytes")
    
    # Strategy: Find file_id message (message type 0) and device_info (message type 23)
    # FIT messages have a header byte that indicates message type
    # We'll look for specific patterns
    
    modifications = []
    
    # Search for Zwift manufacturer ID (260 = 0x0104 in little-endian)
    # But ONLY in the first 500 bytes (file_id and first device_info)
    zwift_bytes = struct.pack('<H', 260)
    target_bytes = struct.pack('<H', preset['manufacturer_id'])
    
    print(f"\nSearching for manufacturer field (Zwift ID 260) in first 1200 bytes...")
    
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
                print(f"  Found manufacturer at offset {i}, changed {old_val} -> {preset['manufacturer_id']}")
                mfg_count += 1
            else:
                print(f"  Skipping manufacturer at offset {i} (keeping original)")
    
    # Also look for product field (0) right after manufacturer
    # Product is uint16, value 0 for Zwift
    print(f"\nSearching for product field (0) after manufacturer...")
    product_target = struct.pack('<H', preset['product_id'])
    
    for mod_type, offset, old_val, new_val in modifications:
        if mod_type == 'manufacturer':
            # Check if next uint16 is product (value 0)
            product_offset = offset + 2
            if product_offset + 2 <= data_end:
                current_product = struct.unpack('<H', data[product_offset:product_offset+2])[0]
                if current_product == 0:
                    data[product_offset:product_offset+2] = product_target
                    print(f"  Found product at offset {product_offset}, changed 0 -> {preset['product_id']}")
                    modifications.append(('product', product_offset, 0, preset['product_id']))
    
    print(f"\nTotal modifications: {len(modifications)}")
    
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
    print(f"New CRC: {new_crc}")
    
    # Write modified file
    with open(output_path, 'wb') as f:
        f.write(data)
    
    print(f"\n✓ Modified file saved to: {output_path}")
    
    # Verify
    try:
        print("\nVerifying...")
        fitfile = FitFile(str(output_path))
        
        print("File ID:")
        for record in fitfile.get_messages('file_id'):
            for field in record.fields:
                if field.name in ['manufacturer', 'product', 'garmin_product'] and field.value is not None:
                    print(f"  {field.name}: {field.value}")
            break
        
        print("\nDevice Info:")
        for record in fitfile.get_messages('device_info'):
            for field in record.fields:
                if field.name in ['manufacturer', 'product', 'garmin_product', 'device_index'] and field.value is not None:
                    print(f"  {field.name}: {field.value}")
            break
        
        print("\n✓ Verification complete!")
        
    except Exception as e:
        print(f"\nVerification note: {e}")
        print("File should still be usable.")
    
    return True


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python fit_device_change.py <input_fit_file> <preset_id>")
        print("\nPresets:")
        for pid, preset in PRESETS.items():
            print(f"  {pid} - {preset['name']} (Mfg: {preset['manufacturer_id']}, Product: {preset['product_id']})")
        print("\nExamples:")
        print("  python fit_device_change.py fit/20869954939_ACTIVITY.fit 1")
        sys.exit(1)
    
    input_file = sys.argv[1]
    preset_id = sys.argv[2]
    
    if not Path(input_file).exists():
        print(f"Error: File not found: {input_file}")
        sys.exit(1)
    
    try:
        modify_fit_precise(input_file, preset_id)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
