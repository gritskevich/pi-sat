#!/usr/bin/env python3
"""
Interactive MPD Player Control
Keyboard controls:
  ↑/↓    - Volume up/down
  ←/→    - Previous/Next song
  S      - Toggle shuffle
  ESC    - Exit
  Space  - Play/Pause
"""
import sys
import os
import time
import subprocess
import logging
from pathlib import Path

from modules.mpd_controller import MPDController

# Try to import keyboard library, fallback to getch
try:
    import keyboard
    USE_KEYBOARD = True
except ImportError:
    USE_KEYBOARD = False
    try:
        import termios
        import tty
        import select
        USE_TERMIOS = True
    except ImportError:
        USE_TERMIOS = False

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def get_alsa_volume():
    """Get ALSA Master volume percentage"""
    try:
        result = subprocess.run(
            ['amixer', 'get', 'Master'],
            capture_output=True,
            text=True,
            timeout=1
        )
        # Parse output like "Front Left: Playback 26304 [40%] [on]"
        for line in result.stdout.split('\n'):
            if '[' in line and '%' in line:
                # Extract percentage
                start = line.find('[') + 1
                end = line.find('%', start)
                if start > 0 and end > start:
                    return int(line[start:end])
        return None
    except Exception:
        return None


def set_alsa_volume(percent):
    """Set ALSA Master volume percentage (0-100)"""
    try:
        subprocess.run(
            ['amixer', 'set', 'Master', f'{percent}%'],
            capture_output=True,
            timeout=1
        )
        return True
    except Exception:
        return False


def getch():
    """Get a single character from stdin (Linux) - terminal must already be in raw mode"""
    if not USE_TERMIOS:
        return None
    
    try:
        ch = sys.stdin.read(1)
        # Handle escape sequences for arrow keys
        if ch == '\x1b':
            # In raw mode, arrow keys send: ESC [ A/B/C/D
            import fcntl
            fd = sys.stdin.fileno()
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            
            try:
                # Try to read the next 2 characters
                for i in range(2):
                    attempts = 0
                    while attempts < 20:
                        try:
                            ch2 = sys.stdin.read(1)
                            if ch2:
                                if i == 0 and ch2 == '[':
                                    continue
                                elif i == 1:
                                    if ch2 == 'A':
                                        return 'UP'
                                    elif ch2 == 'B':
                                        return 'DOWN'
                                    elif ch2 == 'C':
                                        return 'RIGHT'
                                    elif ch2 == 'D':
                                        return 'LEFT'
                                break
                        except (IOError, OSError):
                            time.sleep(0.005)
                            attempts += 1
                    if i == 0:
                        break
            finally:
                fcntl.fcntl(fd, fcntl.F_SETFL, flags)
            
            return 'ESC'
        elif ch == ' ':
            return 'SPACE'
        elif ch.lower() == 's':
            return 'S'
        elif ch == '\x03':
            return 'CTRL_C'
        return ch
    except Exception:
        return None


def format_time(seconds):
    """Format seconds as MM:SS"""
    if seconds == 'n/a':
        return '--:--'
    try:
        secs = int(float(seconds))
        mins = secs // 60
        secs = secs % 60
        return f"{mins:02d}:{secs:02d}"
    except:
        return '--:--'


def get_detailed_status(controller):
    """Get detailed MPD status"""
    try:
        with controller._ensure_connection():
            status = controller.client.status()
            current = controller.client.currentsong()
            
            elapsed = status.get('elapsed', '0')
            duration = current.get('time', '0')
            if duration == '0':
                duration = status.get('time', '0')
            
            # Try MPD volume first, fallback to ALSA
            volume_str = status.get('volume')
            volume = None
            if volume_str and volume_str not in ('n/a', '-1', None):
                try:
                    volume = int(volume_str)
                except (ValueError, TypeError):
                    pass
            
            # If MPD volume not available, use ALSA
            if volume is None:
                volume = get_alsa_volume()
            
            # Extract song name
            song_name = current.get('title') or current.get('name', '')
            if not song_name and 'file' in current:
                file_path = current['file']
                song_name = os.path.splitext(os.path.basename(file_path))[0]
            if not song_name:
                song_name = current.get('file', 'Unknown')
            
            # Extract artist
            artist_name = current.get('artist', 'Unknown')
            if artist_name == 'Unknown' and 'file' in current:
                file_path = current['file']
                filename = os.path.splitext(os.path.basename(file_path))[0]
                if ' - ' in filename:
                    artist_name = filename.split(' - ')[0]
            
            return {
                'state': status.get('state', 'stop'),
                'volume': volume,
                'song': song_name,
                'artist': artist_name,
                'elapsed': format_time(elapsed),
                'duration': format_time(duration),
                'random': status.get('random', '0') == '1',
                'repeat': status.get('repeat', '0') == '1',
            }
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return None


