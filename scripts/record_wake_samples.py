#!/usr/bin/env python3
"""Record wake word samples for training. Press Ctrl+C to stop."""
import sys
import wave
import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pyaudio
from modules.audio_devices import find_input_device_index
from modules.alsa_utils import suppress_alsa_errors, suppress_jack_autostart, suppress_stderr

RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK = 1024

def main():
    output_dir = Path(__file__).parent.parent / "recordings"
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"wake_samples_{timestamp}.wav"

    suppress_alsa_errors()
    suppress_jack_autostart()

    with suppress_stderr():
        p = pyaudio.PyAudio()

    # Find USB Microphone
    idx = find_input_device_index("USB Microphone")
    if idx is None:
        print("USB Microphone not found, using default")

    # Try 16kHz, fallback to 48kHz
    rate = RATE
    try:
        with suppress_stderr():
            stream = p.open(format=FORMAT, channels=CHANNELS, rate=rate,
                           input=True, input_device_index=idx, frames_per_buffer=CHUNK)
    except Exception:
        rate = 48000
        print(f"Using {rate}Hz (will need resampling)")
        with suppress_stderr():
            stream = p.open(format=FORMAT, channels=CHANNELS, rate=rate,
                           input=True, input_device_index=idx, frames_per_buffer=CHUNK)

    print(f"\n🎤 Recording to: {output_file}")
    print(f"   Sample rate: {rate}Hz")
    print("\n📢 Instructions:")
    print("   1. Say 'ALEXA' clearly")
    print("   2. Wait 2-3 seconds")
    print("   3. Repeat 10-20 times")
    print("   4. Press Ctrl+C when done\n")
    print("Recording... (Ctrl+C to stop)")

    frames = []
    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
    except KeyboardInterrupt:
        pass

    stream.stop_stream()
    stream.close()
    p.terminate()

    # Save WAV
    with wave.open(str(output_file), 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(rate)
        wf.writeframes(b''.join(frames))

    duration = len(frames) * CHUNK / rate
    print(f"\n✅ Saved: {output_file}")
    print(f"   Duration: {duration:.1f}s")
    print(f"\nNext: python scripts/cut_wake_samples.py {output_file}")

if __name__ == "__main__":
    main()
