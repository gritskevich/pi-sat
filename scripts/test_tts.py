#!/usr/bin/env python3
"""
Test TTS Integration - End-to-End Audio Output Verification

Tests that TTS is properly integrated and can produce audio output.
Run this to verify TTS works on your Raspberry Pi 5.
"""

import sys

import config
from modules.piper_tts import PiperTTS
from modules.volume_manager import VolumeManager
from modules.audio_devices import validate_alsa_device, list_alsa_devices, get_default_alsa_device


def test_audio_device():
    """Test: Validate audio output device"""
    print("\n=== Testing Audio Device ===")
    device = config.PIPER_OUTPUT_DEVICE
    print(f"Configured device: {device}")
    
    if validate_alsa_device(device):
        print(f"✓ Device '{device}' is valid")
    else:
        print(f"⚠ Device '{device}' may not be available")
        default = get_default_alsa_device()
        print(f"  Suggested default: {default}")
    
    print("\nAvailable ALSA devices:")
    devices = list_alsa_devices()
    if devices:
        for device in devices:
            print(f"  - {device}")
    else:
        print("  (No devices found)")
    
    return validate_alsa_device(device)


def test_tts_initialization():
    """Test: TTS initialization"""
    print("\n=== Testing TTS Initialization ===")
    try:
        tts = PiperTTS(output_device=config.PIPER_OUTPUT_DEVICE)
        print(f"✓ TTS initialized successfully")
        print(f"  Model: {tts.model_path.name}")
        print(f"  Output device: {tts.output_device}")
        return tts
    except Exception as e:
        print(f"✗ TTS initialization failed: {e}")
        return None


def test_tts_with_volume_manager():
    """Test: TTS with volume manager"""
    print("\n=== Testing TTS with Volume Manager ===")
    try:
        from modules.mpd_controller import MPDController
        mpd_controller = MPDController()
        volume_manager = VolumeManager(mpd_controller=mpd_controller)
        tts = PiperTTS(
            volume_manager=volume_manager,
            output_device=config.PIPER_OUTPUT_DEVICE
        )
        print("✓ TTS initialized with volume manager")
        return tts
    except Exception as e:
        print(f"⚠ TTS with volume manager failed (may be expected): {e}")
        return None


def test_tts_speak(text="Hello, this is a test of the text to speech system."):
    """Test: TTS speech generation and playback"""
    print("\n=== Testing TTS Speech Playback ===")
    print(f"Text: '{text}'")
    
    try:
        tts = PiperTTS(output_device=config.PIPER_OUTPUT_DEVICE)
        print("Speaking...")
        success = tts.speak(text)
        
        if success:
            print("✓ Speech playback successful")
            print("  (You should have heard audio output)")
        else:
            print("✗ Speech playback failed")
        
        return success
    except Exception as e:
        print(f"✗ Speech playback error: {e}")
        return False


def test_orchestrator_tts_integration():
    """Test: TTS integration in command processor (new architecture)"""
    print("\n=== Testing CommandProcessor TTS Integration ===")
    try:
        from modules.factory import create_command_processor
        from modules.mpd_controller import MPDController
        
        mpd_controller = MPDController()
        processor = create_command_processor(mpd_controller=mpd_controller, verbose=False, debug=True)
        
        print("✓ CommandProcessor initialized")
        print(f"  TTS device: {processor.tts.output_device}")
        print(f"  TTS has volume_manager: {processor.tts.volume_manager is not None}")
        
        try:
            processor.stt.cleanup()
        except Exception:
            pass
        return True
    except Exception as e:
        print(f"✗ CommandProcessor TTS integration test failed: {e}")
        return False


def main():
    """Run all TTS tests"""
    print("=" * 60)
    print("Pi-Sat TTS Integration Test")
    print("=" * 60)
    
    results = {}
    
    # Test 1: Audio device
    results['audio_device'] = test_audio_device()
    
    # Test 2: TTS initialization
    tts = test_tts_initialization()
    results['tts_init'] = tts is not None
    
    # Test 3: TTS with volume manager
    tts_vm = test_tts_with_volume_manager()
    results['tts_volume_manager'] = tts_vm is not None
    
    # Test 4: TTS speech playback
    if tts:
        results['tts_speak'] = test_tts_speak()
    else:
        print("\n⚠ Skipping speech playback test (TTS not initialized)")
        results['tts_speak'] = False
    
    # Test 5: Orchestrator integration
    results['orchestrator_integration'] = test_orchestrator_tts_integration()
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(results.values())
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