def display_status(status):
    """Display current player status"""
    if not status:
        print("\r" + " " * 80 + "\r", end='', flush=True)
        return
    
    state_icon = "▶" if status['state'] == 'play' else "⏸" if status['state'] == 'pause' else "⏹"
    shuffle_icon = "🔀" if status['random'] else "  "
    
    song = status['song'][:40] if len(status['song']) > 40 else status['song']
    artist = status['artist'][:30] if len(status['artist']) > 30 else status['artist']
    
    # Handle volume display
    if status['volume'] is not None:
        volume_str = f"{status['volume']:3d}%"
    else:
        volume_str = "N/A"
    
    line = f"{state_icon} [{volume_str:>4}] {shuffle_icon} {song} - {artist} [{status['elapsed']}/{status['duration']}]"
    print("\r" + line + " " * (80 - len(line)), end='', flush=True)


def handle_keyboard_input(controller):
    """Handle keyboard input using keyboard library"""
    import signal
    
    def signal_handler(sig, frame):
        print("\n\nStopping playback...")
        try:
            controller.stop()
        except:
            pass
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    def on_volume_up():
        volume_up(controller)
    
    def on_volume_down():
        volume_down(controller)
    
    def on_next():
        controller.next()
    
    def on_previous():
        controller.previous()
    
    def on_shuffle():
        with controller._ensure_connection():
            status = controller.client.status()
            current_random = status.get('random', '0') == '1'
            controller.client.random(0 if current_random else 1)
    
    def on_play_pause():
        status = controller.get_status()
        if status['state'] == 'play':
            controller.pause()
        else:
            controller.resume()
    
    def on_exit():
        signal_handler(None, None)
    
    keyboard.add_hotkey('up', on_volume_up)
    keyboard.add_hotkey('down', on_volume_down)
    keyboard.add_hotkey('right', on_next)
    keyboard.add_hotkey('left', on_previous)
    keyboard.add_hotkey('s', on_shuffle)
    keyboard.add_hotkey('space', on_play_pause)
    keyboard.add_hotkey('esc', on_exit)
    keyboard.add_hotkey('ctrl+c', on_exit)
    
    print("Interactive Player - Press ESC to exit")
    print("Controls: ↑↓ Volume | ←→ Next/Prev | S Shuffle | Space Play/Pause")
    print("=" * 80)
    
    try:
        while True:
            status = get_detailed_status(controller)
            display_status(status)
            time.sleep(0.5)
    except KeyboardInterrupt:
        signal_handler(None, None)


def volume_up(controller, amount=5):
    """Increase volume - try MPD first, fallback to ALSA"""
    try:
        with controller._ensure_connection():
            status = controller.client.status()
            volume_str = status.get('volume')
            if volume_str and volume_str not in ('n/a', '-1', None):
                # MPD volume available
                try:
                    current = int(volume_str)
                    new_volume = min(100, current + amount)
                    controller.client.setvol(new_volume)
                    return
                except (ValueError, TypeError):
                    pass
    except:
        pass
    
    # Fallback to ALSA
    current = get_alsa_volume()
    if current is not None:
        new_volume = min(100, current + amount)
        set_alsa_volume(new_volume)


def volume_down(controller, amount=5):
    """Decrease volume - try MPD first, fallback to ALSA"""
    try:
        with controller._ensure_connection():
            status = controller.client.status()
            volume_str = status.get('volume')
            if volume_str and volume_str not in ('n/a', '-1', None):
                # MPD volume available
                try:
                    current = int(volume_str)
                    new_volume = max(0, current - amount)
                    controller.client.setvol(new_volume)
                    return
                except (ValueError, TypeError):
                    pass
    except:
        pass
    
    # Fallback to ALSA
    current = get_alsa_volume()
    if current is not None:
        new_volume = max(0, current - amount)
        set_alsa_volume(new_volume)


