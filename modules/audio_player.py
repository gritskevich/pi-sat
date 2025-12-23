import subprocess
import os
import config


def play_wake_sound():
    """
    Play wake sound in background (non-blocking).

    This allows recording to start immediately without waiting
    for the sound to finish playing.

    SIMPLIFIED: Volume controlled by PulseAudio sink (pactl), not sox.
    All audio plays at 100%; master volume controls everything.
    """
    if not getattr(config, "PLAY_WAKE_SOUND", True):
        return
    path = getattr(config, "WAKE_SOUND_PATH", "")
    if not path or not os.path.exists(path):
        return
    device = getattr(config, "OUTPUT_ALSA_DEVICE", None)

    # Play at 100% volume (NO sox scaling), PulseAudio sink controls actual volume
    cmd_parts = ["aplay"]
    if device:
        cmd_parts += ["-D", device]
    cmd_parts += ["-q", path]

    cmd = " ".join(cmd_parts)
    try:
        # Use Popen for non-blocking playback
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


