# Pi-Sat Version Status

**Last Updated:** 2025-12-20

## Summary

| Component | Current | Latest | Action | Reason |
|-----------|---------|--------|--------|--------|
| **Python Dependencies** | | | | |
| torch | 2.6.0 | **2.9.1** | ✅ **Updated** | Latest stable |
| transformers | 4.50.1 | **4.57.3** | ✅ **Updated** | Latest stable |
| openwakeword | 0.6.0 | 0.6.0 | ✅ Current | Latest available |
| faster-whisper | 1.2.1 | 1.2.1 | ✅ Current | Latest available |
| **System Components** | | | | |
| Piper TTS | 1.2.0 | 1.3.0 | ⚠️ **Keep** | Breaking changes (see below) |
| HailoRT | 4.20.0 | 4.23.0 | ⚠️ **Keep** | Stability issues (see below) |
| Hailo Speech Code | Custom | Dec 2025 | ✅ **Keep** | No new features |

## Detailed Recommendations

### ✅ Updated (2025-12-20)

**torch: 2.6.0 → 2.9.1**
- Latest stable release (Nov 2025)
- Performance improvements
- Compatible with current code

**transformers: 4.50.1 → 4.57.3**
- Latest stable release (Nov 2025)
- v5.0.0rc available but not recommended (RC)

### ⚠️ Keep Current Version

#### Piper TTS (1.2.0)

**Don't update to 1.3.0 because:**
- Breaking CLI changes: `piper --model` → `python3 -m piper -m`
- Removed C++ binary (Python-only now)
- License changed: MIT → GPLv3
- Current setup works perfectly via shell pipeline

**New features in 1.3.0 (not critical):**
- `--volume` flag (already handled by VolumeManager)
- Phoneme support `[[ phonemes ]]`
- Direct playback via ffplay

**Migration required if updating:**
```bash
# Current (1.2.0)
echo "text" | piper --model model.onnx --output-raw | aplay

# New (1.3.0)
python3 -m piper -m voice_name --volume 1.0 -- "text"
```

#### HailoRT (4.20.0)

**Don't update to 4.21-4.23 because:**
- Version mismatch issues reported in community
- 4.20.0 marked "oldstable" (proven stable)
- Driver/library/firmware conflicts in newer versions
- Current setup: zero issues, working perfectly

**Your customizations:**
- Multi-language support added (Dec 15, 2024)
- Official repo lacks this feature
- Recent updates are docs-only, no code improvements

**Installed:**
```
hailo-all               4.20.0
hailort                 4.20.0-1
hailofw                 4.20.0-1
python3-hailort         4.20.0-1
Device: Hailo-8L, Firmware: 4.20.0 ✅
```

## When to Update

**Piper TTS:**
- Only if you need new features (volume control, phonemes)
- Requires code refactoring in `modules/piper_tts.py`

**HailoRT:**
- Wait for 4.24+ with confirmed RPi5 stability
- Only if official repo adds critical features
- Only if you encounter bugs in current version

## Version Check Commands

```bash
# Python packages
python -c "import torch; print(f'torch: {torch.__version__}')"
python -c "import transformers; print(f'transformers: {transformers.__version__}')"

# Piper
/usr/local/bin/piper --version

# Hailo
hailortcli fw-control identify
dpkg -l | grep hailo
```

## References

- [PyTorch Releases](https://github.com/pytorch/pytorch/releases)
- [Transformers Releases](https://github.com/huggingface/transformers/releases)
- [Piper v1.3.0](https://github.com/OHF-Voice/piper1-gpl/releases/tag/v1.3.0)
- [Hailo Application Examples](https://github.com/hailo-ai/Hailo-Application-Code-Examples)
- [HailoRT Compatibility Issues](https://forums.raspberrypi.com/viewtopic.php?t=385489)

---

**Next Review:** After significant version releases or if issues arise
