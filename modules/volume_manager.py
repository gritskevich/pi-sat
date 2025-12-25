"""
Volume Manager - SIMPLIFIED single master volume control

Handles:
- Single master volume via PulseAudio/PipeWire sink (pactl)
- All audio (music, TTS, beep) uses the same volume

Best Practice (Raspberry Pi 5 + PipeWire):
- ALSA PCM hardware: Leave at current level (do NOT touch via amixer)
- MPD software volume: 100% (fixed at startup)
- PulseAudio sink volume: THE ONLY volume control (via pactl)

IMPORTANT: We do NOT set ALSA PCM to 100% as it would be too loud.
The research shows: "Don't use amixer, it can confuse PipeWire session managers."
"""
import subprocess
import logging
from typing import Optional, Tuple
from modules.logging_utils import setup_logger
import config

logger = setup_logger(__name__)


class VolumeManager:
    """
    SIMPLIFIED volume management using PulseAudio/PipeWire sink volume.

    Single master volume controls all audio output (music, TTS, beep).
    Uses pactl for PulseAudio/PipeWire volume control.
    """

    def __init__(self, mpd_controller=None):
        """
        Initialize volume manager.

        Args:
            mpd_controller: Optional MPDController instance (for setting MPD to 100%)
        """
        self.mpd_controller = mpd_controller

        # Cached master volume (0-100)
        self.master_volume = None

        # Detect PulseAudio/PipeWire availability
        self._pulse_available = self._check_pulse_available()

        logger.info(f"VolumeManager initialized - PulseAudio/PipeWire: {self._pulse_available}")

    def initialize_default_volume(self, default_volume: int = 50):
        """
        Initialize MASTER volume at startup (simplified single-volume approach).

        Steps:
        1. Set PulseAudio sink to default_volume (THE ONLY master control) - FIRST!
        2. Set MPD software volume to 100% (fixed, never changed)

        IMPORTANT: We do NOT touch ALSA PCM hardware volume - let it stay at its current level.
        Best practice for Raspberry Pi 5 + PipeWire: only control via PulseAudio sink (pactl).

        Args:
            default_volume: Default master volume percentage (0-100)
        """
        try:
            # Step 1: Set PulseAudio sink to default volume FIRST (before any MPD operations)
            success = self.set_master_volume(default_volume)
            if success:
                self.master_volume = default_volume
                logger.info(f"🔊 Initialized MASTER volume: {default_volume}%")
            else:
                logger.warning(f"Failed to initialize volume to {default_volume}%, using current volume")
                current = self.get_master_volume()
                if current is not None:
                    self.master_volume = current
                    logger.info(f"🔊 Using current MASTER volume: {current}%")
                else:
                    self.master_volume = default_volume
                    logger.warning(f"Cannot read volume, assuming {default_volume}%")

            # Step 2: Set MPD to 100% (software volume, never changed after this)
            if self.mpd_controller:
                self._set_mpd_volume_100()
        except Exception as e:
            logger.error(f"Error initializing default volume: {e}")
            self.master_volume = default_volume

    def _check_pulse_available(self) -> bool:
        """Check if PulseAudio/PipeWire is available"""
        try:
            result = subprocess.run(
                ['pactl', 'get-sink-volume', '@DEFAULT_SINK@'],
                capture_output=True,
                timeout=1
            )
            return result.returncode == 0
        except Exception:
            return False

    def _set_mpd_volume_100(self) -> bool:
        """
        Set MPD software volume to 100% (fixed, never changed after startup).

        Returns:
            True if successful
        """
        if not self.mpd_controller:
            return False

        try:
            with self.mpd_controller._ensure_connection():
                self.mpd_controller.client.setvol(100)
                logger.info(f"🔈 MPD software volume set to 100% (fixed)")
                return True
        except Exception as e:
            logger.debug(f"Failed to set MPD volume to 100%: {e}")
        return False
    
    def get_master_volume(self) -> Optional[int]:
        """
        Get current MASTER volume from PulseAudio/PipeWire sink (0-100).

        Uses cached value when available for performance.

        Returns:
            Volume percentage or None if unavailable
        """
        # Use cached volume if available
        if self.master_volume is not None:
            return self.master_volume

        # Otherwise read from PulseAudio/PipeWire sink
        if self._pulse_available:
            vol = self._get_pulse_volume()
            if vol is not None:
                self.master_volume = vol
            return vol

        return None

    def set_master_volume(self, volume: int) -> bool:
        """
        Set MASTER volume via PulseAudio/PipeWire sink (0-100).

        This is the ONLY volume control - affects all audio output.

        Args:
            volume: Volume percentage (0-100)

        Returns:
            True if successful
        """
        volume = max(0, min(100, volume))

        if self._pulse_available:
            if self._set_pulse_volume(volume):
                self.master_volume = volume
                logger.debug(f"MASTER volume set (PulseAudio sink): {volume}%")
                return True

        logger.warning("PulseAudio/PipeWire not available for volume control")
        return False

    def _get_pulse_volume(self) -> Optional[int]:
        """Get PulseAudio/PipeWire sink volume percentage"""
        try:
            result = subprocess.run(
                ['pactl', 'get-sink-volume', '@DEFAULT_SINK@'],
                capture_output=True,
                text=True,
                timeout=1
            )

            if result.returncode != 0:
                return None

            # Parse output like: "Volume: front-left: 32768 /  50% / -18.06 dB,   front-right: 32768 /  50% / -18.06 dB"
            for line in result.stdout.split('\n'):
                if 'Volume:' in line and '%' in line:
                    # Extract first percentage value
                    parts = line.split('/')
                    for part in parts:
                        if '%' in part:
                            pct_str = part.strip().replace('%', '').strip()
                            try:
                                return int(pct_str)
                            except ValueError:
                                continue

            return None
        except Exception as e:
            logger.debug(f"Failed to get PulseAudio volume: {e}")
            return None

    def _set_pulse_volume(self, volume: int) -> bool:
        """Set PulseAudio/PipeWire sink volume percentage"""
        try:
            result = subprocess.run(
                ['pactl', 'set-sink-volume', '@DEFAULT_SINK@', f'{volume}%'],
                capture_output=True,
                timeout=1
            )
            return result.returncode == 0
        except Exception as e:
            logger.debug(f"Failed to set PulseAudio volume: {e}")
            return False
    
    def _adjust_volume(self, amount: int, direction: str) -> Tuple[bool, str]:
        """
        Helper to adjust volume up or down.

        Args:
            amount: Volume adjustment amount
            direction: 'up' or 'down'

        Returns:
            Tuple of (success, message)
        """
        current = self.master_volume if self.master_volume is not None else self.get_master_volume()
        if current is None:
            return (False, "Volume control unavailable")

        if direction == 'up':
            max_vol = min(100, getattr(config, "MAX_VOLUME", 100))
            new_volume = min(max_vol, current + amount)
        else:  # down
            new_volume = max(0, current - amount)

        success = self.set_master_volume(new_volume)
        if success:
            self.master_volume = new_volume
            logger.info(f"📊 Volume {direction}: {current}% → {new_volume}%")
            return (True, f"Volume {new_volume}%")
        return (False, f"Failed to {'increase' if direction == 'up' else 'decrease'} volume")

    def music_volume_up(self, amount: int = 10) -> Tuple[bool, str]:
        """
        Increase MASTER volume.

        Args:
            amount: Volume increase amount

        Returns:
            Tuple of (success, message)
        """
        return self._adjust_volume(amount, 'up')

    def music_volume_down(self, amount: int = 10) -> Tuple[bool, str]:
        """
        Decrease MASTER volume.

        Args:
            amount: Volume decrease amount

        Returns:
            Tuple of (success, message)
        """
        return self._adjust_volume(amount, 'down')
