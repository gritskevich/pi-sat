# Start Fresh Repository Guide

**Simplest solution:** Create new repo with clean history, no large files.

## Why Start Fresh?

✅ **Much simpler** than rewriting history
✅ **Clean slate** - no baggage
✅ **Small repo** from day one (~10MB vs 1.1GB)
✅ **No force push** drama
✅ **No broken clones**

## Quick Steps

### 1. Prepare Current Repo

```bash
cd /home/dmitry/pi-sat

# Commit current cleanup work
git add .
git commit -m "Clean up: exclude large binaries from git"

# Note your current GitHub URL
git remote get-url origin
# Save this URL - you'll need it
```

### 2. Create Fresh Local Repo

```bash
# Rename old repo (keep as backup)
cd /home/dmitry
mv pi-sat pi-sat-old

# Create fresh directory with clean files
mkdir pi-sat
cd pi-sat

# Copy everything EXCEPT .git
rsync -av --exclude='.git' ../pi-sat-old/ ./

# Initialize fresh git repo
git init
git add .
git commit -m "Initial commit: Pi-Sat voice assistant v2.0

- Multi-language support (French/English)
- Hailo-8L STT acceleration
- Kid safety features
- Phonetic music search
- Large binaries excluded (see .gitignore)"
```

### 3. Create New GitHub Repo

**Option A: Rename old repo on GitHub**
1. Go to old repo settings on GitHub
2. Rename it to `pi-sat-archive` or `pi-sat-old`
3. Create new repo named `pi-sat`

**Option B: Delete old repo** (if you don't care about old history)
1. Go to old repo settings on GitHub
2. Delete repository
3. Create new repo named `pi-sat`

### 4. Push Fresh Repo

```bash
cd /home/dmitry/pi-sat

# Add GitHub remote
git remote add origin https://github.com/YOUR_USERNAME/pi-sat.git

# Push clean repo
git push -u origin main
```

### 5. Verify

```bash
# Check .git size
du -sh .git
# Should be ~10-50MB instead of 1.1GB

# Check what's tracked
git ls-files | wc -l
# Should be reasonable number

# Verify no large files
git ls-files | xargs du -h | sort -h | tail -20
```

## Comparison

| Method | Complexity | Time | Result |
|--------|------------|------|--------|
| **Start Fresh** | ⭐ Easy | 5 min | Clean, simple |
| Rewrite History | ⭐⭐⭐ Hard | 30 min | Complex, risky |

## What You Lose

❌ **Old commit history** - but do you really need it?
  - Current code is what matters
  - Can keep old repo as archive

## What You Keep

✅ **All current code**
✅ **All documentation**
✅ **All configuration**
✅ **Working state**
✅ **Can reference old repo if needed**

## One-Command Script

```bash
#!/bin/bash
# Quick fresh start script

# 1. Backup
cd /home/dmitry
cp -r pi-sat pi-sat-old-backup

# 2. Create fresh
mkdir pi-sat-fresh
cd pi-sat-fresh
rsync -av --exclude='.git' --exclude='venv' --exclude='playlist' ../pi-sat/ ./

# 3. Init
git init
git add .
git commit -m "Initial commit: Pi-Sat v2.0 - clean slate"

# 4. Ready to push
echo ""
echo "✅ Fresh repo ready!"
echo ""
echo "Next steps:"
echo "1. Create new repo on GitHub: pi-sat"
echo "2. git remote add origin https://github.com/YOUR_USERNAME/pi-sat.git"
echo "3. git push -u origin main"
echo ""
echo "Old repo backed up at: /home/dmitry/pi-sat-old-backup"
```

## Recommended Approach

**I recommend starting fresh because:**
1. ⏱️ **Saves time** - 5 minutes vs 30+ minutes
2. 🧹 **Cleaner** - no history baggage
3. 🛡️ **Safer** - no force push risks
4. 📦 **Smaller** - 10MB vs 1.1GB
5. 🎯 **Simpler** - one command vs complex rewriting

## If You Want Old History

Keep `pi-sat-old` repo locally:
- All history preserved
- Can reference commits
- Can cherry-pick if needed
- Rename on GitHub to `pi-sat-archive`

## Next Steps After Fresh Start

```bash
# Clone on other machines
git clone https://github.com/YOUR_USERNAME/pi-sat.git
cd pi-sat

# Setup (from INSTALL.md)
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Download models
wget -O resources/voices/fr_FR-siwis-medium.onnx ...
cd hailo_examples/speech_recognition/app && ./download_resources.sh

# Add music
cp ~/Music/*.mp3 playlist/

# Run
./pi-sat.sh run
```

Ready to start fresh! 🚀
