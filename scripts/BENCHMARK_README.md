# STT Performance Benchmark

Comprehensive performance comparison of Whisper STT implementations on Raspberry Pi 5 + Hailo-8L.

## Overview

This benchmark compares:
- **Native Whisper**: CPU-based inference using `faster-whisper` (quantized INT8)
- **Hailo Whisper**: Hardware-accelerated inference using Hailo-8L NPU

## Metrics Collected

### Performance
- **Cold Start Time**: Model loading time (first run)
- **Transcription Time**: Audio processing latency
- **Real-Time Factor (RTF)**: Processing time / Audio duration
  - RTF < 1.0 = Faster than real-time
  - RTF = 1.0 = Real-time speed
  - RTF > 1.0 = Slower than real-time
- **Throughput**: Files processed per second

### Resources
- **CPU Usage**: Percentage during transcription
- **Memory Delta**: RAM increase during processing
- **CPU Temperature**: Thermal monitoring (throttling detection)

### Quality
- **Transcription Output**: Side-by-side comparison
- **Accuracy**: Can be extended with WER (Word Error Rate) if ground truth available

## Usage

### Quick Start

```bash
# Benchmark Hailo (default, French)
./pi-sat.sh benchmark_stt

# Benchmark specific engine
./pi-sat.sh benchmark_stt --engine hailo
./pi-sat.sh benchmark_stt --engine native

# Select language (applies to Hailo + native faster-whisper)
./pi-sat.sh benchmark_stt --lang fr
./pi-sat.sh benchmark_stt --lang en

# Benchmark a specific audio suite directory
./pi-sat.sh benchmark_stt --audio-dir tests/audio_samples/integration/fr

# Custom runs and files
./pi-sat.sh benchmark_stt --runs 5 --files 10

# Save results to custom file
./pi-sat.sh benchmark_stt --output my_results.json
```

### Options

```
--engine {native|hailo|both}  Which engine to benchmark (default: hailo)
--lang {fr|en}                Language to benchmark (default: fr)
--audio-dir DIR               Directory containing WAV files (default: tests/audio_samples/integration/<lang>)
--runs N                       Number of benchmark runs (default: 3)
--files N                      Number of test files to use (default: 5)
--output FILE                  Output JSON file for results (default: benchmark_results.json)
```

## Installation

### Native Whisper (faster-whisper)

Install for CPU-optimized inference:

```bash
pip install faster-whisper
```

**Note**: This is optional - the benchmark will automatically use Hailo-only if faster-whisper is not installed.

### Hailo Whisper

Already configured via existing `hailo_stt.py` module. No additional setup needed.

## Output Example

```
🚀 STT Performance Benchmark
================================================================================
  System: Raspberry Pi 5 (8GB)
  Engines: both
  Runs: 3
  Test Files: 5
================================================================================

📁 Found 5 test files:
  - alexa_with_prefix.wav
  - alexa_wake_only.wav
  - alexa_immediate_command.wav
  - alexa_with_suffix.wav
  - noise.wav

============================================================
Benchmarking: NATIVE
============================================================
  Loading faster-whisper base...
  ✓ Loaded in 2.34s

🔥 Warm-up run...
  ✓ Warm-up complete

📊 Running 3 benchmark iterations...

--- Run 1/3 ---
  [1/5] alexa_with_prefix.wav (2.1s)
    ✓ Transcribed in 1.234s (RTF: 0.588x)
    📝 Text: Alexa turn on the lights...

...

================================================================================
📊 BENCHMARK SUMMARY
================================================================================

🔧 NATIVE
--------------------------------------------------------------------------------
  Cold Start (Model Load):  2.34s
  Transcription Time:        1.245s ± 0.089s
  Real-Time Factor (RTF):    0.594x
  Throughput:                0.80 files/sec
  CPU Usage:                 42.3%
  Memory Delta:              158.2 MB
  CPU Temperature:           54.2°C
  Total Audio Processed:     10.5s
  Total Processing Time:     6.2s

🔧 HAILO
--------------------------------------------------------------------------------
  Cold Start (Model Load):  3.12s
  Transcription Time:        0.487s ± 0.034s
  Real-Time Factor (RTF):    0.232x
  Throughput:                2.05 files/sec
  CPU Usage:                 18.7%
  Memory Delta:              42.1 MB
  CPU Temperature:           48.1°C
  Total Audio Processed:     10.5s
  Total Processing Time:     2.4s

⚡ COMPARISON
--------------------------------------------------------------------------------
  Hailo Speedup:             2.56x faster

📋 DETAILED RESULTS
--------------------------------------------------------------------------------
Engine   File                           Audio    Trans    RTF      Temp
--------------------------------------------------------------------------------
native   alexa_with_prefix.wav           2.1s   1.234s   0.588x   52.1°C
native   alexa_wake_only.wav             1.8s   1.089s   0.605x   53.4°C
hailo    alexa_with_prefix.wav           2.1s   0.489s   0.233x   47.2°C
hailo    alexa_wake_only.wav             1.8s   0.421s   0.234x   47.8°C
...
```

