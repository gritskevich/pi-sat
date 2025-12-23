#!/usr/bin/env python3
"""Test microphone audio levels"""

import numpy as np
import pyaudio

print("Opening microphone...")
p = pyaudio.PyAudio()
stream = p.open(
    format=pyaudio.paInt16,
    channels=1,
    rate=16000,
    input=True,
    frames_per_buffer=1600  # 100ms
)

print("\nListening for 5 seconds...")
print("Please speak or make noise NOW!\n")

for i in range(50):  # 5 seconds
    data = stream.read(1600, exception_on_overflow=False)
    audio = np.frombuffer(data, dtype=np.int16)

    # Calculate RMS (root mean square) as volume indicator
    rms = np.sqrt(np.mean(audio.astype(np.float32)**2))
    max_amp = np.max(np.abs(audio))

    # Simple volume bar
    volume_bar = "█" * int(rms / 200)

    print(f"RMS: {rms:6.1f}  Max: {max_amp:5d}  {volume_bar}")

stream.stop_stream()
stream.close()
p.terminate()

print("\nIf RMS values are all near 0, your microphone isn't working or is muted")
print("If RMS is > 1000 when speaking, microphone is working fine")
