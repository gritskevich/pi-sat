# Git Repository Cleanup Summary

**Date:** 2025-12-21
**Objective:** Reduce repository size by excluding large binary files and generated content

## Changes Made

### 1. Virtual Environments Excluded
**Added to .gitignore:**
- `venv/`
- `env/`
- `ENV/`
- `.venv/`

**Removed from git:**
- ~24,000 files from `venv/` directory

### 2. Music Library Excluded
**Added to .gitignore:**
- `playlist/`

**Removed from git:**
- 38 MP3 files (~330MB)
- User-specific music collection

**Documentation:**
- Created `playlist/README.md` with setup instructions

### 3. Generated Audio Samples Excluded
**Added to .gitignore:**
- `tests/audio_samples/_cache_tts/` - TTS cache
- `tests/audio_samples/e2e_french/` - Generated E2E tests
- `tests/audio_samples/integration/` - Generated integration tests
- `tests/audio_samples/language_tests/french_full/` - Full test suites
- `tests/audio_samples/language_tests/french_full_elevenlabs/` - ElevenLabs suite
- `tests/audio_samples/synthetic/` - Synthetic samples
- `tests/audio_samples/commands/` - Command samples

**Removed from git:**
- 50 .wav files (~2.4MB)
- All regenerable with scripts in `scripts/generate_*.py`

**Kept in git:**
- `tests/audio_samples/wake_word/` - Hand-crafted samples (essential)
- `tests/audio_samples/language_tests/english/` - Reference set (10 files)
- `tests/audio_samples/language_tests/french/` - Reference set (10 files)
- `tests/audio_samples/e2e/` - End-to-end reference (5 files)
- `tests/audio_samples/noise/` - Noise samples (1 file)
- `tests/audio_samples/stt/` - STT test samples (4 files)
- `resources/` - Essential sounds (beeps, wake sound)

**Documentation:**
- Created `tests/audio_samples/README.md` with regeneration instructions

### 4. Hailo Model Files Excluded
**Added to hailo_examples/speech_recognition/.gitignore:**
- `app/hefs/` - Hailo model files (464MB)
- `app/decoder_assets/` - Decoder assets (178MB)

**Removed from git:**
- 12 large model files (~642MB)
- Downloadable via `hailo_examples/speech_recognition/app/download_resources.sh`

### 5. TTS Voice Models Excluded
**Added to .gitignore:**
- `resources/voices/*.onnx` - Voice model files (2 × 61MB)
- `resources/voices/*.onnx.json` - Voice model metadata

**Removed from git:**
- 4 files (French + English voices, ~121MB)
- Downloadable from HuggingFace

**Documentation:**
- Created `resources/voices/README.md` with download instructions

## Summary Statistics

### Files Removed from Git Tracking
- **venv/**: ~24,000 files
- **playlist/**: 38 MP3 files (330MB)
- **Audio samples**: 50 .wav files (2.4MB)
- **Hailo models**: 12 files (642MB)
- **TTS voices**: 4 files (121MB)
- **Total size reduction**: ~1.1GB

### Files Kept in Git
- Essential audio samples: 49 .wav files (2.3MB)
- Code and documentation: All tracked
- Configuration files: All tracked
- Essential resources: beep sounds, wake sound

## Benefits

1. **Smaller repository**: ~1.1GB reduction in tracked files
2. **Faster clone/fetch**: Less data to transfer
3. **No binary bloat**: Git history stays clean
4. **Better for collaboration**: Smaller diffs, faster syncs
5. **User-specific content**: Each user can customize playlist and voice models

## Setup After Clone

After cloning the repository, users need to:

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Download TTS voice models (see resources/voices/README.md)
wget -O resources/voices/fr_FR-siwis-medium.onnx \
    https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx

# 3. Download Hailo models (if using Hailo STT)
cd hailo_examples/speech_recognition/app
./download_resources.sh

# 4. Generate test audio samples (optional)
python scripts/generate_language_test_audio.py
python scripts/generate_e2e_french_tests.py

# 5. Add music to playlist/
cp ~/Music/*.mp3 playlist/
```

See `INSTALL.md` for complete setup instructions.

## Cache Directories (Already Ignored)

These were already in .gitignore and properly excluded:
- `__pycache__/` - Python bytecode
- `.pytest_cache/` - Pytest cache
- `*.pyc` - Compiled Python files
- `debug_audio/` - Debug audio output

## Version Control Best Practices Applied

✅ No large binary files in repository
✅ No generated content in git
✅ No user-specific files (playlists, local config)
✅ No virtual environments
✅ Downloadable models excluded
✅ Documentation for regenerating excluded content

## Next Steps

Consider adding to future commits:
- Git LFS for any essential large files (if needed)
- Pre-commit hooks to prevent accidental binary commits
- CI/CD to auto-download models on deployment
