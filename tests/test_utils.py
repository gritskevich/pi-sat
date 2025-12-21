import soundfile as sf
import numpy as np
import os
import config

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
        audio, rate = sf.read(audio_path)
    except Exception as e:
        raise Exception(f"Failed to read audio file {file_path}: {e}")
    
    if len(audio.shape) > 1:
        audio = audio[:, 0]
    
    audio = (audio * 32767).astype(np.int16)
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