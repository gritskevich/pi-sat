# Quick Performance Wins - Analysis

**Date:** 2025-12-19

## 🎯 Top 3 Improvements to Implement

### 1. **Reduce Model Reset Overhead** (Save 45-60ms)
**Current:** 5 predictions on silence after wake word detection
**Impact:** 5 × 15ms = **75ms wasted**
**Fix:** Reduce to 2 predictions
**Gain:** 45ms faster response

### 2. **Optimize STT First-Try** (Save retry overhead)
**Current:** Retry logic always prepared, imports in loop
**Impact:** Redundant imports, retry delay calculation
**Fix:** Move imports to top, simplify first attempt
**Gain:** Cleaner code, ~5ms faster

### 3. **Remove Unused Wake Sound** (Cleanup)
**Current:** wakesound.wav (21KB) unused (beep-instant.wav is default)
**Impact:** Disk space, confusion
**Fix:** Archive or remove old wake sound
**Gain:** Clean repo, clear defaults

---

## Implementation Plan

**Time:** 15 minutes
**Risk:** LOW
**Benefit:** 50ms faster + cleaner code
