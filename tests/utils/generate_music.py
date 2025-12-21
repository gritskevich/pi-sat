"""
Demo Music Library Generator

Creates realistic demo music library for testing MPD integration.
Generates silent MP3 files with proper ID3 tags for metadata testing.
"""

import os
import sys
import subprocess
from pathlib import Path
import json



# Demo music library structure
DEMO_LIBRARY = {
    'French Pop': [
        {'title': 'maman', 'artist': 'Louane', 'album': 'Louane', 'duration': 210},
        {'title': 'Jour 1', 'artist': 'Louane', 'album': 'Louane', 'duration': 200},
        {'title': 'On écrit sur les murs', 'artist': 'Kids United', 'album': 'Kids United', 'duration': 210},
        {'title': 'Le lion est mort ce soir', 'artist': 'Kids United', 'album': 'Kids United', 'duration': 190},
        {'title': 'Alors on danse', 'artist': 'Stromae', 'album': 'Alors on danse', 'duration': 210},
        {'title': 'Magic in the Air', 'artist': 'Magic System', 'album': 'Magic System', 'duration': 200},
        {'title': 'Grace Kelly', 'artist': 'MIKA', 'album': 'Life in Cartoon Motion', 'duration': 190},
        {'title': 'Queen of Kings', 'artist': 'Alessandra', 'album': 'Queen of Kings', 'duration': 200},
    ],
    'Classical': [
        {'title': 'Für Elise', 'artist': 'Beethoven', 'album': 'Classical Favorites', 'duration': 180},
        {'title': 'Canon in D', 'artist': 'Pachelbel', 'album': 'Baroque', 'duration': 300},
        {'title': 'Moonlight Sonata', 'artist': 'Beethoven', 'album': 'Piano Sonatas', 'duration': 360},
    ],
}


def generate_silent_mp3(duration, output_path, metadata):
    """
    Generate silent MP3 with proper ID3 tags.

    Args:
        duration: Duration in seconds
        output_path: Output file path
        metadata: Dict with title, artist, album

    Returns:
        bool: True if successful
    """
    try:
        # Create silent audio using ffmpeg
        # Generate silence at 44.1kHz, 128kbps MP3
        cmd = [
            'ffmpeg',
            '-f', 'lavfi',
            '-i', f'anullsrc=r=44100:cl=mono',
            '-t', str(duration),
            '-c:a', 'libmp3lame',
            '-b:a', '128k',
            # Add ID3 tags
            '-metadata', f'title={metadata["title"]}',
            '-metadata', f'artist={metadata["artist"]}',
            '-metadata', f'album={metadata["album"]}',
            '-y',  # Overwrite
            output_path
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # Verify file was created
        if Path(output_path).exists() and Path(output_path).stat().st_size > 0:
            return True
        else:
            return False

    except subprocess.CalledProcessError as e:
        print(f"  ✗ ffmpeg error: {e.stderr}")
        return False
    except FileNotFoundError:
        print(f"  ✗ ffmpeg not found - install with: sudo apt-get install ffmpeg")
        return False
    except Exception as e:
        print(f"  ✗ Unexpected error: {e}")
        return False


def create_favorites_playlist(music_dir, songs):
    """
    Create favorites.m3u playlist.

    Args:
        music_dir: Music library root directory
        songs: List of song paths to include

    Returns:
        bool: True if successful
    """
    try:
        playlist_path = music_dir / 'favorites.m3u'

        with open(playlist_path, 'w') as f:
            f.write("#EXTM3U\n")

            for song in songs:
                # Make relative to music_dir
                rel_path = song.relative_to(music_dir)
                f.write(f"{rel_path}\n")

        print(f"\n✓ Created favorites playlist with {len(songs)} songs")
        return True

    except Exception as e:
        print(f"\n✗ Error creating playlist: {e}")
        return False


def generate_demo_library(output_dir=None):
    """
    Generate complete demo music library.

    Args:
        output_dir: Directory to create library (default: tests/demo_music/)

    Returns:
        dict: Statistics
    """
    if output_dir is None:
        output_dir = project_root / 'tests' / 'demo_music'

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating demo music library...")
    print(f"Output directory: {output_dir}")
    print()

    stats = {
        'total_songs': 0,
        'total_artists': len(DEMO_LIBRARY),
        'total_albums': 0,
        'total_duration': 0,
        'generated': 0,
        'failed': 0,
    }

    all_songs = []
    favorite_songs = []

    for artist_folder, songs in DEMO_LIBRARY.items():
        print(f"[{artist_folder}]")

        artist_dir = output_dir / artist_folder
        artist_dir.mkdir(exist_ok=True)

        albums = set()

        for i, song in enumerate(songs, 1):
            # Create filename
            filename = f"{song['artist']} - {song['title']}.mp3"
            output_path = artist_dir / filename

            print(f"  Generating: {song['title']} ({song['duration']}s)")

            success = generate_silent_mp3(
                duration=song['duration'],
                output_path=str(output_path),
                metadata=song
            )

            if success:
                size_kb = output_path.stat().st_size / 1024
                print(f"    ✓ Saved: {size_kb:.1f} KB")

                stats['generated'] += 1
                stats['total_duration'] += song['duration']
                albums.add(song['album'])
                all_songs.append(output_path)

                # Add first song from each artist to favorites
                if i == 1:
                    favorite_songs.append(output_path)

            else:
                print(f"    ✗ Failed")
                stats['failed'] += 1

        stats['total_songs'] += len(songs)
        stats['total_albums'] += len(albums)

        print()

    # Create favorites playlist
    if favorite_songs:
        create_favorites_playlist(output_dir, favorite_songs)

    # Create library manifest (JSON) for test reference
    manifest_path = output_dir / 'library_manifest.json'
    with open(manifest_path, 'w') as f:
        json.dump({
            'library': DEMO_LIBRARY,
            'stats': stats,
            'favorites': [str(p.relative_to(output_dir)) for p in favorite_songs]
        }, f, indent=2)

    print(f"✓ Created library manifest: {manifest_path}")

    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Songs:     {stats['generated']} / {stats['total_songs']} generated")
    print(f"Artists:   {stats['total_artists']}")
    print(f"Albums:    {stats['total_albums']}")
    print(f"Duration:  {stats['total_duration'] // 60:.0f} minutes {stats['total_duration'] % 60:.0f} seconds")
    print(f"Failed:    {stats['failed']}")
    print("=" * 60)

    return stats


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Generate demo music library')
    parser.add_argument(
        '--output-dir',
        default=None,
        help='Output directory (default: tests/demo_music/)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be generated without creating files'
    )

    args = parser.parse_args()

    if args.dry_run:
        print("DRY RUN - No files will be created\n")
        total_songs = sum(len(songs) for songs in DEMO_LIBRARY.values())
        total_duration = sum(
            song['duration']
            for songs in DEMO_LIBRARY.values()
            for song in songs
        )

        print(f"Would generate:")
        print(f"  Artists: {len(DEMO_LIBRARY)}")
        print(f"  Songs: {total_songs}")
        print(f"  Duration: {total_duration // 60} minutes")

        for artist, songs in DEMO_LIBRARY.items():
            print(f"\n{artist}:")
            for song in songs:
                print(f"  - {song['title']} ({song['duration']}s)")

        sys.exit(0)

    stats = generate_demo_library(output_dir=args.output_dir)

    if stats['failed'] == 0:
        print("\n✓ Demo library generated successfully!")
        sys.exit(0)
    else:
        print(f"\n✗ {stats['failed']} songs failed to generate")
        sys.exit(1)


if __name__ == '__main__':
    main()
