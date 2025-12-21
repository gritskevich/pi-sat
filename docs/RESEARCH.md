# Research Notes

Design decisions, technical research, and performance optimization notes for Pi-Sat.

**Quick Navigation:**
- [Fuzzy Matching Research](#fuzzy-matching-research)
- [MPD Best Practices](#mpd-best-practices)
- [Piper TTS Optimization](#piper-tts-optimization)
- [Hailo Integration](#hailo-integration)
- [Volume Control Strategy](#volume-control-strategy)
- [Future Considerations](#future-considerations)

---

## Fuzzy Matching Research

### Algorithm Selection
**Chosen:** `token_set_ratio` from thefuzz

**Why:**
- Handles extra words better than `token_sort_ratio`
- Example: "could you play frozen please" correctly matches "play frozen"
- Ignores word order differences
- More forgiving for natural speech patterns

**Alternatives Considered:**
- `token_sort_ratio`: Good, but struggles with extra words
- `partial_ratio`: Too permissive, many false positives
- `ratio`: Too strict, fails on word order changes
- **RapidFuzz**: Faster implementation, but thefuzz sufficient for <1000 songs

### Threshold Selection
**Intent Classification:** 50 (default, configurable)
- Balances accuracy vs coverage
- Lower threshold = more matches, more false positives
- Higher threshold = fewer matches, better accuracy

**Music Search:** 50-75 recommended
- 50: More forgiving for typos ("frozzen" → "Frozen")
- 75-85: Stricter matching, fewer false positives
- Can be adjusted per use case

### Priority System
**Critical for Intent Matching:**
```python
'sleep_timer': priority=20  # Check before 'stop'
'stop': priority=10
```

**Without priority:**
- "stop in 30 minutes" matches "stop" intent first
- Sleep timer never reached

**With priority:**
- Sleep timer checked first (higher priority)
- Correct intent classification

### Parameter Extraction
**Regex vs String Manipulation:**
- **Chosen:** Regex patterns
- More robust than naive string replacement
- Handles variations: "play the frozen soundtrack" vs "play frozen"
- Extracts structured data (duration numbers, query strings)

### Performance Benchmarks
| Library | Query Time | Notes |
|---------|-----------|-------|
| thefuzz | <1ms | Sufficient for <1000 songs |
| RapidFuzz | <0.1ms | 10× faster, migrate if library grows |

---

## MPD Best Practices

### Connection Management
**Pattern:** Persistent connection with reconnection decorator

**Why:**
- Faster than creating new connection per command
- Handles transient network issues automatically
- Cleaner code with decorator pattern

**Implementation:**
```python
def _reconnect_on_error(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception:
            self.connect()  # Reconnect once
            return func(self, *args, **kwargs)
    return wrapper
```

### Command Selection
**Search vs Find:**
- `find`: Exact match (case-sensitive)
- `search`: Substring match (case-insensitive)
- **Chosen:** Custom fuzzy search with thefuzz

**Why:**
- Better typo tolerance
- More natural for voice input
- Handles partial artist/song names

### Volume Control Detection
**Challenge:** MPD software volume may be disabled

**Solution:** Runtime detection
```python
status = client.status()
volume = status.get('volume')

if volume in (None, 'n/a', '-1'):
    # MPD volume disabled, use ALSA fallback
    use_alsa_volume()
else:
    # MPD software volume available
    use_mpd_volume()
```

### Idle/Event Pattern
**Not Used:** Real-time event monitoring

**Why:**
- Adds complexity
- Not needed for voice-only interface
- Polling on-demand is sufficient
- Could add later if GUI needed

---

## Piper TTS Optimization

### Model Selection
**Available Models:**
- `fr_FR-siwis-medium.onnx` (default)
- `en_US-lessac-medium.onnx`

**Why Medium:**
- Good balance of quality vs speed
- RTF 0.3 (3× faster than real-time)
- Small models sound robotic
- Large models too slow for real-time

### Output Format
**Chosen:** Raw PCM piped to aplay

**Why:**
- Fastest method (no file I/O)
- Direct pipeline: Piper → stdout → aplay → speaker
- No temporary files to manage

**Alternatives Considered:**
- WAV files: Slower (disk I/O), cleanup needed
- Socket streaming: Over-engineered for single-device use

### Performance
**Benchmark Results:**
- Generation: 0.3 RTF (Real-Time Factor)
- Example: 10-second speech generated in 3 seconds
- Total latency: <1 second for short responses

### Caching Strategy
**Not Implemented:** Pre-generated phrase caching

**Why:**
- Current performance sufficient
- Most responses are dynamic (song names)
- Adds complexity (cache invalidation, storage)
- Could add if latency becomes issue

**When to Add:**
- If RTF >0.7 (slower than real-time)
- If common phrases identified (>50% reuse)
- If storage space abundant

---

## Hailo Integration

### Model Variant Selection
**Chosen:** whisper-base

**Why:**
- Good balance accuracy vs speed
- 1-2 second inference time
- whisper-tiny: Faster but less accurate
- whisper-small/medium: Too slow for Hailo-8L

### Language Configuration
**Design:** Runtime language selection via config

**Implementation:**
- Language token injected at decoder start
- Token IDs: 50258 (start) + 50265 (French) or 50259 (English)
- Supports all Whisper languages: fr, en, es, de, it, etc.

**Why Runtime Config:**
- Easy language switching without model reload
- Single model supports multiple languages
- Configurable per deployment

### Resource Management
**Pattern:** Singleton with cleanup

**Why:**
- Only one Hailo pipeline instance allowed (hardware constraint)
- Prevents resource leaks
- Automatic retry on transient errors

### CPU Fallback
**Not Implemented:** CPU inference fallback

**Why:**
- Too slow for real-time (>10 seconds per command)
- Hailo device required for production
- Dev testing can use mock transcription

---

## Volume Control Strategy

### Separate Volume Tracks
**Design:** Independent music and TTS volumes

**Why:**
- Music may be loud, but TTS should be clear
- Different optimal levels (music: 50%, TTS: 80%)
- Prevents TTS being drowned out

**Implementation:**
- Music: MPD software volume or ALSA
- TTS: ALSA Master volume (temporary)
- VolumeManager saves/restores TTS level

### Volume Ducking
**Design:** Lower music during voice input

**Why:**
- Better microphone pickup
- Reduces echo/feedback
- Standard practice in voice assistants

**Settings:**
- Duck level: 20% (configurable)
- Restore: Always, even on errors (finally block)

### MPD vs ALSA
**Decision Tree:**
1. Try MPD software volume first (preferred)
2. If disabled, fall back to ALSA Master
3. Detect automatically on init

**Why MPD Preferred:**
- Software mixing (doesn't affect other audio)
- Per-client volume control
- Faster (no subprocess calls)

**Why ALSA Fallback:**
- Works when MPD volume disabled
- Hardware volume control
- System-wide (affects all audio)

---

## Future Considerations

### Performance Optimizations

**RapidFuzz Migration:**
- **When:** Music library >1000 songs
- **Why:** 10× faster than thefuzz
- **Effort:** Low (drop-in replacement)

**TTS Response Caching:**
- **When:** Latency >1 second or high phrase reuse
- **Why:** Eliminate generation time for common phrases
- **Effort:** Medium (cache management, storage)

**MPD Idle/Event:**
- **When:** Adding real-time GUI
- **Why:** Live status updates without polling
- **Effort:** Medium (event handling, state management)

### Feature Additions

**Multi-Room Audio:**
- Sync multiple Pi-Sat devices
- Coordinated playback
- Requires network communication layer

**Playlist Management:**
- Voice commands to create/edit playlists
- "Add this to my workout playlist"
- Requires persistent playlist storage

**Music Recommendations:**
- Simple algorithm (play count, favorites)
- "Play something I like"
- Requires usage tracking

**USB Auto-Import:**
- udev rule triggers music import
- Automatic MPD database update
- See INSTALL.md for setup

### Volume Improvements

**Independent ALSA Channels:**
- Use separate mixer channel for TTS
- True independent volume control
- Requires ALSA configuration

**Smooth Fade Algorithm:**
- Better sleep timer fade-out
- Logarithmic volume curve
- Perception-corrected steps

---

## Lessons Learned

### Architecture Decisions

**Protocol Interfaces (2025-12-14):**
- Enabled full testability without hardware
- Dependency injection via factory pattern
- Each module independently usable

**Singleton for Hailo:**
- Necessary due to hardware constraint
- Complicates testing (global state)
- Mitigated with cleanup methods

**Separate CommandProcessor:**
- Lifecycle (Orchestrator) vs Pipeline (CommandProcessor)
- Better separation of concerns
- Easier testing and maintenance

### Testing Insights

**Real Audio Testing:**
- Generated TTS audio more realistic than hand-recorded
- 80% accuracy achieved with Piper→Hailo roundtrip
- Language detection validated with real hardware

**Mocking Strategy:**
- Mock external dependencies (MPD, ALSA)
- Use real components when possible (Intent, VAD)
- Balance between realism and speed

### Performance Insights

**Latency Budget:**
- Total pipeline: 2-4 seconds (acceptable for voice assistant)
- Biggest contributor: Hailo STT (1-2s)
- Smallest: Intent classification (<1ms)

**Bottleneck Analysis:**
- Network: MPD commands <50ms (not a bottleneck)
- I/O: TTS generation 0.3 RTF (acceptable)
- Compute: Hailo STT dominates (hardware accelerated)

---

**See also:**
- [IMPLEMENTATION_PATTERNS.md](./IMPLEMENTATION_PATTERNS.md) - How patterns are implemented
- [TESTING.md](./TESTING.md) - How to validate research findings
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - When research doesn't match reality
