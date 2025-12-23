#!/usr/bin/env python3
"""Very verbose wake word debugging"""

import numpy as np
import pyaudio
import config
from openwakeword.model import Model

config.THRESHOLD = 0.2
config.VAD_THRESHOLD = 0.1  # Very low

print("Initializing model...")
model = Model(wakeword_models=['alexa_v0.1'], inference_framework='tflite', vad_threshold=0.1)
print(f"Model loaded, models: {list(model.models.keys())}")

print("\nInitializing PyAudio...")
p = pyaudio.PyAudio()
stream = p.open(
    format=pyaudio.paInt16,
    channels=1,
    rate=16000,
    input=True,
    frames_per_buffer=320
)

print("Starting detection loop (10 seconds)...")
print("Say 'ALEXA' NOW!\n")

frame_count = 0
max_frames = 500  # ~10 seconds at 20ms per frame

for i in range(max_frames):
    try:
        data = stream.read(320, exception_on_overflow=False)
        audio = np.frombuffer(data, dtype=np.int16)

        prediction = model.predict(audio)
        frame_count += 1

        # Print every 50 frames (~1 second)
        if frame_count % 50 == 0:
            print(f"Frame {frame_count}: {prediction}")

        # Check for detection
        for wake_word, confidence in prediction.items():
            if confidence > 0.15:  # Very low threshold for debugging
                print(f"\n🔔 Detection: {wake_word} = {confidence:.3f}")
            if confidence > config.THRESHOLD:
                print(f"\n✅ ✅ ✅  WAKE WORD DETECTED: {wake_word} ({confidence:.3f})  ✅ ✅ ✅\n")
                break

    except KeyboardInterrupt:
        break
    except Exception as e:
        print(f"Error: {e}")
        break

stream.stop_stream()
stream.close()
p.terminate()

print(f"\nProcessed {frame_count} frames")
