import subprocess
import os
import config


def play_wake_sound():
    """
    Play wake sound in background (non-blocking).

    This allows recording to start immediately without waiting
    for the sound to finish playing.
    """
    if not getattr(config, "PLAY_WAKE_SOUND", True):
        return
    path = getattr(config, "WAKE_SOUND_PATH", "")
    if not path or not os.path.exists(path):
        return
    device = getattr(config, "OUTPUT_ALSA_DEVICE", None)
    cmd = ["aplay"]
    if device:
        cmd += ["-D", device]
    cmd.append(path)
    try:
        # Use Popen instead of run to avoid blocking
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