def handle_getch_input(controller):
    """Handle keyboard input using getch (termios)"""
    import signal
    
    def signal_handler(sig, frame):
        print("\n\nStopping playback...")
        try:
            controller.stop()
        except:
            pass
        # Restore terminal
        if USE_TERMIOS:
            fd = sys.stdin.fileno()
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_terminal_settings)
            except:
                pass
        sys.exit(0)
    
    # Save terminal settings
    old_terminal_settings = None
    if USE_TERMIOS:
        fd = sys.stdin.fileno()
        old_terminal_settings = termios.tcgetattr(fd)
        tty.setraw(fd)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    print("Interactive Player - Press ESC to exit")
    print("Controls: ↑↓ Volume | ←→ Next/Prev | S Shuffle | Space Play/Pause")
    print("=" * 80)
    
    try:
        while True:
            status = get_detailed_status(controller)
            display_status(status)
            
            if USE_TERMIOS:
                ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                if ready:
                    try:
                        ch = sys.stdin.read(1)
                        key = None
                        
                        if ch == '\x1b':
                            # Escape sequence - read more characters
                            import fcntl
                            fd = sys.stdin.fileno()
                            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
                            fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
                            
                            try:
                                # Read the next 2 characters with timeout
                                ch2 = None
                                ch3 = None
                                start = time.time()
                                
                                # Read '['
                                while time.time() - start < 0.1:
                                    try:
                                        ch2 = sys.stdin.read(1)
                                        if ch2:
                                            break
                                    except (IOError, OSError):
                                        time.sleep(0.01)
                                
                                # If we got '[', read direction
                                if ch2 == '[':
                                    start = time.time()
                                    while time.time() - start < 0.1:
                                        try:
                                            ch3 = sys.stdin.read(1)
                                            if ch3:
                                                break
                                        except (IOError, OSError):
                                            time.sleep(0.01)
                                    
                                    if ch3 == 'A':
                                        key = 'UP'
                                    elif ch3 == 'B':
                                        key = 'DOWN'
                                    elif ch3 == 'C':
                                        key = 'RIGHT'
                                    elif ch3 == 'D':
                                        key = 'LEFT'
                                    else:
                                        # Unknown escape sequence, ignore
                                        key = None
                                else:
                                    # ESC without proper sequence, treat as ESC key
                                    key = 'ESC'
                            finally:
                                fcntl.fcntl(fd, fcntl.F_SETFL, flags)
                        elif ch == ' ':
                            key = 'SPACE'
                        elif ch.lower() == 's':
                            key = 'S'
                        elif ch == '\x03':
                            key = 'CTRL_C'
                        else:
                            # Ignore other characters
                            continue
                        
                        # Process key if we got one
                        if key is None:
                            continue
                        
                        if key == 'UP':
                            volume_up(controller, 5)
                        elif key == 'DOWN':
                            volume_down(controller, 5)
                        elif key == 'RIGHT':
                            try:
                                status = controller.get_status()
                                if status['state'] == 'stop':
                                    controller.play()
                                else:
                                    result = controller.next()
                                    if not result[0] and "end of playlist" in result[1].lower():
                                        with controller._ensure_connection():
                                            controller.client.play(0)
                            except Exception as e:
                                logger.error(f"Next error: {e}")
                                try:
                                    status = controller.get_status()
                                    if status['state'] == 'stop':
                                        controller.play()
                                except:
                                    pass
                        elif key == 'LEFT':
                            try:
                                status = controller.get_status()
                                if status['state'] == 'stop':
                                    controller.play()
                                else:
                                    result = controller.previous()
                                    if not result[0] and "start of playlist" in result[1].lower():
                                        with controller._ensure_connection():
                                            playlist_info = controller.client.playlistinfo()
                                            if playlist_info:
                                                controller.client.play(len(playlist_info) - 1)
                            except Exception as e:
                                logger.error(f"Previous error: {e}")
                                try:
                                    status = controller.get_status()
                                    if status['state'] == 'stop':
                                        controller.play()
                                except:
                                    pass
                        elif key == 'S' or key == 's':
                            try:
                                with controller._ensure_connection():
                                    status = controller.client.status()
                                    current_random = status.get('random', '0') == '1'
                                    controller.client.random(0 if current_random else 1)
                            except:
                                pass
                        elif key == 'SPACE':
                            try:
                                status = controller.get_status()
                                if status['state'] == 'play':
                                    controller.pause()
                                else:
                                    controller.resume()
                            except:
                                pass
                        elif key == 'ESC':
                            try:
                                controller.stop()
                            except:
                                pass
                            break
                        elif key == 'CTRL_C':
                            signal_handler(None, None)
                    except Exception as e:
                        # Log but don't exit - just continue the loop
                        logger.error(f"Input handling error: {e}")
                        pass
            else:
                time.sleep(0.5)
    except KeyboardInterrupt:
        signal_handler(None, None)
    except Exception as e:
        logger.error(f"Main loop error: {e}")
        try:
            controller.stop()
        except:
            pass
    finally:
        if USE_TERMIOS and old_terminal_settings:
            try:
                fd = sys.stdin.fileno()
                termios.tcsetattr(fd, termios.TCSADRAIN, old_terminal_settings)
            except:
                pass
        print("\n")


def main():
    """Main function"""
    try:
        controller = MPDController(debug=False)
    except Exception as e:
        print(f"❌ Failed to initialize MPD controller: {e}")
        return 1
    
    if not controller.connect():
        print("❌ Failed to connect to MPD")
        print("   Make sure MPD is running")
        return 1
    
    try:
        with controller._ensure_connection():
            playlist_info = controller.client.playlistinfo()
            if not playlist_info:
                print("⚠️  No playlist loaded. Load a playlist first.")
                print("   Example: python3 scripts/test_playlist.py")
                return 1
    except Exception as e:
        print(f"⚠️  Could not check playlist: {e}")
        return 1
    
    try:
        status = controller.get_status()
        if status['state'] == 'stop':
            controller.play()
    except Exception as e:
        print(f"⚠️  Could not start playback: {e}")
        print("   Try updating MPD database: mpc update")
        print("   Or load a fresh playlist")
    
    try:
        if USE_KEYBOARD:
            handle_keyboard_input(controller)
        else:
            if not USE_TERMIOS:
                print("⚠️  Keyboard library not available. Install with: pip install keyboard")
                print("   Or use on Linux with termios support")
                return 1
            handle_getch_input(controller)
    except KeyboardInterrupt:
        print("\n\nStopping playback...")
        try:
            controller.stop()
        except:
            pass
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}")
        try:
            controller.stop()
        except:
            pass
        return 1
    
    print("Player stopped.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
