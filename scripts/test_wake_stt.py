#!/usr/bin/env python3
"""
Minimal wake word → STT feedback test with debug audio saving
Usage: python scripts/test_wake_stt.py [--save-audio]
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pyaudio
import numpy as np
import time
import wave
from datetime import datetime
from openwakeword.model import Model
import openwakeword.utils
import config
from modules.hailo_stt import HailoSTT
from modules.speech_recorder import SpeechRecorder
from modules.audio_player import play_wake_sound
from modules.logging_utils import setup_logger, log_info, log_success, log_warning, log_error

# Debug mode - save audio files
SAVE_AUDIO = '--save-audio' in sys.argv
AUDIO_DEBUG_DIR = 'debug_audio'

# Setup logger for this script
logger = setup_logger(__name__)

def save_audio_file(audio_data, prefix, transcription=""):
    """Save audio data to WAV file with timestamp and transcription"""
    if not SAVE_AUDIO:
        return

    # Create debug directory if it doesn't exist
    os.makedirs(AUDIO_DEBUG_DIR, exist_ok=True)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Sanitize transcription for filename (max 30 chars)
    safe_text = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in transcription)[:30]
    filename = f"{AUDIO_DEBUG_DIR}/{timestamp}_{prefix}"
    if safe_text:
        filename += f"_{safe_text}"
    filename += ".wav"

    # Save as WAV file
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(config.RATE)  # Use config rate
        wf.writeframes(audio_data)

    log_info(logger, f"💾 Saved: {filename}")
    return filename

def wait_for_wake_word(model, stream, input_rate=48000):
    """Listen for wake word and return when detected"""
    model_rate = 16000
    resample_buf = np.zeros(0, dtype=np.int16)
    frame_size = 320  # 20ms at 16kHz
    last_detection_time = 0
    cooldown = 2.0

    while True:
        try:
            data = stream.read(config.CHUNK, exception_on_overflow=False)
            audio = np.frombuffer(data, dtype=np.int16)

            # Resample to 16kHz if needed
            if input_rate != model_rate and audio.size > 0:
                src = audio.astype(np.float32)
                src_len = src.shape[0]
                ratio = model_rate / float(input_rate)
                new_len = max(1, int(round(src_len * ratio)))
                x_old = np.linspace(0.0, 1.0, num=src_len, dtype=np.float32)
                x_new = np.linspace(0.0, 1.0, num=new_len, dtype=np.float32)
                resampled = np.interp(x_new, x_old, src)
                audio = np.clip(resampled, -32768, 32767).astype(np.int16)

            # Accumulate and process frames
            if audio.size > 0:
                resample_buf = np.concatenate((resample_buf, audio))

            while resample_buf.size >= frame_size:
                frame = resample_buf[:frame_size]
                resample_buf = resample_buf[frame_size:]

                prediction = model.predict(frame)
                for wake_word, confidence in prediction.items():
                    if confidence > config.THRESHOLD:
                        current_time = time.time()
                        if current_time - last_detection_time >= cooldown:
                            last_detection_time = current_time
                            # Reset model state (but don't sleep - we need to start recording ASAP!)
                            silence = np.zeros(config.CHUNK * 25, dtype=np.int16)
                            for _ in range(5):
                                model.predict(silence)
                            # Return immediately - no blocking sleep
                            return

                time.sleep(0.005)

        except Exception as e:
            log_error(logger, f"Wake word detection error: {e}")
            break

def main():
    """Simple wake word + STT test loop"""

    log_info(logger, "=" * 60)
    log_info(logger, "WAKE WORD → STT TEST")
    log_info(logger, "=" * 60)
    log_info(logger, "1. Say 'Alexa' to trigger")
    log_info(logger, "2. Then speak your command")
    log_info(logger, "3. Press Ctrl+C to exit")
    log_info(logger, "=" * 60)
    log_info(logger, "")
    log_info(logger, "Wake Word Optimizations:")
    log_info(logger, f"  Model: {config.WAKE_WORD_MODELS[0]}")
    log_info(logger, f"  Inference: {config.INFERENCE_FRAMEWORK}")
    log_info(logger, f"  Threshold: {config.THRESHOLD}")
    log_info(logger, f"  VAD enabled: {config.VAD_THRESHOLD > 0.0} (threshold: {config.VAD_THRESHOLD})")
    log_info(logger, f"  Noise suppression: {config.ENABLE_SPEEX_NOISE_SUPPRESSION}")
    log_info(logger, "=" * 60)
    log_info(logger, "Recording VAD Settings (tune with ./pi-sat.sh calibrate_vad):")
    log_info(logger, f"  Speech multiplier: {config.VAD_SPEECH_MULTIPLIER}x")
    log_info(logger, f"  Silence duration: {config.VAD_SILENCE_DURATION}s")
    log_info(logger, f"  Min speech: {config.VAD_MIN_SPEECH_DURATION}s")
    log_info(logger, f"  Language: {config.HAILO_STT_LANGUAGE}")
    log_info(logger, "=" * 60)
    if SAVE_AUDIO:
        log_info(logger, f"🎙️  DEBUG MODE: Saving audio to {AUDIO_DEBUG_DIR}/")
        log_info(logger, "=" * 60)
    log_info(logger, "")

    # Initialize components with optimizations
    openwakeword.utils.download_models()
    model = Model(
        wakeword_models=config.WAKE_WORD_MODELS,
        inference_framework=config.INFERENCE_FRAMEWORK,
        vad_threshold=config.VAD_THRESHOLD,
        enable_speex_noise_suppression=config.ENABLE_SPEEX_NOISE_SUPPRESSION
    )

    p = pyaudio.PyAudio()
    stream = p.open(
        format=getattr(pyaudio, config.FORMAT),
        channels=config.CHANNELS,
        rate=config.RATE,
        input=True,
        frames_per_buffer=config.CHUNK
    )

    stt = HailoSTT()
    recorder = SpeechRecorder()

    try:
        iteration = 0

        while True:
            iteration += 1
            log_info(logger, f"\n[{iteration}] Listening for wake word 'Alexa'...")

            # Wait for wake word
            wait_for_wake_word(model, stream, input_rate=config.RATE)
            log_success(logger, "Wake word detected!")

            # Play confirmation sound (in background to avoid blocking)
            log_info(logger, "🔊 Playing wake sound...")
            import threading
            sound_thread = threading.Thread(target=play_wake_sound, daemon=True)
            sound_thread.start()

            # INSTANT RECORDING: Start recording immediately while beep plays
            # Skip time is configurable (0.0 = instant with beep-instant.wav)
            skip_seconds = config.WAKE_SOUND_SKIP_SECONDS

            if skip_seconds > 0:
                time.sleep(skip_seconds)  # Optional: wait for longer wake sounds
                log_info(logger, "🎤 Recording... (speak now)")
                audio_data = recorder.record_from_stream(stream, input_rate=config.RATE)
            else:
                # Instant mode: record immediately while beep plays!
                log_info(logger, "🎤 Recording... (instant mode - speak now!)")
                audio_data = recorder.record_from_stream(
                    stream,
                    input_rate=config.RATE,
                    skip_initial_seconds=0.0  # No skipping in test mode with instant beep
                )
            log_success(logger, f"Recording complete ({len(audio_data)} bytes)")

            # Save audio file for debugging
            if SAVE_AUDIO:
                save_audio_file(audio_data, f"recording_{iteration:03d}", "")

            # Transcribe
            log_info(logger, "🔄 Transcribing...")
            transcription = stt.transcribe(audio_data)

            # Save audio with transcription in filename
            if SAVE_AUDIO:
                save_audio_file(audio_data, f"transcribed_{iteration:03d}", transcription)

            # Show result
            log_info(logger, "")
            log_info(logger, "=" * 60)
            log_success(logger, f"RESULT: {transcription}")
            log_info(logger, "=" * 60)
            log_info(logger, "")

    except KeyboardInterrupt:
        log_info(logger, "\n\nTest stopped by user")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        log_info(logger, "Cleanup complete")

if __name__ == "__main__":
    main()
