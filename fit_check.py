#!/usr/bin/env python3
"""
Script to read FIT file and display available device information
"""

import sys
from fitparse import FitFile
from pathlib import Path


def check_fit_file(fit_path):
    """
    Read and display information from a FIT file
    
    Args:
        fit_path: Path to FIT file
    """
    if not Path(fit_path).exists():
        print(f"Error: File not found: {fit_path}")
        return False
    
    print(f"Reading FIT file: {fit_path}")
    print("=" * 80)
    
    try:
        fitfile = FitFile(fit_path)
        
        # Display file_id message
        print("\n📄 FILE ID INFORMATION:")
        print("-" * 80)
        try:
            for record in fitfile.get_messages('file_id'):
                for field in record.fields:
                    if field.value is not None:
                        print(f"  {field.name:20s}: {field.value}")
        except Exception as e:
            print(f"  Error reading file_id: {e}")
        
        # Display device_info messages
        print("\n🔧 DEVICE INFORMATION:")
        print("-" * 80)
        device_count = 0
        try:
            for record in fitfile.get_messages('device_info'):
                device_count += 1
                print(f"\n  Device #{device_count}:")
                for field in record.fields:
                    if field.value is not None:
                        print(f"    {field.name:20s}: {field.value}")
        except Exception as e:
            print(f"  Error reading device_info: {e}")
        
        if device_count == 0:
            print("  No device_info messages found")
        
        # Display session information
        print("\n📊 SESSION INFORMATION:")
        print("-" * 80)
        session_count = 0
        try:
            for record in fitfile.get_messages('session'):
                session_count += 1
                # Display only key fields
                key_fields = ['sport', 'sub_sport', 'total_distance', 'total_elapsed_time', 
                             'total_timer_time', 'avg_speed', 'max_speed', 'avg_heart_rate', 
                             'max_heart_rate', 'avg_cadence', 'max_cadence', 'avg_power', 
                             'max_power', 'total_calories']
                
                for field in record.fields:
                    if field.name in key_fields and field.value is not None:
                        print(f"  {field.name:20s}: {field.value}")
                break  # Only show first session
        except Exception as e:
            print(f"  Error reading session: {e}")
        
        if session_count == 0:
            print("  No session messages found")
        
        # Display activity information
        print("\n🏃 ACTIVITY INFORMATION:")
        print("-" * 80)
        try:
            for record in fitfile.get_messages('activity'):
                for field in record.fields:
                    if field.value is not None:
                        print(f"  {field.name:20s}: {field.value}")
        except Exception as e:
            print(f"  Error reading activity: {e}")
        
        # Display record count
        print("\n📈 DATA RECORDS:")
        print("-" * 80)
        try:
            record_count = sum(1 for _ in fitfile.get_messages('record'))
            print(f"  Total data records: {record_count}")
        except Exception as e:
            print(f"  Error counting records: {e}")
        
        print("\n" + "=" * 80)
        print("✓ File read completed (some sections may have errors)")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error reading FIT file: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fit_check.py <fit_file>")
        print("\nExample:")
        print("  python fit_check.py fit/20861519609_ACTIVITY.fit")
        print("  python fit_check.py fit_mod/20861519609_ACTIVITY.fit")
        sys.exit(1)
    
    fit_file = sys.argv[1]
    
    success = check_fit_file(fit_file)
    sys.exit(0 if success else 1)
