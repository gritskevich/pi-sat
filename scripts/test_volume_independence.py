#!/usr/bin/env python3
"""
Test volume independence: music, TTS, and beep should have independent volumes.
Music volume should NEVER change when TTS or beep plays.
"""

import time
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.mpd_controller import MPDController
from modules.piper_tts import PiperTTS
from modules.audio_player import play_wake_sound
from modules.logging_utils import setup_logger
import config

logger = setup_logger(__name__)

def test_volume_independence():
    """Test that music, TTS, and beep have independent volumes."""
    print("\n=== Testing Volume Independence ===\n")

    # Initialize components
    print("1. Initializing MPD and TTS...")
    mpd = MPDController()
    tts = PiperTTS()

    # Set up music
    print("2. Starting music playback...")
    print(f"   - Setting MPD volume to 50%")
    print(f"   - System Master volume: 40%")
    print(f"   - Expected total music volume: 50% × 40% = 20%")

    with mpd._ensure_connection():
        mpd.client.setvol(50)  # MPD software volume
    mpd.play()

    # Get initial music volume
    with mpd._ensure_connection():
        status = mpd.client.status()
        initial_volume = int(status.get('volume', 0))
    print(f"   ✓ Music playing at MPD volume: {initial_volume}%")

    time.sleep(2)

    # Test TTS volume independence
    print("\n3. Testing TTS volume independence...")
    print(f"   - TTS volume: {config.TTS_VOLUME}% (using sox)")
    print(f"   - Expected TTS output: ~32% (80% × 40% Master)")
    print(f"   - Music should stay at MPD {initial_volume}%")

    tts.speak("Testing TTS volume independence")

    # Check music volume after TTS
    time.sleep(1)
    with mpd._ensure_connection():
        status = mpd.client.status()
        volume_after_tts = int(status.get('volume', 0))
    print(f"   ✓ Music volume after TTS: {volume_after_tts}%")

    if volume_after_tts == initial_volume:
        print(f"   ✅ SUCCESS: Music volume unchanged!")
    else:
        print(f"   ❌ FAIL: Music volume changed from {initial_volume}% to {volume_after_tts}%")

    time.sleep(2)

    # Test beep volume independence
    print("\n4. Testing beep volume independence...")
    print(f"   - Beep volume: {config.BEEP_VOLUME}% (using sox)")
    print(f"   - Expected beep output: ~16% (40% × 40% Master)")
    print(f"   - Music should stay at MPD {initial_volume}%")

    play_wake_sound()

    # Check music volume after beep
    time.sleep(1)
    with mpd._ensure_connection():
        status = mpd.client.status()
        volume_after_beep = int(status.get('volume', 0))
    print(f"   ✓ Music volume after beep: {volume_after_beep}%")

    if volume_after_beep == initial_volume:
        print(f"   ✅ SUCCESS: Music volume unchanged!")
    else:
        print(f"   ❌ FAIL: Music volume changed from {initial_volume}% to {volume_after_beep}%")

    time.sleep(2)

    # Test system Master volume stability
    print("\n5. Checking ALSA Master volume stability...")
    import subprocess
    result = subprocess.run(
        ['amixer', 'get', 'Master'],
        capture_output=True,
        text=True
    )
    for line in result.stdout.split('\n'):
        if '[' in line and '%' in line:
            print(f"   {line.strip()}")
            if '40%' in line:
                print(f"   ✅ SUCCESS: Master volume stable at 40%")
            else:
                print(f"   ⚠️  WARNING: Master volume not at expected 40%")

    # Stop playback
    print("\n6. Stopping playback...")
    mpd.stop()

    # Summary
    print("\n=== Test Summary ===")
    print(f"Initial music volume: {initial_volume}%")
    print(f"After TTS:            {volume_after_tts}%")
    print(f"After beep:           {volume_after_beep}%")

    if volume_after_tts == initial_volume and volume_after_beep == initial_volume:
        print("\n✅ ALL TESTS PASSED: Volume independence verified!")
        return 0
    else:
        print("\n❌ TESTS FAILED: Volume changed during TTS/beep playback")
        return 1

if __name__ == '__main__':
    try:
        sys.exit(test_volume_independence())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        sys.exit(1)