## JSON Output Format

Results are saved to `benchmark_results.json` (or custom path):

```json
{
  "timestamp": "2025-12-20 12:34:56",
  "system": "Raspberry Pi 5 (8GB)",
  "results": [
    {
      "engine": "hailo",
      "file_name": "alexa_with_prefix.wav",
      "audio_duration": 2.1,
      "transcription": "Alexa turn on the lights in the kitchen",
      "load_time": 3.12,
      "transcription_time": 0.489,
      "rtf": 0.233,
      "cpu_percent": 18.7,
      "memory_mb": 42.1,
      "cpu_temp": 47.2,
      "run_number": 1,
      "is_cold_start": true
    },
    ...
  ]
}
```

## Interpretation Guide

### Real-Time Factor (RTF)
- **RTF < 0.5**: Excellent - Can process audio 2x faster than real-time
- **RTF < 1.0**: Good - Faster than real-time (suitable for streaming)
- **RTF ≈ 1.0**: Acceptable - Real-time processing
- **RTF > 1.0**: Problematic - Slower than real-time (latency accumulates)

### CPU Temperature
- **< 60°C**: Normal operation
- **60-70°C**: Warm but acceptable
- **70-80°C**: Hot - may throttle
- **> 80°C**: Critical - thermal throttling active

### Memory Usage
- Watch for memory leaks (increasing over runs)
- Compare peak usage between engines
- Hailo should show lower memory footprint (offloaded to NPU)

## Extending the Benchmark

### Add Ground Truth for WER

Create a JSON file with expected transcriptions:

```json
{
  "alexa_with_prefix.wav": "Alexa turn on the lights",
  "alexa_wake_only.wav": "Alexa"
}
```

Then extend the benchmark to calculate Word Error Rate.

### Add Custom Test Files

Place audio files in `tests/audio_samples/` and the benchmark will automatically discover them.

### Test Different Models

Modify the benchmark to test different Whisper model sizes:
- `tiny` (39M params) - Fastest, lowest accuracy
- `base` (74M params) - **Current default**
- `small` (244M params) - Better accuracy, slower
- `medium` (769M params) - High accuracy, much slower

## Troubleshooting

### "faster-whisper not installed"

```bash
pip install faster-whisper
```

Or run Hailo-only:
```bash
./pi-sat.sh benchmark_stt --engine hailo
```

### "No test files found"

Generate test audio:
```bash
# Music suite (recommended)
python scripts/generate_music_test_audio.py --languages fr

# Language suite (for language override validation)
python scripts/generate_language_test_audio.py
```

### High CPU Temperature

- Ensure adequate cooling
- Reduce workload: `--runs 1 --files 3`
- Add delays between runs (modify script)

### Inconsistent Results

- Close other applications
- Run multiple times: `--runs 5`
- Check for thermal throttling (monitor temperature)

## Performance Expectations

### Raspberry Pi 5 (8GB) Estimates

**Native Whisper (faster-whisper INT8)**
- RTF: 0.5-0.7x (whisper-base)
- Memory: 150-200 MB
- CPU: 40-60%

**Hailo Whisper (NPU)**
- RTF: 0.2-0.4x (2-3x speedup)
- Memory: 40-60 MB (offloaded)
- CPU: 15-25% (minimal)

**Expected Speedup**: 2-3x faster with Hailo

## Notes

- First run includes model loading (cold start)
- Subsequent runs show "warm" performance
- RTF varies with audio complexity (silence, noise, speech rate)
- Temperature can affect performance (throttling)
- Results may vary based on system load

## Next Steps

1. Run initial benchmark: `./pi-sat.sh benchmark_stt`
2. Compare cold vs warm performance
3. Analyze resource usage patterns
4. Test with real-world audio samples
5. Validate transcription accuracy
6. Make architecture decision based on data

---

**Created**: 2025-12-20
**Author**: Pi-Sat Development Team
**License**: MIT
