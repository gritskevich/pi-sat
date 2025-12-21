# Git History Cleanup Guide

**Current .git size:** 1.1GB
**Expected after cleanup:** ~50-100MB

## What Gets Removed from History

- All .wav files (test audio samples)
- All .mp3 files (music playlist)
- All .onnx files (TTS voice models)
- All .hef files (Hailo AI models)
- All .npy files (model weights)

## Quick Start (Automated)

```bash
# 1. Backup first!
cd /home/dmitry
cp -r pi-sat pi-sat-backup

# 2. Run cleanup script
cd pi-sat
./scripts/clean_git_history.sh

# 3. Re-add GitHub remote (filter-repo removes it)
git remote add origin https://github.com/YOUR_USERNAME/pi-sat.git

# 4. Force push (DESTRUCTIVE!)
git push origin --force --all
git push origin --force --tags
```

## Manual Method (git-filter-repo)

### Step 1: Backup
```bash
cd /home/dmitry
cp -r pi-sat pi-sat-backup
```

### Step 2: Install git-filter-repo
```bash
pip install git-filter-repo
```

### Step 3: Clean History
```bash
cd /home/dmitry/pi-sat

# Remove binary files from all history
git filter-repo --invert-paths \
  --path-glob '*.wav' \
  --path-glob '*.mp3' \
  --path-glob '*.onnx' \
  --path-glob '*.hef' \
  --path-glob '*.npy' \
  --force
```

### Step 4: Aggressive Cleanup
```bash
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

### Step 5: Check Size
```bash
du -sh .git
# Should be ~50-100MB instead of 1.1GB
```

### Step 6: Re-add Remote & Force Push
```bash
# Filter-repo removes remotes for safety
git remote add origin https://github.com/YOUR_USERNAME/pi-sat.git

# Force push (overwrites GitHub history)
git push origin --force --all
git push origin --force --tags
```

## Alternative: BFG Repo Cleaner

If git-filter-repo doesn't work:

```bash
# Install Java
sudo apt-get install default-jre

# Download BFG
wget https://repo1.maven.org/maven2/com/madgag/bfg/1.14.0/bfg-1.14.0.jar

# Run from outside repo
cd /home/dmitry
java -jar bfg-1.14.0.jar --delete-files '*.{wav,mp3,onnx,hef,npy}' pi-sat

# Clean up
cd pi-sat
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Force push
git push origin --force --all
```

## After Force Push

### For You
```bash
# Your local repo is clean, just continue working
git status
```

### For Collaborators
⚠️ **Everyone else must re-clone:**
```bash
# Delete old clone
rm -rf pi-sat

# Fresh clone
git clone https://github.com/YOUR_USERNAME/pi-sat.git
cd pi-sat

# Re-setup (see INSTALL.md)
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## What Gets Preserved

✅ All code and commit messages
✅ All branches and tags
✅ Full commit history (with SHAs changed)
✅ .gitignore already updated

## Expected Results

| Item | Before | After | Savings |
|------|--------|-------|---------|
| .git size | 1.1GB | ~50-100MB | ~1GB |
| Clone time | Minutes | Seconds | 95% faster |
| History | Clean | Clean | Same |

## Troubleshooting

### Remote not found
```bash
# Re-add remote
git remote add origin https://github.com/YOUR_USERNAME/pi-sat.git
```

### Push rejected
```bash
# Use --force (you've rewritten history)
git push origin --force --all
```

### Files still present locally
```bash
# That's normal! .gitignore prevents re-adding them
# They're only removed from git history, not disk
```

### Want to verify what will be removed
```bash
# List all .wav files in history
git log --all --pretty=format: --name-only | grep '\.wav$' | sort -u
```

## Rollback (If Needed)

If something goes wrong BEFORE force push:

```bash
# Restore from backup
cd /home/dmitry
rm -rf pi-sat
cp -r pi-sat-backup pi-sat
```

If you already force pushed:

```bash
# You'll need to force push the backup
cd /home/dmitry/pi-sat-backup
git push origin --force --all
```

## References

- [git-filter-repo docs](https://github.com/newren/git-filter-repo)
- [BFG Repo Cleaner](https://rtyley.github.io/bfg-repo-cleaner/)
- [GitHub: Removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
