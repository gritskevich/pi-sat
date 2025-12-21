# Benchmark Architecture Decision

## TL;DR: Keep as Single File ✅

**Decision**: Don't split `benchmark_stt.py`
**Reason**: It's a TOOL, not a library - monolithic is KISS-optimal
**Optimization**: Added `--quick` mode for fast iteration

---

## The Challenge

> "Let's split the main file into 2: 'prod' and 'test'. Find best practice examples, do a DRY part, optimise. I think one huge runner is overkill. Or not? Challenge me. Stay KISS and minimalist."

## Analysis Results

### Current State
```
File: scripts/benchmark_stt.py (511 lines)

Code Distribution:
  STTBenchmark (orchestrator)    : 195 lines (38%)
  CLI/main (argparse)            :  76 lines (15%)
  NativeWhisperEngine            :  70 lines (14%)
  HailoWhisperEngine             :  48 lines ( 9%)
  ResourceMonitor                :  41 lines ( 8%)
  BenchmarkResult (dataclass)    :  23 lines ( 5%)
  Imports/helpers                :  58 lines (11%)
```

### DRY Check
✅ **No duplication found**
- Engine wrappers: Benchmark-specific, not reused
- ResourceMonitor: Only used here (no other scripts)
- Core logic: Single purpose, no repetition

### Cohesion Check
✅ **Highly cohesive**
- Single responsibility: Benchmark STT engines
- All components serve this one purpose
- Clear separation of concerns within file

### Size Check
✅ **511 lines is reasonable for a tool**
- Linux `ls`: 5,000+ lines
- Git commands: 2,000+ lines average
- Our benchmark: 511 lines (SMALL!)

---

## Best Practice: Tool vs Library

### Library Pattern (modules/)
```
modules/hailo_stt.py          ← Production code
modules/intent_engine.py      ← Reusable components
modules/mpd_controller.py     ← Modular, minimal
```

**Requirements**:
- ✅ Minimal, focused
- ✅ Reusable across codebase
- ✅ Split into logical components
- ✅ Clean interfaces

### Tool Pattern (scripts/)
```
scripts/benchmark_stt.py      ← Benchmark tool
scripts/calibrate_vad.py      ← Calibration tool
scripts/player.py             ← Interactive player
```

**Allowed**:
- ✅ Can be comprehensive
- ✅ Can be monolithic
- ✅ Single-purpose utility
- ✅ Self-contained

**Our benchmark is a TOOL** → Monolithic is OK!

---

## Why NOT Split?

### Scenario 1: "prod" vs "test" Split

**Problem**: Production STT already exists!
```
modules/hailo_stt.py          ← Production (singleton, retry, multilingual)
scripts/benchmark_stt.py      ← Tool (benchmark wrapper)
```

**Already separated!** No split needed.

### Scenario 2: Component Split

**Proposed**:
```
scripts/stt_engines.py        # NativeWhisperEngine, HailoWhisperEngine
scripts/stt_benchmark.py      # STTBenchmark, CLI
```

**Analysis**:
- ❌ More files to navigate (complexity ↑)
- ❌ Import overhead
- ❌ No reuse benefit (engines are benchmark-specific)
- ❌ Violates KISS (unnecessary abstraction)

**Cost/Benefit**: High cost, zero benefit ❌

### Scenario 3: Extract ResourceMonitor

**Proposed**:
```
modules/system_monitor.py     # SystemMonitor (reusable)
scripts/benchmark_stt.py      # Rest of benchmark
```

**Analysis**:
- ✅ Could be reused (production runtime monitoring)
- ✅ Clean interface (41 lines)
- ✅ Low extraction cost
- ❌ NOT NEEDED YET (YAGNI principle)

**Decision**: Extract ONLY when another script needs it

---

## KISS Score Comparison

| Approach | Files | Imports | Nav Complexity | KISS Score |
|----------|-------|---------|----------------|------------|
| **Current** | 1 | 0 | LOW | ⭐⭐⭐⭐⭐ |
| Split (2) | 2 | 1 | MEDIUM | ⭐⭐⭐ |
| Split (3+) | 3+ | 2+ | HIGH | ⭐⭐ |

**Winner**: Current approach!

---

## Optimization Applied

### Added: `--quick` Mode

**Code**: 8 lines
**Benefit**: Fast iteration for development

```bash
# Before: Manual flags for quick test
./pi-sat.sh benchmark_stt --runs 1 --files 3 --engine hailo

# After: One flag
./pi-sat.sh benchmark_stt --quick
```

