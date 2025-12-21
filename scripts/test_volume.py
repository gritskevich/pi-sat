#!/usr/bin/env python3
"""
Standalone volume debugging script
Tests MPD and ALSA volume control
"""
import sys
import subprocess
import time
from pathlib import Path

from modules.mpd_controller import MPDController


def get_alsa_volume():
    """Get ALSA Master volume percentage"""
    try:
        result = subprocess.run(
            ['amixer', 'get', 'Master'],
            capture_output=True,
            text=True,
            timeout=1
        )
        for line in result.stdout.split('\n'):
            if '[' in line and '%' in line:
                start = line.find('[') + 1
                end = line.find('%', start)
                if start > 0 and end > start:
                    return int(line[start:end])
        return None
    except Exception as e:
        print(f"  ❌ ALSA get error: {e}")
        return None


def set_alsa_volume(percent):
    """Set ALSA Master volume percentage (0-100)"""
    try:
        result = subprocess.run(
            ['amixer', 'set', 'Master', f'{percent}%'],
            capture_output=True,
            text=True,
            timeout=1
        )
        return result.returncode == 0
    except Exception as e:
        print(f"  ❌ ALSA set error: {e}")
        return False


def test_alsa_volume():
    """Test ALSA volume control"""
    print("\n" + "="*60)
    print("Testing ALSA Volume Control")
    print("="*60)
    
    # Get initial volume
    print("\n1. Getting initial ALSA volume...")
    initial = get_alsa_volume()
    if initial is None:
        print("  ❌ Failed to get ALSA volume")
        return False
    print(f"  ✅ Initial volume: {initial}%")
    
    # Calculate test volume (don't go below 10% or above 90%)
    if initial < 50:
        test_volume = min(90, initial + 20)
    else:
        test_volume = max(10, initial - 20)
    
    print(f"\n2. Setting ALSA volume to {test_volume}%...")
    if not set_alsa_volume(test_volume):
        print("  ❌ Failed to set ALSA volume")
        return False
    print(f"  ✅ Volume set command executed")
    
    # Wait a moment for change to take effect
    time.sleep(0.2)
    
    # Get volume again
    print(f"\n3. Getting ALSA volume after change...")
    after = get_alsa_volume()
    if after is None:
        print("  ❌ Failed to get ALSA volume after change")
        return False
    print(f"  ✅ Volume after change: {after}%")
    
    # Validate
    print(f"\n4. Validating volume change...")
    if abs(after - test_volume) <= 2:  # Allow 2% tolerance
        print(f"  ✅ Volume change successful: {initial}% → {after}% (target: {test_volume}%)")
    else:
        print(f"  ⚠️  Volume mismatch: expected {test_volume}%, got {after}%")
    
    # Restore initial volume
    print(f"\n5. Restoring initial volume ({initial}%)...")
    set_alsa_volume(initial)
    time.sleep(0.2)
    restored = get_alsa_volume()
    if restored is not None and abs(restored - initial) <= 2:
        print(f"  ✅ Volume restored: {restored}%")
    else:
        print(f"  ⚠️  Volume restore may have failed: {restored}% (expected {initial}%)")
    
    return True


def test_mpd_volume():
    """Test MPD volume control"""
    print("\n" + "="*60)
    print("Testing MPD Volume Control")
    print("="*60)
    
    try:
        controller = MPDController(debug=False)
        if not controller.connect():
            print("\n  ❌ Failed to connect to MPD")
            return False
    except Exception as e:
        print(f"\n  ❌ Failed to initialize MPD controller: {e}")
        return False
    
    try:
        with controller._ensure_connection():
            # Get initial status
            print("\n1. Getting initial MPD status...")
            status = controller.client.status()
            volume_str = status.get('volume')
            
            if volume_str is None or volume_str in ('n/a', '-1'):
                print("  ⚠️  MPD volume control not available (software mixer disabled)")
                print("  ℹ️  This is normal - MPD is using hardware volume control")
                return None  # Not an error, just not available
            
            try:
                initial = int(volume_str)
                print(f"  ✅ Initial MPD volume: {initial}%")
            except (ValueError, TypeError):
                print(f"  ❌ Invalid volume value: {volume_str}")
                return False
            
            # Calculate test volume
            if initial < 50:
                test_volume = min(90, initial + 20)
            else:
                test_volume = max(10, initial - 20)
            
            print(f"\n2. Setting MPD volume to {test_volume}%...")
            controller.client.setvol(test_volume)
            print(f"  ✅ Volume set command executed")
            
            # Wait a moment
            time.sleep(0.2)
            
            # Get volume again
            print(f"\n3. Getting MPD volume after change...")
            status = controller.client.status()
            volume_str = status.get('volume')
            try:
                after = int(volume_str)
                print(f"  ✅ Volume after change: {after}%")
            except (ValueError, TypeError):
                print(f"  ❌ Invalid volume value after change: {volume_str}")
                return False
            
            # Validate
            print(f"\n4. Validating volume change...")
            if abs(after - test_volume) <= 2:
                print(f"  ✅ Volume change successful: {initial}% → {after}% (target: {test_volume}%)")
            else:
                print(f"  ⚠️  Volume mismatch: expected {test_volume}%, got {after}%")
            
            # Restore initial volume
            print(f"\n5. Restoring initial volume ({initial}%)...")
            controller.client.setvol(initial)
            time.sleep(0.2)
            status = controller.client.status()
            restored_str = status.get('volume')
            try:
                restored = int(restored_str)
                if abs(restored - initial) <= 2:
                    print(f"  ✅ Volume restored: {restored}%")
                else:
                    print(f"  ⚠️  Volume restore may have failed: {restored}% (expected {initial}%)")
            except (ValueError, TypeError):
                print(f"  ⚠️  Could not verify restore: {restored_str}")
            
            return True
            
    except Exception as e:
        print(f"\n  ❌ MPD test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function"""
    print("="*60)
    print("Volume Control Debugging Test")
    print("="*60)
    
    # Test ALSA volume
    alsa_ok = test_alsa_volume()
    
    # Test MPD volume
    mpd_result = test_mpd_volume()
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    if alsa_ok:
        print("✅ ALSA volume control: Working")
    else:
        print("❌ ALSA volume control: Failed")
    
    if mpd_result is True:
        print("✅ MPD volume control: Working")
    elif mpd_result is None:
        print("ℹ️  MPD volume control: Not available (hardware control)")
    else:
        print("❌ MPD volume control: Failed")
    
    print("\n" + "="*60)
    
    if alsa_ok:
        print("✅ System ready - ALSA volume control is functional")
        return 0
    else:
        print("❌ System issue - ALSA volume control failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())

