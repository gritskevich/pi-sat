import subprocess
import os
import config


def play_wake_sound():
    """
    Play wake sound in background (non-blocking).

    This allows recording to start immediately without waiting
    for the sound to finish playing.

    Uses sox for independent volume control (doesn't affect music/TTS).
    """
    if not getattr(config, "PLAY_WAKE_SOUND", True):
        return
    path = getattr(config, "WAKE_SOUND_PATH", "")
    if not path or not os.path.exists(path):
        return
    device = getattr(config, "OUTPUT_ALSA_DEVICE", None)

    # Convert BEEP_VOLUME (0-100) to sox volume multiplier (0.0-1.0)
    beep_volume_pct = getattr(config, "BEEP_VOLUME", 40)
    sox_volume = beep_volume_pct / 100.0

    # Use sox to apply volume, then pipe to aplay
    # sox input.wav -t wav - vol X | aplay
    cmd_parts = ["sox", path, "-t", "wav", "-", "vol", str(sox_volume), "|", "aplay"]
    if device:
        cmd_parts += ["-D", device]
    cmd_parts.append("-q")

    cmd = " ".join(cmd_parts)
    try:
        # Use Popen with shell=True for pipe support (non-blocking)
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


