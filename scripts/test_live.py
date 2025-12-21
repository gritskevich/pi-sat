#!/usr/bin/env python3
"""Minimal live tests - wake word, STT, full pipeline"""
import sys

def test_wake_word():
    """Test: Say 'Alexa' - should detect"""
    from modules.wake_word_listener import WakeWordListener
    print("🔔 Say 'Alexa' (Ctrl+C to stop)...")
    listener = WakeWordListener(debug=True)
    listener.running = True
    listener.start_listening()

def test_stt():
    """Test: Record → Transcribe"""
    from modules.speech_recorder import SpeechRecorder
    from modules.hailo_stt import HailoSTT
    print("🎤 Speak now (will auto-stop after 1s silence)...")
    recorder = SpeechRecorder()
    audio = recorder.record_command()
    print(f"✓ Recorded {len(audio)/16000:.1f}s")
    print("📝 Transcribing...")
    stt = HailoSTT()
    text = stt.transcribe(audio)
    print(f"✓ Transcribed: '{text}'")

def test_pipeline():
    """Test: Full orchestrator (Wake → Record → Transcribe → TTS)"""
    from modules.factory import create_production_orchestrator
    print("🔔 Say 'Alexa', then speak command...")
    orchestrator = create_production_orchestrator(verbose=True, debug=True)
    try:
        orchestrator.start()
    except KeyboardInterrupt:
        orchestrator.stop()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        test = sys.argv[1]
        if test == 'wake':
            test_wake_word()
        elif test == 'stt':
            test_stt()
        elif test == 'pipeline':
            test_pipeline()
        else:
            print("Usage: python test_live.py [wake|stt|pipeline]")
    else:
        print("Usage: python test_live.py [wake|stt|pipeline]")
