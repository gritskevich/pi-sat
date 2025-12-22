import os
import wave

import numpy as np

import config


def read_wav_mono_int16(path: str) -> tuple[np.ndarray, int]:
    """Read a WAV file as mono int16 numpy array + sample rate (WAV-only standard)."""
    with wave.open(path, "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        rate = wf.getframerate()
        frames = wf.getnframes()
        raw = wf.readframes(frames)

    if sampwidth != 2:
        raise ValueError(f"expected 16-bit PCM WAV (sampwidth=2), got {sampwidth}: {path}")

    audio = np.frombuffer(raw, dtype=np.int16)
    if channels > 1:
        audio = audio.reshape(-1, channels)[:, 0]
    return audio, rate

def reset_model_state(model):
    silence = np.zeros(config.CHUNK * 25, dtype=np.int16)
    for _ in range(5):
        model.predict(silence)

def process_audio_file(file_path, model):
    # Accept either full path or filename
    if os.path.isabs(file_path):
        audio_path = file_path
    else:
        # Look for file in audio_samples first, then fallback to audio_16k for compatibility
        audio_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_samples", file_path)
        
        if not os.path.exists(audio_path):
            # Fallback to old location for compatibility
            audio_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "audio_16k", file_path)
    
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    
    try:
        audio, rate = read_wav_mono_int16(audio_path)
    except Exception as e:
        raise Exception(f"Failed to read audio file {file_path}: {e}")

    if audio.dtype != np.int16:
        audio = audio.astype(np.int16)
    silence_pad = np.zeros(config.CHUNK * 10, dtype=np.int16)
    audio = np.concatenate([silence_pad, audio, silence_pad])
    
    chunk_size = config.CHUNK
    max_confidence = 0
    detections = 0
    
    for i in range(0, len(audio), chunk_size):
        chunk = audio[i:i+chunk_size]
        if len(chunk) < chunk_size:
            chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
        
        prediction = model.predict(chunk)
        for wake_word, confidence in prediction.items():
            max_confidence = max(max_confidence, confidence)
            if confidence > config.THRESHOLD:
                detections += 1
    
    return detections > 0, max_confidence 
