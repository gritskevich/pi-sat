#!/bin/bash
# Clean Git History - Remove Large Binary Files
# WARNING: This rewrites git history and requires force push!

set -e

echo "⚠️  WARNING: This will rewrite git history!"
echo "⚠️  All commit SHAs will change!"
echo "⚠️  Requires force push to GitHub!"
echo ""
read -p "Have you backed up the repo? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Please backup first: cp -r pi-sat pi-sat-backup"
    exit 1
fi

echo ""
echo "Installing git-filter-repo..."
pip install git-filter-repo

echo ""
echo "Current .git size:"
du -sh .git

echo ""
echo "Removing large binary files from history..."

# Remove all large binary file types
git filter-repo --invert-paths \
  --path-glob '*.wav' \
  --path-glob '*.mp3' \
  --path-glob '*.onnx' \
  --path-glob '*.hef' \
  --path-glob '*.npy' \
  --force

echo ""
echo "Cleaning up..."
git reflog expire --expire=now --all
git gc --prune=now --aggressive

echo ""
echo "New .git size:"
du -sh .git

echo ""
echo "✅ History cleaned!"
echo ""
echo "Next steps:"
echo "1. Re-add your GitHub remote: git remote add origin <your-github-url>"
echo "2. Force push: git push origin --force --all"
echo "3. Force push tags: git push origin --force --tags"
echo "4. Tell collaborators to re-clone the repo"
