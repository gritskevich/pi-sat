# Pi-Sat Documentation Index

**Quick Navigation** for developers and AI assistants

---

## 📚 Core Documentation (Start Here)

### For Development
- **[CLAUDE.md](../CLAUDE.md)** - AI-optimized developer guide (27KB)
  - **When to use:** Primary reference for AI assistants and developers
  - **Content:** Architecture, quick reference, configuration, commands
  - **Size:** Optimized at ~27KB for LLM performance
  - **Updates:** Keep this under 30KB for optimal AI performance

### For Users
- **[README.md](../README.md)** - User-facing project overview (6.5KB)
  - **When to use:** Introduction, quick start, features overview
  - **Content:** Installation, usage examples, voice commands
  - **Audience:** End users and potential contributors

- **[INSTALL.md](../INSTALL.md)** - Complete installation guide (15KB)
  - **When to use:** Setting up Pi-Sat from scratch
  - **Content:** Prerequisites, dependencies, system configuration
  - **Audience:** New users installing the system

### For Tracking
- **[CHANGELOG.md](../CHANGELOG.md)** - Version history and changes (8KB)
  - **When to use:** Understanding what changed and when
  - **Content:** Version history, feature additions, bug fixes
  - **Format:** Semantic versioning (MAJOR.MINOR.PATCH)

- **[VERSION_STATUS.md](../VERSION_STATUS.md)** - Dependency versions (3.5KB)
  - **When to use:** Checking if dependencies need updating
  - **Content:** Current vs latest versions, update recommendations
  - **Updates:** Review monthly or when issues arise

---

## 🔧 Technical Documentation

### Implementation Details
- **[IMPLEMENTATION_PATTERNS.md](IMPLEMENTATION_PATTERNS.md)** - Code patterns (26KB)
  - **When to use:** Understanding how modules work, implementing new features
  - **Content:** Detailed code examples, design patterns, best practices
  - **Sections:** Wake word, VAD, STT, Intent, MPD, TTS, Orchestrator

### Testing
- **[TESTING.md](TESTING.md)** - Testing guide (10KB)
  - **When to use:** Writing tests, running test suite, debugging failures
  - **Content:** Test organization, patterns, coverage goals
  - **Coverage:** 140+ tests, >85% code coverage

### Debugging
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Problem solving (9KB)
  - **When to use:** Debugging issues, fixing configuration problems
  - **Content:** Common issues, diagnostic steps, quick fixes
  - **Sections:** Hailo, MPD, audio, wake word, STT, TTS

### Research & Decisions
- **[RESEARCH.md](RESEARCH.md)** - Technical decisions (10KB)
  - **When to use:** Understanding why things are built this way
  - **Content:** Design rationale, benchmarks, trade-offs
  - **Topics:** Fuzzy matching, MPD, TTS, Hailo, volume control

---

## 📖 Specialized Documentation

### Features
- **[PHONETIC_SEARCH_ARCHITECTURE.md](PHONETIC_SEARCH_ARCHITECTURE.md)** - Music search (8.5KB)
  - **When to use:** Understanding phonetic music matching
  - **Content:** Hybrid search algorithm, confidence thresholds, examples
  - **Performance:** 90% accuracy, 100% match rate

### System Integration
- **[TTS_INTEGRATION.md](TTS_INTEGRATION.md)** - TTS integration (6.5KB)
  - **When to use:** Understanding TTS setup and integration
  - **Content:** Piper TTS configuration, volume management, response templates

- **[PACKAGE_STRUCTURE.md](PACKAGE_STRUCTURE.md)** - Module organization (2.8KB)
  - **When to use:** Understanding codebase organization
  - **Content:** Module structure, import patterns, dependencies

### Guides
- **[MUSIC_LIBRARY_ORGANIZATION.md](MUSIC_LIBRARY_ORGANIZATION.md)** - Music setup (9.6KB)
  - **When to use:** Organizing music library for optimal search
  - **Content:** Directory structure, ID3 tags, MPD configuration

