# Project Optimization Checklist

**Date:** 2025-12-20
**Focus:** Documentation, code, repo cleanup

---

## Documentation (20 items)

### Immediate Cleanup
- [ ] 1. Archive `docs/CLEANUP_PATTERN.md` (352 lines) → Implementation complete, historical
- [ ] 2. Merge `docs/TTS_INTEGRATION.md` (187 lines) into IMPLEMENTATION_PATTERNS.md
- [ ] 3. Review IMPLEMENTATION_PATTERNS.md (841 lines) - split if >1000 lines
- [ ] 4. Remove redundant music search examples from multiple docs
- [ ] 5. Consolidate VAD documentation (scattered across 3 files)

### Structure
- [ ] 6. Move SCHEMA.md to README.md as visual overview section
- [ ] 7. Create docs/HARDWARE.md (extract from INSTALL.md + HAILO_STATUS.md)
- [ ] 8. Simplify docs/README.md (219 lines → <150 lines)
- [ ] 9. Update CHANGELOG.md - move detailed features to docs
- [ ] 10. Remove duplicate command examples (exist in CLAUDE.md + README.md)

### Content Optimization
- [ ] 11. TROUBLESHOOTING.md - remove solved historical issues
- [ ] 12. RESEARCH.md - archive old benchmark data
- [ ] 13. MUSIC_LIBRARY_ORGANIZATION.md - reduce to quick reference
- [ ] 14. HAILO_STATUS.md - split debug guide vs. status log
- [ ] 15. PHONETIC_SEARCH - merge architecture into IMPLEMENTATION_PATTERNS.md

### CLAUDE.md Optimization
- [ ] 16. Remove Phonetic Search section (306→200 lines, link to docs)
- [ ] 17. Collapse Multi-Language section (reduce examples)
- [ ] 18. Adaptive VAD section → link to TROUBLESHOOTING.md
- [ ] 19. Implementation Patterns → remove (already in docs/)
- [ ] 20. Target: 26KB → <20KB (30% reduction)

---

## Code (15 items)

### Module Cleanup
- [ ] 21. Remove unused imports (grep results show many)
- [ ] 22. Consolidate music_resolver.py + intent_engine.py music extraction
- [ ] 23. Review modules/interfaces.py - unused protocol methods?
- [ ] 24. Check factory.py - all modules integrated?
- [ ] 25. intent_engine.py (1073 lines) - split FR/EN patterns to separate files?

### Test Cleanup
- [ ] 26. Remove duplicate test audio samples
- [ ] 27. Archive old test patterns (tests/utils/)
- [ ] 28. Consolidate integration test fixtures
- [ ] 29. Review test_*.py - remove deprecated tests
- [ ] 30. pytest.ini - add coverage targets

### Script Cleanup
- [ ] 31. Remove scripts/test_*.py duplicates
- [ ] 32. Consolidate calibration scripts
- [ ] 33. player.py - extract common patterns to module
- [ ] 34. Benchmark scripts - archive old versions
- [ ] 35. speak.py - merge with piper_tts module?

---

## Repository (10 items)

### File Management
- [ ] 36. .gitignore - add __pycache__, *.pyc, .pytest_cache
- [ ] 37. Remove orphaned audio samples (>50MB)
- [ ] 38. Clean tests/audio_samples/integration/fr/ duplicates
- [ ] 39. Verify all symlinks are valid
- [ ] 40. Remove .DS_Store, .vscode/ if present

### Configuration
- [ ] 41. config.py - group related settings with comments
- [ ] 42. .envrc - document all overrides
- [ ] 43. requirements.txt - verify all deps needed
- [ ] 44. pi-sat.sh - remove unused commands
- [ ] 45. Bash completion - update for new commands

---

## Priority Actions (Top 10)

**High Impact:**
1. Archive CLEANUP_PATTERN.md
2. Reduce CLAUDE.md to <20KB (remove redundant sections)
3. Clean __pycache__ and *.pyc
4. .gitignore for cache files
5. Remove duplicate test audio (save 50MB+)

**Medium Impact:**
6. Merge TTS_INTEGRATION.md into IMPLEMENTATION_PATTERNS.md
7. Consolidate VAD documentation
8. Split intent_engine.py patterns to language files
9. Review unused imports
10. Archive old benchmark scripts

---

## Metrics

**Before:**
- Active docs: 17 files, 165KB
- CLAUDE.md: 26KB
- Test audio: ~150MB
- Cache files: 14K+

**Target:**
- Active docs: <15 files, <120KB (27% reduction)
- CLAUDE.md: <20KB (23% reduction)
- Test audio: <100MB (33% reduction)
- Cache files: 0 (clean repo)

---

## Automation

```bash
# Quick cleanup script
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete
find . -name ".DS_Store" -delete
find . -name "*.log" -mtime +30 -delete

# Size check
du -sh docs/ tests/audio_samples/ CLAUDE.md
wc -l docs/*.md
```

---

**Last Updated:** 2025-12-20
**Status:** Planning - execute in priority order
