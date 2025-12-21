#!/bin/bash
# Start Fresh Git Repository
# Creates a clean repo without the 1.1GB history

set -e

echo "🚀 Pi-Sat Fresh Repository Creator"
echo "===================================="
echo ""
echo "This will:"
echo "  1. Backup current repo to pi-sat-old"
echo "  2. Create fresh git repo with current files"
echo "  3. Keep .git size small (~10MB instead of 1.1GB)"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

cd /home/dmitry

# 1. Backup old repo
echo ""
echo "📦 Step 1: Backing up current repo..."
if [ -d "pi-sat-old" ]; then
    echo "⚠️  pi-sat-old already exists!"
    read -p "Overwrite? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled. Please rename/remove pi-sat-old first."
        exit 1
    fi
    rm -rf pi-sat-old
fi
mv pi-sat pi-sat-old
echo "✅ Backup created: /home/dmitry/pi-sat-old"

# 2. Create fresh directory
echo ""
echo "🆕 Step 2: Creating fresh repository..."
mkdir pi-sat
cd pi-sat

# 3. Copy files (exclude git and generated content)
echo ""
echo "📋 Step 3: Copying files..."
rsync -av \
  --exclude='.git' \
  --exclude='venv/' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  --exclude='*.pyc' \
  --exclude='playlist/*.mp3' \
  --exclude='tests/audio_samples/_cache_tts/' \
  --exclude='tests/audio_samples/e2e_french/' \
  --exclude='tests/audio_samples/integration/' \
  --exclude='tests/audio_samples/language_tests/english/' \
  --exclude='tests/audio_samples/language_tests/french/' \
  --exclude='tests/audio_samples/language_tests/french_full/' \
  --exclude='tests/audio_samples/synthetic/' \
  --exclude='tests/audio_samples/commands/' \
  --exclude='resources/voices/*.onnx' \
  --exclude='hailo_examples/speech_recognition/app/hefs/' \
  --exclude='hailo_examples/speech_recognition/app/decoder_assets/' \
  ../pi-sat-old/ ./

# 4. Initialize fresh git
echo ""
echo "🎯 Step 4: Initializing git repository..."
git init
git add .

# 5. Create initial commit
echo ""
echo "💾 Step 5: Creating initial commit..."
git commit -m "Initial commit: Pi-Sat voice assistant v2.0

Pi-Sat: Local-first, offline voice-controlled music player for Raspberry Pi 5 + Hailo-8L

Features:
- Multi-language support (French/English)
- Hailo-8L accelerated STT (Whisper)
- Kid safety features (bedtime, time limits, alarms)
- Phonetic music search (90% accuracy)
- MPD music control with queue/repeat/shuffle
- Piper offline TTS
- 140+ tests, comprehensive documentation

Architecture:
- Zero cloud dependencies
- 100% on-device processing
- Protocol-based design with dependency injection
- Adaptive VAD with dual detection

This is a fresh repository start - large binaries excluded.
See .gitignore for excluded files and INSTALL.md for setup.

Previous history archived at: pi-sat-old (local backup)
"

# 6. Show results
echo ""
echo "✅ Fresh repository created!"
echo ""
echo "📊 Statistics:"
echo "  .git size: $(du -sh .git | cut -f1)"
echo "  Files tracked: $(git ls-files | wc -l)"
echo ""
echo "📁 Old repo backed up at:"
echo "  /home/dmitry/pi-sat-old"
echo ""
echo "🎯 Next steps:"
echo ""
echo "  1. On GitHub, rename old repo to 'pi-sat-archive' OR delete it"
echo "  2. Create new GitHub repo named 'pi-sat'"
echo "  3. Run these commands:"
echo ""
echo "     cd /home/dmitry/pi-sat"
echo "     git remote add origin https://github.com/YOUR_USERNAME/pi-sat.git"
echo "     git push -u origin main"
echo ""
echo "  4. Clone on other machines and setup per INSTALL.md"
echo ""
echo "🎉 Done! Your repo is now clean and lightweight!"