- **[HAILO_STATUS.md](HAILO_STATUS.md)** - Hailo hardware status (8.7KB)
  - **When to use:** Debugging Hailo device issues
  - **Content:** Hardware status, common errors, troubleshooting

### Architecture
- **[SCHEMA.md](SCHEMA.md)** - Visual architecture (1KB)
  - **When to use:** Quick architecture overview
  - **Content:** ASCII diagram of system flow
  - **Format:** Simple visual representation

---

## 📦 Script Documentation

- **[scripts/README.md](../scripts/README.md)** - Scripts overview
  - **When to use:** Understanding available utility scripts
  - **Content:** Script descriptions, usage examples

- **[scripts/BENCHMARK_README.md](../scripts/BENCHMARK_README.md)** - STT benchmark
  - **When to use:** Running STT performance benchmarks
  - **Content:** Benchmark tool usage, metrics, analysis

---

## 📁 Archive

Historical documentation preserved in `docs/archive/`:
- Session summaries (development logs)
- Implementation completion reports
- Optimization summaries
- Planning documents
- Old architecture docs

**When to use archive:** Understanding project history, reviewing past decisions

---

## 🎯 Documentation Usage Guide

### For AI Assistants (like Claude)
**Primary reference:** `CLAUDE.md` (optimized for LLM context)
**For implementation:** `IMPLEMENTATION_PATTERNS.md`
**For testing:** `TESTING.md`
**For debugging:** `TROUBLESHOOTING.md`

### For New Developers
1. Start with `README.md` (project overview)
2. Read `INSTALL.md` (setup)
3. Review `CLAUDE.md` (architecture and patterns)
4. Dive into `IMPLEMENTATION_PATTERNS.md` (detailed code examples)
5. Check `TESTING.md` (test suite)

### For Contributors
1. `CLAUDE.md` - Understand architecture
2. `RESEARCH.md` - Understand design decisions
3. `TESTING.md` - Write tests
4. `CHANGELOG.md` - Document changes

### For Users
1. `README.md` - Quick start
2. `INSTALL.md` - Full setup
3. `TROUBLESHOOTING.md` - Fix issues
4. `MUSIC_LIBRARY_ORGANIZATION.md` - Organize music

---

## 📏 Documentation Principles

### Size Guidelines
- **CLAUDE.md:** Keep under 30KB (currently 27KB ✅)
- **Other core docs:** Keep under 30KB each
- **Specialized docs:** No strict limit, optimize for clarity

### Content Organization
1. **CLAUDE.md** - Essential info only, quick reference
2. **Detailed docs** - Deep dives, code examples, full explanations
3. **Archive** - Historical context, old decisions

### When to Split Content
**Move to separate doc when:**
- Section exceeds 200 lines
- Content is primarily reference material
- Information is useful but not essential daily

**Keep in main docs when:**
- Needed for every coding session
- Quick reference is essential
- Recent changes and active status

---

## 🔄 Maintenance

### Document Owners
- **CLAUDE.md** - Keep current, update monthly
- **CHANGELOG.md** - Update with each release
- **VERSION_STATUS.md** - Review monthly
- **IMPLEMENTATION_PATTERNS.md** - Update when patterns change
- **TESTING.md** - Update when test structure changes

### Review Cadence
- **Weekly:** CHANGELOG.md (during active development)
- **Monthly:** VERSION_STATUS.md, CLAUDE.md
- **As needed:** Technical docs when features change

### Archive Policy
- Session logs → Archive immediately after session
- Planning docs → Archive when implementation complete
- Old implementation docs → Archive when superseded

---

## 📊 Documentation Stats

**Total Documentation:** ~180KB across all files

**Active Documentation:**
- Root: 4 files (~52KB)
- docs/: 10 files (~110KB)
- scripts/: 2 readme files (~15KB)

**Archived:** 21 files (~115KB) in docs/archive/

**Optimization:** 60% reduction in active docs vs. pre-cleanup

---

**Last Updated:** 2025-12-20
**Maintained by:** Project contributors
**Purpose:** Quick navigation and documentation discovery
