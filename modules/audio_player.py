import subprocess
import os
import shutil
from modules.logging_utils import setup_logger, log_info, log_warning
import config

logger = setup_logger(__name__)


def _release_mpd_audio_device():
    """
    Release audio device held by MPD if it's paused.

    When MPD is paused (not stopped), it may hold onto the audio device,
    preventing other applications from playing sound. This function stops
    MPD if it's in paused state, ensuring the audio device is released.

    Returns:
        True if MPD was paused and stopped, False otherwise
    """
    # Not needed (and harmful) when using Pulse/PipeWire mixing.
    device = getattr(config, "OUTPUT_ALSA_DEVICE", None)
    if device in ("pulse", "pipewire"):
        return False

    try:
        # Check MPD status
        result = subprocess.run(
            ["mpc", "status"],
            capture_output=True,
            text=True,
            timeout=0.5
        )

        # If MPD is paused, stop it to release the audio device
        if result.returncode == 0 and "[paused]" in result.stdout:
            subprocess.run(
                ["mpc", "stop"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=0.5
            )
            return True

    except Exception:
        pass

    return False


def play_wake_sound():
    """
    Play wake word detection sound.

    Uses paplay (PulseAudio) when output device is 'pulse' for better audio mixing
    with MPD. If MPD is paused and blocking the audio device, it will be stopped
    to ensure the beep plays (it will be resumed later by the command processor).
    """
    if not getattr(config, "PLAY_WAKE_SOUND", True):
        log_info(logger, "Wake sound disabled (PLAY_WAKE_SOUND=false)")
        return
    path = getattr(config, "WAKE_SOUND_PATH", "")
    if not path or not os.path.exists(path):
        log_info(logger, f"Wake sound file missing: {path}")
        return

    log_info(logger, "Wake sound: start")

    # Release audio device if MPD is paused (will be resumed later)
    _release_mpd_audio_device()

    device = getattr(config, "OUTPUT_ALSA_DEVICE", None)

    # Prefer PipeWire native playback when available; fallback to PulseAudio/ALSA.
    if device in ("pulse", "pipewire") and shutil.which("pw-play"):
        # PipeWire can drop ultra-short sounds when the sink is idle.
        # Add leading/trailing silence and repeat 3x to wake the sink reliably.
        if shutil.which("sox"):
            sox_proc = subprocess.run(
                ["sox", path, "-t", "raw", "-r", "48000", "-e", "signed", "-b", "16", "-c", "1", "-", "repeat", "2", "pad", "0.03", "0.05"],
                capture_output=True,
                timeout=2
            )
            if sox_proc.returncode != 0:
                err = sox_proc.stderr.decode("utf-8", errors="replace").strip()
                log_warning(logger, f"Wake sound sox failed: {err}")
                return
            play_proc = subprocess.run(
                ["pw-play", "--format", "s16", "--rate", "48000", "--channels", "1", "--volume", "1.0", "-"],
                input=sox_proc.stdout,
                capture_output=True,
                timeout=2
            )
            if play_proc.returncode != 0:
                err = play_proc.stderr.decode("utf-8", errors="replace").strip()
                log_warning(logger, f"Wake sound pw-play failed: {err}")
            return
        cmd_parts = ["pw-play", "--volume", "1.0", path]
        play_repeats = 3
        play_data = None
    elif device == "pulse":
        if shutil.which("sox"):
            sox_proc = subprocess.run(
                ["sox", path, "-t", "wav", "-", "repeat", "2", "pad", "0.03", "0.05"],
                capture_output=True,
                timeout=2
            )
            if sox_proc.returncode != 0:
                err = sox_proc.stderr.decode("utf-8", errors="replace").strip()
                log_warning(logger, f"Wake sound sox failed: {err}")
                return
            cmd_parts = ["paplay", "--volume=65536", "-"]  # 65536 = 100% volume
            play_repeats = 1
            play_data = sox_proc.stdout
        else:
            cmd_parts = ["paplay", "--volume=65536", path]  # 65536 = 100% volume
            play_repeats = 3
            play_data = None
    else:
        if shutil.which("sox"):
            sox_proc = subprocess.run(
                ["sox", path, "-t", "wav", "-", "repeat", "2", "pad", "0.03", "0.05"],
                capture_output=True,
                timeout=2
            )
            if sox_proc.returncode != 0:
                err = sox_proc.stderr.decode("utf-8", errors="replace").strip()
                log_warning(logger, f"Wake sound sox failed: {err}")
                return
            cmd_parts = ["aplay"]
            if device:
                cmd_parts += ["-D", device]
            cmd_parts += ["-q", "-"]
            play_repeats = 1
            play_data = sox_proc.stdout
        else:
            cmd_parts = ["aplay"]
            if device:
                cmd_parts += ["-D", device]
            cmd_parts += ["-q", path]
            play_repeats = 3
            play_data = None

    for _ in range(play_repeats):
        try:
            subprocess.run(
                cmd_parts,
                input=play_data,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2
            )
        except Exception:
            break
