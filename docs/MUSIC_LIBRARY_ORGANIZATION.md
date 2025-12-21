# Music Library Organization

**Production-Tested Patterns for Pi-Sat Music Library**

---

## Real-World Example

Based on analysis of production playlist (`/home/dmitry/pi-sat/playlist/`):

```
playlist/
├── ABBA - Gimme! Gimme! Gimme! (A Man After Midnight) (SPOTISAVER).mp3
├── Air - Another Day (SPOTISAVER).mp3
├── Grand Corps Malade, Louane - Derrière le brouillard (SPOTISAVER).mp3
├── Imagine Dragons - Believer (SPOTISAVER).mp3
├── Kids United - On écrit sur les murs (SPOTISAVER).mp3
├── MIKA - Grace Kelly (SPOTISAVER).mp3
└── ... (38 files total, ~330MB)
```

**Characteristics:**
- **Format**: 320kbps MP3, ID3v2.3 tags, 44.1kHz stereo
- **Naming**: `Artist - Title (SOURCE).mp3`
- **Organization**: Flat directory (no subfolders)
- **Content**: Mixed languages (English, French), diverse genres
- **Special cases**: Featured artists, accented characters, punctuation

---

## Supported Library Structures

Pi-Sat supports multiple organization patterns (KISS principle - accept what users have):

### 1. Flat Directory (Production Example)

**Structure:**
```
~/Music/pisat/
├── ABBA - Gimme! Gimme! Gimme! (A Man After Midnight).mp3
├── The Beatles - Hey Jude.mp3
└── Frozen - Let It Go.mp3
```

**Pros:**
- Simple, no subfolder navigation
- Matches how music downloaders organize files
- Common for playlists exported from streaming services

**Cons:**
- Can become messy with large libraries (100s of files)
- Harder to browse manually

**Fuzzy Search Examples:**
- "Play ABBA" → finds "ABBA - Gimme! Gimme! Gimme!"
- "Play Gimme" → finds "ABBA - Gimme! Gimme! Gimme!"
- "Play Hey Jude" → finds "The Beatles - Hey Jude"

### 2. Artist Folders (Demo Library)

**Structure:**
```
~/Music/pisat/
├── Disney/
│   ├── Frozen - Let It Go.mp3
│   └── Frozen - Do You Want to Build a Snowman.mp3
├── The Beatles/
│   ├── The Beatles - Hey Jude.mp3
│   └── The Beatles - Let It Be.mp3
└── Kids Songs/
    └── Pinkfong - Baby Shark.mp3
```

**Pros:**
- Organized, easy to browse
- Natural for manually-organized libraries
- Groups related songs together

**Cons:**
- More directory structure to maintain
- User must decide on organization scheme

**Fuzzy Search Examples:**
- "Play Frozen" → finds files in Disney/ folder
- "Play Beatles" → finds files in The Beatles/ folder
- "Play Baby Shark" → finds file in Kids Songs/ folder

### 3. Album Folders (iTunes/Jellyfin Style)

**Structure:**
```
~/Music/pisat/
├── Disney/
│   ├── Frozen OST/
│   │   ├── 01 - Let It Go.mp3
│   │   └── 02 - Do You Want to Build a Snowman.mp3
│   └── Moana OST/
│       └── 01 - How Far I'll Go.mp3
└── The Beatles/
    ├── Hey Jude/
    │   └── 01 - Hey Jude.mp3
    └── Abbey Road/
        ├── 01 - Come Together.mp3
        └── 02 - Here Comes the Sun.mp3
```

**Pros:**
- Most organized, matches CD structure
- Good for complete album collections
- Preserves album context

**Cons:**
- Most complex structure
- Overkill for kids' playlists
- Requires strict organization

**Fuzzy Search Examples:**
- "Play Let It Go" → finds Frozen OST track
- "Play Abbey Road" → finds album in The Beatles/
- "Play Come Together" → finds file in Abbey Road/

---

## File Naming Best Practices

### Recommended Format

**Pattern**: `Artist - Title.mp3`

**Examples:**
```
The Beatles - Hey Jude.mp3
Frozen - Let It Go.mp3
MIKA - Grace Kelly.mp3
```

### Featured Artists

**Pattern**: `Artist, Featured Artist - Title.mp3`

**Examples:**
```
Grand Corps Malade, Louane - Derrière le brouillard.mp3
Kids United, Angelique Kidjo, Youssou N'Dour - Mama Africa.mp3
```

### Special Characters

**Supported:**
- Accented characters: `é è à ç ñ ü` (UTF-8 encoded)
- Punctuation: `! ? , . - '`
- Parentheses: `(remastered) [live] {acoustic}`

**Examples:**
```
Début De Soirée - Nuit de folie.mp3
Éric Serra - The Big Blue - Ouverture.mp3
```

### Avoid

- Non-standard characters: `/ \ : * ? " < > |` (filesystem conflicts)
- Leading/trailing spaces
- Double spaces
- Excessive punctuation: `!!!???`

---

## Fuzzy Search Behavior

Pi-Sat uses fuzzy matching (thefuzz library) with 50% similarity threshold.

### What Gets Matched

**File path components:**
```
~/Music/pisat/Disney/Frozen - Let It Go.mp3
              ^^^^^^ ^^^^^^^^^^^^^^^^^^^^^^^^
              folder      filename
```

**Searchable parts:**
1. Folder name: "Disney"
2. Artist: "Frozen"
3. Title: "Let It Go"
4. Full filename: "Frozen - Let It Go"

### Typo Tolerance Examples