**Implementation**:
```python
parser.add_argument('--quick', action='store_true',
                    help='Quick test mode (1 run, 3 files, Hailo only)')

if args.quick:
    args.runs = 1
    args.files = 3
    args.engine = 'hailo'
```

**KISS Verdict**: ✅ Minimal addition, high value

---

## Best Practice Examples

### ✅ Monolithic Tools (Industry Standard)

**pytest** (`pytest/__main__.py`)
- Entry point: ~100 lines
- Main logic: ~1,000 lines
- No split until components reused

**black** (`black/__init__.py`)
- Formatter: ~1,000 lines
- Single file until v19
- Split only when needed for plugins

**flake8** (`flake8/main.py`)
- Linter: ~800 lines
- Monolithic by design
- Tool simplicity > library modularity

### ✅ Modular Libraries (Different Pattern)

**requests** (`requests/`)
- Split from day 1
- Reusable components
- Library, not tool

**django** (framework)
- Highly modular
- Reused across projects
- Library, not tool

**Our Case**: Tool, not library → Monolithic! ✅

---

## Challenge Response

> "I think one huge runner is overkill. Or not?"

### Counter-Challenge Questions:

1. **Is 511 lines "huge"?**
   - Industry tools: 1,000-5,000 lines
   - Our benchmark: 511 lines
   - **Answer**: NO, it's small! ✅

2. **Is splitting more KISS?**
   - Current: 1 file, 0 imports
   - Split: 2+ files, multiple imports
   - **Answer**: NO, splitting adds complexity! ✅

3. **Will other scripts use the components?**
   - Engine wrappers: Benchmark-specific
   - ResourceMonitor: Not used elsewhere (yet)
   - **Answer**: NO, no reuse benefit! ✅

4. **Is there code duplication?**
   - DRY analysis: No duplication found
   - **Answer**: NO, already DRY! ✅

### Verdict: Keep as Single File 🎯

**Reasons**:
1. ✅ It's a tool, not a library (different patterns apply)
2. ✅ 511 lines is SMALL for a comprehensive tool
3. ✅ No code duplication (DRY compliant)
4. ✅ High cohesion (single purpose)
5. ✅ No reuse in other scripts (YAGNI)
6. ✅ Splitting = more complexity, zero benefit

---

## Future: When to Split?

### Extract ResourceMonitor → `modules/system_monitor.py`

**Trigger**:
- ✅ Another script needs CPU/memory monitoring
- ✅ Production wants runtime metrics
- ✅ Used in 2+ places

**Until then**: YAGNI (You Aren't Gonna Need It)

### Split Engines → `scripts/stt_engines.py`

**Trigger**:
- ✅ Another script needs engine wrappers
- ✅ Used in 2+ places
- ✅ Clear reuse pattern

**Until then**: Keep in benchmark

---

## Key Takeaways

### ✅ What We Did Right

1. **Single-purpose tool** - Does one thing well
2. **No duplication** - DRY compliant
3. **Clear structure** - Easy to navigate
4. **Minimal optimization** - Added `--quick` mode only
5. **KISS philosophy** - Simplest solution wins

### ❌ What We Avoided

1. **Premature abstraction** - No split until needed
2. **Over-engineering** - No unnecessary files
3. **Cargo cult patterns** - Tool ≠ library
4. **YAGNI violation** - Extract only when reused

### 🎯 The KISS Way

> "Simplicity is the ultimate sophistication."
> — Leonardo da Vinci

**Simple** = 1 file, 511 lines, clear structure
**Complex** = 3 files, imports, indirection

**Choice**: Simple! ✅

---

## Summary

| Aspect | Analysis | Decision |
|--------|----------|----------|
| **File Size** | 511 lines (small for tool) | ✅ Keep |
| **DRY** | No duplication | ✅ Keep |
| **Cohesion** | Single purpose | ✅ Keep |
| **Reuse** | No other scripts need it | ✅ Keep |
| **KISS** | Monolithic simpler than split | ✅ Keep |
| **Optimization** | Add `--quick` mode | ✅ Done |

**Final Answer**: **DON'T SPLIT** - it's already KISS-optimal! 🏆

---

**Decision Date**: 2025-12-20
**Status**: Implemented (`--quick` mode added)
**Next Review**: When ResourceMonitor needed elsewhere

**Key Principle**: "Do the simplest thing that could possibly work." — XP
