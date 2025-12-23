#!/usr/bin/env python3
"""Test wake word with VAD disabled"""

import numpy as np
import pyaudio
from openwakeword.model import Model

print("Initializing model with VAD DISABLED (threshold=0.0)...")
model = Model(
    wakeword_models=['alexa_v0.1'],
    inference_framework='tflite',
    vad_threshold=0.0  # DISABLE VAD completely
)

print("Opening microphone...")
p = pyaudio.PyAudio()
stream = p.open(
    format=pyaudio.paInt16,
    channels=1,
    rate=16000,
    input=True,
    frames_per_buffer=320
)

print("\n" + "="*60)
print("Listening for 10 seconds with VAD DISABLED...")
print("Say 'ALEXA' clearly and loudly NOW!")
print("="*60 + "\n")

frame_count = 0
max_frames = 500

for i in range(max_frames):
    try:
        data = stream.read(320, exception_on_overflow=False)
        audio = np.frombuffer(data, dtype=np.int16)

        prediction = model.predict(audio)
        frame_count += 1

        # Show all non-zero confidences
        for wake_word, confidence in prediction.items():
            if confidence > 0.01:
                print(f"Frame {frame_count}: {wake_word} = {confidence:.4f}")

            if confidence > 0.35:
                print(f"\n✅ ✅ ✅  DETECTED: {wake_word} ({confidence:.3f})  ✅ ✅ ✅\n")
                stream.stop_stream()
                stream.close()
                p.terminate()
                print("SUCCESS!")
                exit(0)

    except KeyboardInterrupt:
        break

stream.stop_stream()
stream.close()
p.terminate()

print(f"\nProcessed {frame_count} frames. No detection.")
