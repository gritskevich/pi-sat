#!/usr/bin/env python3
"""
Test script to play from MPD playlist in pi-sat folder
"""
import sys
import logging
import os
from pathlib import Path

from modules.mpd_controller import MPDController

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def create_playlist_from_folder(playlist_folder, output_m3u):
    """Create M3U playlist from MP3 files in folder"""
    playlist_path = project_root / playlist_folder
    if not playlist_path.exists():
        return False
    
    mp3_files = sorted(playlist_path.glob("*.mp3"))
    if not mp3_files:
        return False
    
    with open(output_m3u, 'w') as f:
        f.write("#EXTM3U\n")
        for mp3_file in mp3_files:
            # Relative path from music library root
            rel_path = f"{playlist_folder}/{mp3_file.name}"
            f.write(f"{rel_path}\n")
    
    return True

def load_local_playlist(controller, playlist_path):
    """Load and play a local M3U playlist file"""
    playlist_path = Path(playlist_path)
    if not playlist_path.exists():
        return False, f"Playlist file not found: {playlist_path}"
    
    try:
        with controller._ensure_connection():
            # Read playlist file
            files_to_add = []
            with open(playlist_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        files_to_add.append(line)
            
            if not files_to_add:
                return False, "Playlist file is empty"
            
            # Clear current playlist and add files
            controller.client.clear()
            added_count = 0
            for file_path in files_to_add:
                try:
                    controller.client.add(file_path)
                    added_count += 1
                except Exception as e:
                    logger.warning(f"Could not add {file_path}: {e}")
            
            if added_count == 0:
                return False, "No files could be added to playlist"
            
            # Start playing
            controller.client.play()
            return True, f"Playing {added_count} tracks from {playlist_path.name}"
            
    except Exception as e:
        return False, f"Error loading playlist: {e}"

def main():
    print("=" * 60)
    print("MPD Playlist Test - Pi-Sat Folder")
    print("=" * 60)
    
    # Initialize controller
    try:
        controller = MPDController(debug=True)
    except Exception as e:
        print(f"❌ Failed to initialize MPD controller: {e}")
        return 1
    
    # Connect to MPD
    print("\n1. Connecting to MPD...")
    if not controller.connect():
        print("❌ Failed to connect to MPD")
        print("   Make sure MPD is running")
        return 1
    print("✓ Connected to MPD")
    
    # Check for playlist folder
    playlist_folder = project_root / "playlist"
    playlist_m3u = project_root / "playlist.m3u"
    
    print(f"\n2. Checking for playlist in pi-sat folder...")
    print(f"   Playlist folder: {playlist_folder}")
    print(f"   Playlist file: {playlist_m3u}")
    
    # Try to find or create playlist
    playlist_to_load = None
    
    if playlist_m3u.exists():
        print(f"   ✓ Found playlist file: {playlist_m3u.name}")
        playlist_to_load = playlist_m3u
    elif playlist_folder.exists():
        print(f"   ✓ Found playlist folder with MP3 files")
        # Create M3U from folder
        if create_playlist_from_folder("playlist", playlist_m3u):
            print(f"   ✓ Created playlist.m3u from folder")
            playlist_to_load = playlist_m3u
        else:
            print(f"   ⚠️  Could not create playlist from folder")
    else:
        print(f"   ❌ No playlist found in pi-sat folder")
        return 1
    
    # Load and play the playlist
    if playlist_to_load:
        print(f"\n3. Loading playlist: {playlist_to_load.name}...")
        success, message = load_local_playlist(controller, playlist_to_load)
        if success:
            print(f"   ✓ {message}")
        else:
            print(f"   ❌ {message}")
            return 1
    
    # Show status
    print("\n4. Current status...")
    try:
        status = controller.get_status()
        print(f"   State: {status['state']}")
        print(f"   Volume: {status['volume']}%")
        if status['state'] == 'play':
            print(f"   Now playing: {status['song']} by {status['artist']}")
            
            # Show playlist info
            with controller._ensure_connection():
                playlist_info = controller.client.playlistinfo()
                print(f"   Playlist: {len(playlist_info)} tracks")
                if len(playlist_info) > 0:
                    print(f"   First track: {playlist_info[0].get('title', 'Unknown')}")
    except Exception as e:
        print(f"   ⚠️  Could not get status: {e}")
    
    print("\n" + "=" * 60)
    print("Test complete")
    print("=" * 60)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
