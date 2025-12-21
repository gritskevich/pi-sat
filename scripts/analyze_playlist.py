#!/usr/bin/env python3
"""
Analyze playlist folder - check files, sizes, formats, issues
"""
import os
import subprocess
from pathlib import Path

def analyze_playlist():
    """Analyze files in playlist folder"""
    playlist_dir = Path(__file__).parent.parent / "playlist"
    
    if not playlist_dir.exists():
        print(f"❌ Playlist directory not found: {playlist_dir}")
        return
    
    mp3_files = list(playlist_dir.glob("*.mp3"))
    
    print("=" * 80)
    print("Playlist Analysis")
    print("=" * 80)
    print(f"\n📁 Directory: {playlist_dir}")
    print(f"📊 Total files: {len(mp3_files)}")
    
    # Calculate total size
    total_size = sum(f.stat().st_size for f in mp3_files)
    print(f"💾 Total size: {total_size / (1024*1024):.1f} MB")
    
    # Check file types
    print(f"\n🔍 File Analysis:")
    valid_files = 0
    invalid_files = 0
    empty_files = 0
    large_files = []
    small_files = []
    
    for mp3_file in sorted(mp3_files):
        size = mp3_file.stat().st_size
        size_mb = size / (1024*1024)
        
        # Check if empty
        if size == 0:
            empty_files.append(mp3_file.name)
            invalid_files += 1
            continue
        
        # Check file type
        try:
            result = subprocess.run(
                ['file', str(mp3_file)],
                capture_output=True,
                text=True,
                timeout=5
            )
            if 'MPEG' in result.stdout or 'Audio' in result.stdout:
                valid_files += 1
            else:
                invalid_files += 1
                print(f"  ⚠️  {mp3_file.name}: {result.stdout.strip()}")
        except Exception as e:
            print(f"  ⚠️  {mp3_file.name}: Could not check ({e})")
            invalid_files += 1
        
        # Track large/small files
        if size_mb > 15:
            large_files.append((mp3_file.name, size_mb))
        elif size_mb < 2:
            small_files.append((mp3_file.name, size_mb))
    
    print(f"\n✅ Valid MP3 files: {valid_files}")
    if invalid_files > 0:
        print(f"❌ Invalid/empty files: {invalid_files}")
    if empty_files:
        print(f"  Empty files: {', '.join(empty_files)}")
    
    if large_files:
        print(f"\n📦 Large files (>15 MB):")
        for name, size in large_files:
            print(f"  - {name}: {size:.1f} MB")
    
    if small_files:
        print(f"\n📦 Small files (<2 MB):")
        for name, size in small_files:
            print(f"  - {name}: {size:.1f} MB")
    
    # Check for special characters in filenames
    print(f"\n🔤 Filename Analysis:")
    special_chars = []
    long_names = []
    for mp3_file in mp3_files:
        name = mp3_file.name
        if len(name) > 80:
            long_names.append(name)
        # Check for problematic characters
        if any(c in name for c in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']):
            special_chars.append(name)
    
    if special_chars:
        print(f"  ⚠️  Files with problematic characters: {len(special_chars)}")
        for name in special_chars[:5]:
            print(f"    - {name}")
    
    if long_names:
        print(f"  ⚠️  Very long filenames (>80 chars): {len(long_names)}")
        for name in long_names[:3]:
            print(f"    - {name[:60]}...")
    
    # Summary
    print(f"\n" + "=" * 80)
    print("Summary:")
    print(f"  ✅ Ready to play: {valid_files} files")
    if invalid_files > 0:
        print(f"  ⚠️  Issues found: {invalid_files} files")
    print("=" * 80)

if __name__ == '__main__':
    analyze_playlist()

