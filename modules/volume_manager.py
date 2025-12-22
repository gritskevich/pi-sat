"""
Volume Manager - Unified volume control for music and TTS

Handles:
- Music volume (MPD software volume + ALSA fallback)
- TTS volume (ALSA hardware volume, separate from music)
- Volume ducking for music during voice input
- Volume restoration after voice input
"""
import subprocess
import logging
from typing import Optional, Tuple
from modules.logging_utils import setup_logger
import config

logger = setup_logger(__name__)


class VolumeManager:
    """
    Unified volume management for music playback and TTS.
    
    Manages separate volumes:
    - Music: MPD software volume (if available) or ALSA Master
    - TTS: ALSA Master (always, independent of music volume)
    """
    
    def __init__(self, mpd_controller=None):
        """
        Initialize volume manager.
        
        Args:
            mpd_controller: Optional MPDController instance for music volume
        """
        self.mpd_controller = mpd_controller
        self._music_original_volume = None
        self._ducking_active = False
        
        # Volume levels (0-100)
        self.music_volume = None
        self.tts_volume = None
        
        # Detect available volume control methods
        self._mpd_volume_available = self._check_mpd_volume()
        self._alsa_available = self._check_alsa_available()
        
        logger.info(f"VolumeManager initialized - MPD: {self._mpd_volume_available}, ALSA: {self._alsa_available}")
    
    def _check_mpd_volume(self) -> bool:
        """Check if MPD software volume is available"""
        if not self.mpd_controller:
            return False
        
        try:
            with self.mpd_controller._ensure_connection():
                status = self.mpd_controller.client.status()
                volume_str = status.get('volume')
                if volume_str and volume_str not in (None, 'n/a', '-1'):
                    return True
        except Exception:
            pass
        
        return False
    
    def _check_alsa_available(self) -> bool:
        """Check if ALSA volume control is available"""
        try:
            result = subprocess.run(
                ['amixer', 'get', 'Master'],
                capture_output=True,
                timeout=1
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def get_music_volume(self) -> Optional[int]:
        """
        Get current music volume (0-100).
        
        Returns:
            Volume percentage or None if unavailable
        """
        if self._mpd_volume_available and self.mpd_controller:
            try:
                with self.mpd_controller._ensure_connection():
                    status = self.mpd_controller.client.status()
                    volume_str = status.get('volume')
                    if volume_str and volume_str not in (None, 'n/a', '-1'):
                        self.music_volume = int(volume_str)
                        return self.music_volume
            except Exception as e:
                logger.debug(f"Failed to get MPD volume: {e}")
        
        if self._alsa_available:
            self.music_volume = self._get_alsa_volume()
            return self.music_volume
        
        return None
    
    def set_music_volume(self, volume: int) -> bool:
        """
        Set music volume (0-100).
        
        Args:
            volume: Volume percentage (0-100)
            
        Returns:
            True if successful
        """
        volume = max(0, min(100, volume))
        
        if self._mpd_volume_available and self.mpd_controller:
            try:
                with self.mpd_controller._ensure_connection():
                    self.mpd_controller.client.setvol(volume)
                    self.music_volume = volume
                    logger.debug(f"Music volume set (MPD): {volume}%")
                    return True
            except Exception as e:
                logger.debug(f"Failed to set MPD volume: {e}")
        
        if self._alsa_available:
            if self._set_alsa_volume(volume):
                self.music_volume = volume
                logger.debug(f"Music volume set (ALSA): {volume}%")
                return True
        
        return False
    
    def get_tts_volume(self) -> Optional[int]:
        """
        Get current TTS volume (0-100).
        
        Returns:
            Volume percentage or None if unavailable
        """
        if self._alsa_available:
            self.tts_volume = self._get_alsa_volume()
            return self.tts_volume
        return None
    
    def set_tts_volume(self, volume: int) -> bool:
        """
        Set TTS volume (0-100).

        DEPRECATED: TTS now uses aplay --volume for independent control.
        This method no longer modifies ALSA Master to avoid affecting music volume.

        Args:
            volume: Volume percentage (0-100)

        Returns:
            True (always succeeds, stores value only)
        """
        volume = max(0, min(100, volume))
        self.tts_volume = volume
        logger.debug(f"TTS volume stored (not applied to Master): {volume}%")
        return True
    
    def duck_music_volume(self, duck_to: int = 20) -> bool:
        """
        Duck music volume for voice input (preserves TTS volume).
        
        Args:
            duck_to: Target volume percentage during ducking
            
        Returns:
            True if successful
        """
        if self._ducking_active:
            logger.debug("Volume already ducked")
            return True
        
        current = self.get_music_volume()
        if current is None:
            logger.warning("Cannot duck volume - no volume control available")
            return False
        
        self._music_original_volume = current
        success = self.set_music_volume(duck_to)
        
        if success:
            self._ducking_active = True
            logger.info(f"Music volume ducked: {current}% → {duck_to}%")
        
        return success
    
    def restore_music_volume(self) -> bool:
        """
        Restore music volume after voice input.
        
        Returns:
            True if successful
        """
        if not self._ducking_active:
            return True
        
        if self._music_original_volume is None:
            logger.warning("No original volume to restore")
            self._ducking_active = False
            return False
        
        success = self.set_music_volume(self._music_original_volume)
        
        if success:
            logger.info(f"Music volume restored: {self._music_original_volume}%")
            self._ducking_active = False
            self._music_original_volume = None
        
        return success
    
    def _get_alsa_volume(self) -> Optional[int]:
        """Get ALSA Master volume percentage"""
        try:
            result = subprocess.run(
                ['amixer', 'get', 'Master'],
                capture_output=True,
                text=True,
                timeout=1
            )
            
            if result.returncode != 0:
                return None
            
            for line in result.stdout.split('\n'):
                if '[' in line and '%' in line:
                    start = line.find('[') + 1
                    end = line.find('%', start)
                    if start > 0 and end > start:
                        return int(line[start:end])
            
            return None
        except Exception as e:
            logger.debug(f"Failed to get ALSA volume: {e}")
            return None
    
    def _set_alsa_volume(self, volume: int) -> bool:
        """Set ALSA Master volume percentage"""
        try:
            result = subprocess.run(
                ['amixer', 'set', 'Master', f'{volume}%'],
                capture_output=True,
                timeout=1
            )
            return result.returncode == 0
        except Exception as e:
            logger.debug(f"Failed to set ALSA volume: {e}")
            return False
    
    def music_volume_up(self, amount: int = 10) -> Tuple[bool, str]:
        """
        Increase music volume.
        
        Args:
            amount: Volume increase amount
            
        Returns:
            Tuple of (success, message)
        """
        # If we're ducking during a voice command, adjust the *restore target* volume
        # instead of the currently-ducked output volume.
        if self._ducking_active and self._music_original_volume is not None:
            max_vol = min(100, getattr(config, "MAX_VOLUME", 100))
            new_volume = min(max_vol, self._music_original_volume + amount)
            self._music_original_volume = new_volume
            self.music_volume = new_volume
            return (True, f"Music volume {new_volume}%")

        current = self.get_music_volume()
        if current is None:
            return (False, "Volume control unavailable")
        
        max_vol = min(100, getattr(config, "MAX_VOLUME", 100))
        new_volume = min(max_vol, current + amount)
        success = self.set_music_volume(new_volume)
        
        if success:
            return (True, f"Music volume {new_volume}%")
        return (False, "Failed to increase volume")
    
    def music_volume_down(self, amount: int = 10) -> Tuple[bool, str]:
        """
        Decrease music volume.
        
        Args:
            amount: Volume decrease amount
            
        Returns:
            Tuple of (success, message)
        """
        # If we're ducking during a voice command, adjust the *restore target* volume
        # instead of the currently-ducked output volume.
        if self._ducking_active and self._music_original_volume is not None:
            new_volume = max(0, self._music_original_volume - amount)
            self._music_original_volume = new_volume
            self.music_volume = new_volume
            return (True, f"Music volume {new_volume}%")

        current = self.get_music_volume()
        if current is None:
            return (False, "Volume control unavailable")
        
        new_volume = max(0, current - amount)
        success = self.set_music_volume(new_volume)
        
        if success:
            return (True, f"Music volume {new_volume}%")
        return (False, "Failed to decrease volume")