| User says | Matches | Confidence |
|-----------|---------|------------|
| "Play Frozen" | "Frozen - Let It Go.mp3" | 100% |
| "Play frozzen" | "Frozen - Let It Go.mp3" | 52% |
| "Play let it" | "Frozen - Let It Go.mp3" | 75% |
| "Play Beatles" | "The Beatles - Hey Jude.mp3" | 100% |
| "Play beatles" | "The Beatles - Hey Jude.mp3" | 100% |
| "Play hey jood" | "The Beatles - Hey Jude.mp3" | 55% |

### Suffix Ignoring

Download sources often add suffixes - Pi-Sat ignores these:

| Filename | Search treats as |
|----------|------------------|
| `Song (SPOTISAVER).mp3` | `Song.mp3` |
| `Song (Official Video).mp3` | `Song.mp3` |
| `Song [Remastered].mp3` | `Song [Remastered].mp3`* |

*Square brackets are less common for download tags, kept in search.

---

## MPD Integration

### Database Updates

MPD scans the music library and builds a database:

```bash
# Manual update
mpc update

# Auto-update on startup (in ~/.mpd/mpd.conf)
auto_update "yes"
```

### Search Behavior

Pi-Sat searches MPD's file index:
1. Gets all files from MPD (`client.listall()`)
2. Extracts searchable names from file paths
3. Uses fuzzy matching to find best match
4. Returns file path to play

### Playlist Management

**Favorites playlist** (`~/.mpd/playlists/favorites.m3u`):

```m3u
#EXTM3U
Disney/Frozen - Let It Go.mp3
The Beatles/The Beatles - Hey Jude.mp3
Kids Songs/Pinkfong - Baby Shark.mp3
```

**Voice commands:**
- "Play my favorites" → loads favorites.m3u
- "I love this" → adds current song to favorites.m3u

---

## Migration from Streaming Services

### Spotify/YouTube Downloaders

Many users will have music from downloaders like **SpotiSaver**, **youtube-dl**, **yt-dlp**.

**Typical output:**
```
Artist - Title (SPOTISAVER).mp3
Artist - Title (Official Video).mp3
Artist - Title (Lyric Video).mp3
```

**Pi-Sat handling:**
- ✅ Fuzzy search ignores suffixes in parentheses
- ✅ Multiple versions of same song are distinguishable
- ✅ Filenames used as-is (no renaming required)

**Recommended cleanup** (optional):
```bash
# Remove (SPOTISAVER) suffix from filenames
cd ~/Music/pisat
for f in *\ \(SPOTISAVER\).mp3; do
  mv "$f" "${f% (SPOTISAVER).mp3}.mp3"
done
```

### iTunes/Apple Music

**Typical structure:**
```
~/Music/iTunes/
├── Artist Name/
│   └── Album Name/
│       ├── 01 Track Name.mp3
│       └── 02 Track Name.mp3
```

**Pi-Sat handling:**
- ✅ MPD indexes full directory tree
- ✅ Fuzzy search works on folder and file names
- ✅ Can copy entire iTunes library to `~/Music/pisat/`

**Migration:**
```bash
# Copy iTunes library to Pi-Sat
cp -r ~/Music/iTunes/* ~/Music/pisat/
mpc update
```

---

## USB Auto-Import (Planned Feature)

**Goal**: Plug in USB drive, automatically import new music.

**Workflow:**
1. User plugs in USB drive
2. Pi-Sat detects mount (udev rule)
3. Script scans USB for .mp3 files
4. Copies new files to `~/Music/pisat/`
5. Updates MPD database
6. Announces: "Found 12 new songs"

**See**: `scripts/usb_auto_import.sh` (to be implemented)

---

## Recommendations

### For Kids' Playlists (Primary Use Case)

**Best approach**: **Artist folders** (Demo library style)

**Reason:**
- Kids ask by movie/character: "Play Frozen"
- Natural grouping: Disney/, Kids Songs/
- Easy to add new songs to existing groups
- Visual browsing (file manager) still usable

**Example:**
```
~/Music/pisat/
├── Disney/
├── Kids Songs/
├── Classical/
└── Favorites/  # Manual curated folder
```

### For Adult/Mixed Libraries

**Best approach**: **Flat directory** OR **Artist folders**

**Reason:**
- Adult music requests more diverse: "Play ABBA", "Play that French song"
- Flat works well for < 200 songs
- Artist folders better for > 200 songs

---

## Testing Strategy

### Test Libraries

**Demo library** (`tests/demo_music/`):
- Artist folders structure
- 17 songs, 4 artists
- Silent MP3s with proper ID3 tags
- Used for MPD controller tests

**Production playlist** (`playlist/`):
- Flat directory structure
- 38 real songs, ~330MB
- Real-world naming patterns
- Used for fuzzy matching tests

### Fuzzy Search Test Cases

Test data (`tests/audio_samples/synthetic/fuzzy_matching/`):
- "Play frozzen" (typo in song name)
- "Play beatles" (missing "the")
- "Play favorits" (typo in "favorites")
- "Play hey jood" (typo in title)
- "Pley Frozen" (typo in command)

---

## KISS Principle Applied

**What we DON'T do:**
- ❌ Force users to reorganize their library
- ❌ Require specific naming format
- ❌ Validate ID3 tags
- ❌ Create complex database
- ❌ Transcode formats

**What we DO:**
- ✅ Accept any reasonable organization
- ✅ Use MPD's existing file indexing
- ✅ Fuzzy match on filenames (always present)
- ✅ Fall back to filename when ID3 missing
- ✅ Support MP3 (most common format)

**Result**: Pi-Sat works with the library you already have, no setup required.

---

*Last Updated: 2025-12-14*
