import pyaudio
import subprocess
from modules.logging_utils import setup_logger

logger = setup_logger(__name__)


def find_input_device_index(name_substring):
    if not name_substring:
        return None
    p = pyaudio.PyAudio()
    try:
        count = p.get_device_count()
        for i in range(count):
            info = p.get_device_info_by_index(i)
            if int(info.get("maxInputChannels", 0)) > 0:
                name = info.get("name", "")
                if name_substring.lower() in name.lower():
                    return i
    finally:
        p.terminate()
    return None


def find_output_device_index(name_substring):
    if not name_substring:
        return None
    p = pyaudio.PyAudio()
    try:
        count = p.get_device_count()
        for i in range(count):
            info = p.get_device_info_by_index(i)
            if int(info.get("maxOutputChannels", 0)) > 0:
                name = info.get("name", "")
                if name_substring.lower() in name.lower():
                    return i
    finally:
        p.terminate()
    return None


def list_devices():
    p = pyaudio.PyAudio()
    try:
        return [p.get_device_info_by_index(i) for i in range(p.get_device_count())]
    finally:
        p.terminate()


def list_alsa_devices():
    """List available ALSA playback devices using aplay -l"""
    try:
        result = subprocess.run(
            ['aplay', '-l'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            devices = []
            for line in result.stdout.split('\n'):
                if 'card' in line.lower() and 'device' in line.lower():
                    devices.append(line.strip())
            return devices
    except Exception as e:
        logger.debug(f"Failed to list ALSA devices: {e}")
    return []


def validate_alsa_device(device_name):
    """Validate that an ALSA device is available for playback
    
    Args:
        device_name: ALSA device name (e.g., 'default', 'plughw:0,0', 'hw:0,0')
        
    Returns:
        bool: True if device is valid and can be used for playback
    """
    if not device_name:
        return False
    
    try:
        # Test device by attempting to query it
        # Use aplay with --list-devices to check if device exists
        result = subprocess.run(
            ['aplay', '-D', device_name, '--list-devices'],
            capture_output=True,
            text=True,
            timeout=2
        )
        
        # If device is 'default', it should always be available
        if device_name == 'default':
            return True
        
        # For specific devices, check if they appear in aplay -l output
        if result.returncode == 0:
            return True
        
        # Also check if device appears in aplay -l
        alsa_devices = list_alsa_devices()
        device_lower = device_name.lower()
        for device in alsa_devices:
            if device_lower in device.lower() or any(
                f"card {i}" in device_lower or f"device {i}" in device_lower
                for i in range(10)
            ):
                return True
        
        return False
    except Exception as e:
        logger.debug(f"Failed to validate ALSA device {device_name}: {e}")
        return False


def get_default_alsa_device():
    """Get default ALSA playback device for RPi 5
    
    Returns:
        str: Default ALSA device name (e.g., 'default', 'plughw:0,0')
    """
    # Try common RPi 5 audio devices in order of preference
    candidates = ['default', 'plughw:0,0', 'hw:0,0', 'sysdefault']
    
    for device in candidates:
        if validate_alsa_device(device):
            logger.debug(f"Using ALSA device: {device}")
            return device
    
    # Fallback to 'default' if none validated
    logger.warning("Could not validate any ALSA device, using 'default'")
    return 'default'


