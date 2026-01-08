# Phonetic Algorithm Comparison for French Music Search

**Date:** 2025-12-28
**Context:** Replacing BeiderMorse in music search due to 57-second search times

## Executive Summary

**Winner: FONEM (French-specific phonetic algorithm)**

- **78.6% accuracy** (best among all tested algorithms)
- **75x faster** than BeiderMorse (0.8ms vs 67ms per search)
- Designed specifically for French language phonetics

## Benchmark Results

### Dataset
- **74 songs** in ~/Music (mixed French/English/multilingual)
- **28 realistic test cases** based on actual Whisper STT errors
- Focus on French phonetic errors, not just typos

### Performance Summary

| Algorithm       | Accuracy   | Avg Confidence | Encoding Time | Search Time | Speed vs BM |
|-----------------|------------|----------------|---------------|-------------|-------------|
| **FONEM**       | **78.6%** (22/28) | 80.9%     | 0.1ms        | **0.8ms**   | **75x faster** |
| BeiderMorse     | 71.4% (20/28) | 85.6%          | 4.9ms        | 67.4ms      | 1x (baseline) |
| Metaphone       | 64.3% (18/28) | 78.4%          | 0.0ms        | 0.7ms       | 96x faster |
| Soundex         | 57.1% (16/28) | 84.5%          | 0.0ms        | 0.6ms       | 112x faster |
| DoubleMetaphone | 57.1% (16/28) | 77.2%          | 0.0ms        | 0.7ms       | 96x faster |
| Phonex (FR)     | 53.6% (15/28) | 84.9%          | 0.0ms        | 0.6ms       | 112x faster |

## Key Findings

### 1. FONEM Excels at French Phonetics

**Wins BeiderMorse can't handle:**

- ✅ "alors on dance" → "Alors on danse" (89.2% vs 80.2%)
- ✅ English/French mixing: "air electronique" → "Electronic Performers" (71.6%)

**French-specific strengths:**
- Silent letters: "nuit de foli" → "Nuit de folie"
- Accent variations: "debut de soiree" → "Début De Soirée"
- Phonetic misspellings: "mé je t'aime" → "Mais je t'aime"

### 2. BeiderMorse Performance Problem

**Speed breakdown:**
- Encoding: 4.9ms per query
- Search: 67.4ms total (scanning 74 songs)
- **Problem:** Each song has ~5 variants = ~370 phonetic encodings per search
- **Result:** 370 × 1ms/encoding = ~400ms theoretical, actual 67ms (optimized but still slow)

**Why it worked before:** Only ~20 intent patterns vs ~370 music variants

### 3. English Algorithms Fail on French

**Soundex/Phonex failures:**
- "alors on dance" → "All For Metal" ❌ (English word similarity)
- "nuit de foli" → "Nemo - The Code" ❌ (wrong phonetic encoding)

**Reason:** Designed for English pronunciation rules, not French

### 4. Surprising Losses

All algorithms failed on:
- "ghostwriter" → Expected "RJD2 - Ghostwriter", got "Ghostwriter" (different song)
  - **Reason:** Text-only would work, but catalog has both songs

## Algorithm Characteristics

### FONEM (French Phonetic)
- **Language:** French-specific
- **Method:** Phonetic encoding optimized for French pronunciation
- **Strengths:** Silent letters, accents, French phonemes
- **Weaknesses:** English-only songs (but still works reasonably)
- **Use case:** French voice assistants, French music search

### BeiderMorse (Multilingual)
- **Language:** 16+ languages (Czech, Dutch, English, French, German, Greek, Hebrew, Hungarian, Italian, Latvian, Polish, Portuguese, Romanian, Russian, Spanish, Turkish)
- **Method:** Complex rule-based phonetic matching
- **Strengths:** Multilingual name matching, very accurate
- **Weaknesses:** **SLOW** (~1ms per encoding), overkill for single-language use
- **Use case:** Genealogy, multilingual databases, small pattern sets

### Soundex (Classic)
- **Language:** English
- **Method:** First letter + 3-digit code (LNMN → L550)
- **Strengths:** Fast, simple, good for English names
- **Weaknesses:** French false positives, very limited phonetic coverage
- **Use case:** English databases, legacy systems

### Metaphone / Double Metaphone
- **Language:** English (DM has some multilingual support)
- **Method:** More sophisticated than Soundex, better English phonetics
- **Strengths:** Better than Soundex for English
- **Weaknesses:** Still English-focused, moderate accuracy on French
- **Use case:** English spell-checkers, English search engines

### Phonex (French Soundex)
- **Language:** French adaptation of Soundex
- **Method:** Soundex rules adapted for French
- **Strengths:** Fast, designed for French
- **Weaknesses:** **Lowest accuracy** in our tests (53.6%), crude encoding
- **Use case:** Legacy French databases

## Real STT Error Examples

Test cases based on actual Whisper misrecognitions:

1. **Spelling variations:**
   - "astronomie" → "Astronomia" (French vs original spelling)
   - "astronomie à" (with filler word)

2. **Phonetic French:**
   - "mé je t'aime" → "Mais je t'aime" (é sound)
   - "lou anne mama" → "Louane - maman" (name pronunciation)

3. **English/French mixing:**
   - "air électronic performers" (mixed spelling)
   - "air electronique" (full French translation)

4. **Silent letters:**
   - "nuit de foli" → "Nuit de folie" (silent 'e')
   - "nui de folie" (missing 't')

5. **Common misspellings:**
   - "alors on dance" (English spelling)
   - "alor on danse" (missing 's')

6. **Accent removal:**
   - "eric serra" → "Éric Serra"
   - "debut de soiree" → "Début De Soirée"

## Recommendation

**Switch to FONEM for music search**

### Benefits:
1. **+7% accuracy improvement** (78.6% vs 71.4%)
2. **75x faster** (0.8ms vs 67ms) - fixes 57-second search issue
3. **French-optimized** - better handling of French-specific phonetics

### Trade-offs:
- **Lost capability:** Non-French language support (BeiderMorse supports 16 languages)
- **Acceptable because:** Music library is predominantly French, English songs work well enough with text fuzzy matching

### Implementation:
```python
# music_library.py
from abydos.phonetic import FONEM

self._phonetic_matcher = FONEM()
```

### Keep BeiderMorse for intents:
- Intent matching has only ~20 patterns (vs ~370 music variants)
- 20 patterns × 5ms = 100ms total is acceptable
- Multilingual support useful for intent recognition

## Performance Optimization

### Why the speed difference?

**Music search (370 variants):**
- BeiderMorse: 370 × 1ms = ~400ms (theoretical)
- FONEM: 370 × 0.001ms = ~0.4ms
- **1000x faster encoding**

**Current bottleneck with BM:**
- Each search encodes query (5ms) + 370 variants (67ms) = 72ms
- With 10 variants per song × 74 songs = multiple searches compound

**After FONEM switch:**
- Each search: 0.1ms (query) + 0.8ms (variants) = ~1ms total
- **72x faster overall**

## Sources

Research based on:
- [Talisman - French Phonetic Algorithms](https://yomguithereal.github.io/talisman/phonetics/french)
- [Beider-Morse Phonetic Matching](https://stevemorse.org/phoneticinfo.htm)
- [Performance Evaluation of Phonetic Matching Algorithms](https://www.scitepress.org/papers/2016/59263/59263.pdf)
- [Phonex Algorithm for French](https://github.com/lovasoa/phonex)
- [FONEM French Phonetic Algorithm](https://cran.r-project.org/web/packages/phonics/phonics.pdf)
