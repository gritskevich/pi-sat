#!/usr/bin/env python3
"""PoC: Parallel audio playback + recording validation"""

import pyaudio
import wave
import threading
import time
from pathlib import Path

# Config
RATE = 48000
CHUNK = 1024
PLAYBACK_FILE = "tests/audio_samples/integration/fr/alexa_pause_0.3s_joue_frozen.wav"
RECORD_DURATION = 5  # seconds
OUTPUT_FILE = "/tmp/recorded_poc.wav"


def play_audio(filepath: str, event: threading.Event):
    """Play audio file asynchronously"""
    print(f"[PLAY] Starting: {filepath}")

    p = pyaudio.PyAudio()
    wf = wave.open(filepath, 'rb')

    stream = p.open(
        format=p.get_format_from_width(wf.getsampwidth()),
        channels=wf.getnchannels(),
        rate=wf.getframerate(),
        output=True
    )

    event.set()  # Signal recording can start

    data = wf.readframes(CHUNK)
    while data:
        stream.write(data)
        data = wf.readframes(CHUNK)

    stream.stop_stream()
    stream.close()
    p.terminate()
    print("[PLAY] Done")


def record_audio(output_file: str, duration: int, event: threading.Event):
    """Record audio from mic asynchronously"""
    event.wait()  # Wait for playback to start
    print(f"[REC] Starting {duration}s recording...")

    p = pyaudio.PyAudio()

    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )

    frames = []
    for _ in range(int(RATE / CHUNK * duration)):
        data = stream.read(CHUNK)
        frames.append(data)

    stream.stop_stream()
    stream.close()

    # Save
    wf = wave.open(output_file, 'wb')
    wf.setnchannels(1)
    wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    p.terminate()

    print(f"[REC] Done -> {output_file}")


def main():
    print("=== Parallel Audio PoC ===\n")

    # Validate input file
    if not Path(PLAYBACK_FILE).exists():
        print(f"ERROR: {PLAYBACK_FILE} not found")
        return 1

    # Sync event
    start_event = threading.Event()

    # Launch threads
    t_play = threading.Thread(target=play_audio, args=(PLAYBACK_FILE, start_event))
    t_rec = threading.Thread(target=record_audio, args=(OUTPUT_FILE, RECORD_DURATION, start_event))

    t_play.start()
    t_rec.start()

    # Wait for both
    t_play.join()
    t_rec.join()

    print(f"\n✓ Success! Recorded to {OUTPUT_FILE}")
    print(f"  Play it: aplay {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    exit(main())
