#!/usr/bin/env python3
"""
STT Performance Benchmark: Native Whisper vs Hailo Acceleration
================================================================

Comprehensive comparison of Whisper implementations on Raspberry Pi 5.

Metrics:
- Model loading time (cold start)
- Transcription time (per file + batch)
- Real-Time Factor (RTF = processing_time / audio_duration)
- CPU usage (%)
- Memory usage (MB)
- CPU temperature (°C)
- Throughput (files/second)
- Accuracy (WER comparison)

Usage:
    python scripts/benchmark_stt.py [--engine native|hailo|both]
"""

import os
import sys
import time
import json
import argparse
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import soundfile as sf
from dataclasses import dataclass, asdict


@dataclass
class BenchmarkResult:
    """Single benchmark run result."""
    engine: str
    file_name: str
    audio_duration: float
    transcription: str

    # Timing
    load_time: float = 0.0
    transcription_time: float = 0.0
    rtf: float = 0.0  # Real-Time Factor

    # Resources
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    cpu_temp: float = 0.0

    # Metadata
    run_number: int = 0
    is_cold_start: bool = False


class ResourceMonitor:
    """Monitor system resources during benchmark."""

    @staticmethod
    def get_cpu_temp() -> float:
        """Get CPU temperature in Celsius."""
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                return float(f.read().strip()) / 1000.0
        except:
            return 0.0

    @staticmethod
    def get_memory_usage() -> float:
        """Get current process memory usage in MB."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            # Fallback without psutil
            try:
                with open('/proc/self/status') as f:
                    for line in f:
                        if line.startswith('VmRSS:'):
                            return float(line.split()[1]) / 1024
            except:
                return 0.0
        except:
            return 0.0

    @staticmethod
    def get_cpu_percent() -> float:
        """Get CPU usage percentage."""
        try:
            import psutil
            return psutil.cpu_percent(interval=0.1)
        except ImportError:
            return 0.0


class NativeWhisperEngine:
    """Native Whisper implementation using faster-whisper."""

    def __init__(self, model_size: str = "base", language: str = "fr"):
        self.model_size = model_size
        self.model = None
        self.load_time = 0.0
        self.language = language

    def load_model(self):
        """Load the Whisper model."""
        try:
            from faster_whisper import WhisperModel

            start = time.time()
            print(f"  Loading faster-whisper {self.model_size}...")

            self.model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="int8"  # Quantized for RPi
            )

            self.load_time = time.time() - start
            print(f"  ✓ Loaded in {self.load_time:.2f}s")
            return True

        except ImportError:
            print("  ⚠️  faster-whisper not installed, trying whisper.cpp...")
            return self._load_whisper_cpp()
        except Exception as e:
            print(f"  ❌ Failed to load faster-whisper: {e}")
            return False

    def _load_whisper_cpp(self):
        """Fallback to whisper.cpp if available."""
        # Check if whisper.cpp is available
        result = subprocess.run(['which', 'whisper-cpp'], capture_output=True)
        if result.returncode != 0:
            print("  ❌ whisper.cpp not found either")
            return False

        print("  ✓ Using whisper.cpp")
        self.model = "whisper-cpp"
        return True

    def transcribe(self, audio_path: str) -> Tuple[str, float]:
        """Transcribe audio file."""
        if self.model is None:
            raise RuntimeError("Model not loaded")

        start = time.time()

        if isinstance(self.model, str) and self.model == "whisper-cpp":
            # Use whisper.cpp
            result = subprocess.run(
                ['whisper-cpp', '-m', f'models/ggml-{self.model_size}.bin',
                 '-f', audio_path, '--no-timestamps'],
                capture_output=True,
                text=True
            )
            transcription = result.stdout.strip()
        else:
            # Use faster-whisper
            segments, info = self.model.transcribe(audio_path, language=self.language)
            transcription = " ".join([seg.text for seg in segments])

        elapsed = time.time() - start
        return transcription.strip(), elapsed

    def close(self):
        """Best-effort cleanup to release model resources."""
        self.model = None


class HailoWhisperEngine:
    """Hailo-accelerated Whisper implementation."""

    def __init__(self, language: str = "fr"):
        self.stt = None
        self.load_time = 0.0
        self.language = language

    def load_model(self):
        """Load the Hailo STT model."""
        try:
            from modules.hailo_stt import HailoSTT

            start = time.time()
            print("  Loading Hailo Whisper pipeline...")

            self.stt = HailoSTT(debug=False, language=self.language)

            self.load_time = time.time() - start
            print(f"  ✓ Loaded in {self.load_time:.2f}s")
            return True

        except Exception as e:
            print(f"  ❌ Failed to load Hailo STT: {e}")
            import traceback
            traceback.print_exc()
            return False

    def transcribe(self, audio_path: str) -> Tuple[str, float]:
        """Transcribe audio file using Hailo."""
        if self.stt is None:
            raise RuntimeError("Model not loaded")

        start = time.time()

        # Load audio
        audio_data, sample_rate = sf.read(audio_path)

        # Ensure mono
        if len(audio_data.shape) > 1:
            audio_data = np.mean(audio_data, axis=1)

        # Convert to float32 if needed
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)

        # Transcribe (HailoSTT.transcribe() only takes audio_data)
        transcription = self.stt.transcribe(audio_data)

        elapsed = time.time() - start
        return transcription.strip(), elapsed

    def close(self):
        """Stop the background inference thread started by HailoWhisperPipeline."""
        if self.stt is None:
            return
        try:
            cleanup = getattr(self.stt, "cleanup", None)
            if callable(cleanup):
                cleanup()
        finally:
            self.stt = None


class STTBenchmark:
    """Main benchmark orchestrator."""

    def __init__(self, test_files: List[str]):
        self.test_files = test_files
        self.results: List[BenchmarkResult] = []
        self.monitor = ResourceMonitor()

    def get_audio_duration(self, audio_path: str) -> float:
        """Get audio file duration in seconds."""
        try:
            audio_data, sample_rate = sf.read(audio_path)
            return len(audio_data) / sample_rate
        except:
            return 0.0

    def run_benchmark(self, engine: str, runs: int = 3, language: str = "fr"):
        """Run benchmark for specified engine."""
        print(f"\n{'='*60}")
        print(f"Benchmarking: {engine.upper()}")
        print(f"{'='*60}")

        # Create engine
        if engine == "native":
            stt_engine = NativeWhisperEngine(model_size="base", language=language)
        elif engine == "hailo":
            stt_engine = HailoWhisperEngine(language=language)
        else:
            raise ValueError(f"Unknown engine: {engine}")

        # Load model (cold start)
        if not stt_engine.load_model():
            print(f"❌ Failed to load {engine} engine")
            return

        load_time = stt_engine.load_time
        try:
            # Warm-up run (discard results)
            print(f"\n🔥 Warm-up run...")
            if self.test_files:
                try:
                    stt_engine.transcribe(self.test_files[0])
                    print("  ✓ Warm-up complete")
                except Exception as e:
                    print(f"  ⚠️  Warm-up failed: {e}")

            # Benchmark runs
            print(f"\n📊 Running {runs} benchmark iterations...")

            for run_idx in range(runs):
                print(f"\n--- Run {run_idx + 1}/{runs} ---")

                for file_idx, audio_path in enumerate(self.test_files):
                    file_name = Path(audio_path).name
                    duration = self.get_audio_duration(audio_path)

                    print(f"  [{file_idx+1}/{len(self.test_files)}] {file_name} ({duration:.1f}s)")

                    # Monitor resources before
                    mem_before = self.monitor.get_memory_usage()

                    try:
                        # Transcribe
                        transcription, trans_time = stt_engine.transcribe(audio_path)

                        # Monitor resources after
                        mem_after = self.monitor.get_memory_usage()
                        temp_after = self.monitor.get_cpu_temp()
                        cpu_percent = self.monitor.get_cpu_percent()

                        # Calculate RTF
                        rtf = trans_time / duration if duration > 0 else 0.0

                        # Store result
                        result = BenchmarkResult(
                            engine=engine,
                            file_name=file_name,
                            audio_duration=duration,
                            transcription=transcription[:100],  # Truncate for display
                            load_time=load_time if run_idx == 0 and file_idx == 0 else 0.0,
                            transcription_time=trans_time,
                            rtf=rtf,
                            cpu_percent=cpu_percent,
                            memory_mb=mem_after - mem_before,
                            cpu_temp=temp_after,
                            run_number=run_idx + 1,
                            is_cold_start=(run_idx == 0 and file_idx == 0)
                        )

                        self.results.append(result)

                        print(f"    ✓ Transcribed in {trans_time:.3f}s (RTF: {rtf:.3f}x)")
                        print(f"    📝 Text: {transcription[:60]}...")

                    except Exception as e:
                        print(f"    ❌ Error: {e}")
                        import traceback
                        traceback.print_exc()

            print(f"\n✅ {engine.upper()} benchmark complete!")
        finally:
            close = getattr(stt_engine, "close", None)
            if callable(close):
                try:
                    close()
                except Exception as e:
                    print(f"  ⚠️  Cleanup failed for {engine}: {e}")

    def print_summary(self):
        """Print comprehensive benchmark summary."""
        if not self.results:
            print("No results to summarize")
            return

        print(f"\n{'='*80}")
        print("📊 BENCHMARK SUMMARY")
        print(f"{'='*80}\n")

        # Group by engine
        engines = set(r.engine for r in self.results)

        for engine in sorted(engines):
            engine_results = [r for r in self.results if r.engine == engine]

            # Calculate stats
            load_times = [r.load_time for r in engine_results if r.load_time > 0]
            trans_times = [r.transcription_time for r in engine_results]
            rtfs = [r.rtf for r in engine_results]
            cpu_percents = [r.cpu_percent for r in engine_results if r.cpu_percent > 0]
            memory_mbs = [r.memory_mb for r in engine_results if r.memory_mb > 0]
            temps = [r.cpu_temp for r in engine_results if r.cpu_temp > 0]

            avg_load = np.mean(load_times) if load_times else 0.0
            avg_trans = np.mean(trans_times)
            std_trans = np.std(trans_times)
            avg_rtf = np.mean(rtfs)
            avg_cpu = np.mean(cpu_percents) if cpu_percents else 0.0
            avg_mem = np.mean(memory_mbs) if memory_mbs else 0.0
            avg_temp = np.mean(temps) if temps else 0.0

            total_audio = sum(r.audio_duration for r in engine_results)
            total_processing = sum(r.transcription_time for r in engine_results)
            throughput = len(engine_results) / total_processing if total_processing > 0 else 0.0

            print(f"🔧 {engine.upper()}")
            print(f"{'-'*80}")
            print(f"  Cold Start (Model Load):  {avg_load:.2f}s")
            print(f"  Transcription Time:        {avg_trans:.3f}s ± {std_trans:.3f}s")
            print(f"  Real-Time Factor (RTF):    {avg_rtf:.3f}x")
            print(f"  Throughput:                {throughput:.2f} files/sec")
            print(f"  CPU Usage:                 {avg_cpu:.1f}%")
            print(f"  Memory Delta:              {avg_mem:.1f} MB")
            print(f"  CPU Temperature:           {avg_temp:.1f}°C")
            print(f"  Total Audio Processed:     {total_audio:.1f}s")
            print(f"  Total Processing Time:     {total_processing:.1f}s")
            print()

        # Comparison if both engines tested
        if len(engines) == 2:
            native_results = [r for r in self.results if r.engine == "native"]
            hailo_results = [r for r in self.results if r.engine == "hailo"]

            if native_results and hailo_results:
                native_avg_trans = np.mean([r.transcription_time for r in native_results])
                hailo_avg_trans = np.mean([r.transcription_time for r in hailo_results])

                speedup = native_avg_trans / hailo_avg_trans if hailo_avg_trans > 0 else 0.0

                print(f"⚡ COMPARISON")
                print(f"{'-'*80}")
                print(f"  Hailo Speedup:             {speedup:.2f}x {'faster' if speedup > 1 else 'slower'}")
                print()

        # Detailed results table
        print(f"📋 DETAILED RESULTS")
        print(f"{'-'*80}")
        print(f"{'Engine':<8} {'File':<30} {'Audio':<8} {'Trans':<8} {'RTF':<8} {'Temp':<6}")
        print(f"{'-'*80}")

        for r in self.results:
            print(f"{r.engine:<8} {r.file_name[:28]:<30} {r.audio_duration:>6.1f}s  "
                  f"{r.transcription_time:>6.3f}s  {r.rtf:>6.3f}x  {r.cpu_temp:>4.1f}°C")

        print()

    def save_results(self, output_path: str = "benchmark_results.json"):
        """Save detailed results to JSON."""
        output = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'system': 'Raspberry Pi 5 (8GB)',
            'results': [asdict(r) for r in self.results]
        }

        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"💾 Results saved to: {output_path}")


def find_test_files(max_files: int = 5, audio_dir: str | None = None, lang: str = "fr") -> List[str]:
    """Find test audio files (prefers language-specific suite)."""
    test_dirs = []

    if audio_dir:
        test_dirs.append(audio_dir)
    else:
        test_dirs.extend(
            [
                f"tests/audio_samples/integration/{lang}",
                "tests/audio_samples/integration",
                "tests/audio_samples/wake_word/positive",
            ]
        )

    files = []
    for test_dir in test_dirs:
        if os.path.exists(test_dir):
            for root, dirs, filenames in os.walk(test_dir):
                # Skip generator cache dirs (not meant for benchmarking)
                dirs[:] = [d for d in dirs if not d.startswith("_")]
                for filename in filenames:
                    if filename.endswith('.wav'):
                        if filename.startswith(("tts_", "silence_")):
                            continue
                        files.append(os.path.join(root, filename))
                        if len(files) >= max_files:
                            return files

    return files


def main():
    parser = argparse.ArgumentParser(
        description='Benchmark STT engines: Native Whisper vs Hailo',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--engine',
        choices=['native', 'hailo', 'both'],
        default='hailo',
        help='Which engine to benchmark (default: hailo)'
    )
    parser.add_argument(
        '--lang',
        choices=['fr', 'en'],
        default='fr',
        help='Language to benchmark (default: fr)'
    )
    parser.add_argument(
        '--audio-dir',
        default=None,
        help='Directory containing WAV files (default: tests/audio_samples/integration/<lang>)'
    )
    parser.add_argument(
        '--runs',
        type=int,
        default=3,
        help='Number of benchmark runs (default: 3)'
    )
    parser.add_argument(
        '--files',
        type=int,
        default=5,
        help='Number of test files to use (default: 5)'
    )
    parser.add_argument(
        '--output',
        default='benchmark_results.json',
        help='Output JSON file for results (default: benchmark_results.json)'
    )
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Quick test mode (1 run, 3 files, Hailo only)'
    )

    args = parser.parse_args()

    # Quick mode override
    if args.quick:
        args.runs = 1
        args.files = 3
        args.engine = 'hailo'
        print("⚡ Quick mode: 1 run, 3 files, Hailo only")

    print("🚀 STT Performance Benchmark")
    print(f"{'='*80}")
    print(f"  System: Raspberry Pi 5 (8GB)")
    print(f"  Engines: {args.engine}")
    print(f"  Language: {args.lang}")
    print(f"  Runs: {args.runs}")
    print(f"  Test Files: {args.files}")
    print(f"{'='*80}\n")

    # Find test files
    test_files = find_test_files(max_files=args.files, audio_dir=args.audio_dir, lang=args.lang)
    if not test_files:
        print("❌ No test files found!")
        return 1

    print(f"📁 Found {len(test_files)} test files:")
    for f in test_files:
        print(f"  - {Path(f).name}")

    # Create benchmark
    benchmark = STTBenchmark(test_files)

    # Run benchmarks
    engines_to_test = ['native', 'hailo'] if args.engine == 'both' else [args.engine]

    for engine in engines_to_test:
        try:
            benchmark.run_benchmark(engine, runs=args.runs, language=args.lang)
        except Exception as e:
            print(f"❌ Benchmark failed for {engine}: {e}")
            import traceback
            traceback.print_exc()

    # Print summary
    benchmark.print_summary()

    # Save results
    benchmark.save_results(args.output)

    print("\n✅ Benchmark complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
