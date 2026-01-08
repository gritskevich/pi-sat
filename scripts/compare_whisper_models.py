#!/usr/bin/env python3
"""
Whisper Model Comparison: CPU vs Hailo, tiny vs base

Compares transcription quality and speed across:
- CPU Whisper (faster-whisper): tiny, base
- Hailo Whisper: tiny, base

Uses ElevenLabs generated test audio samples.
"""

import json
import time
import wave
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass

try:
    from faster_whisper import WhisperModel
    CPU_WHISPER_AVAILABLE = True
except ImportError:
    CPU_WHISPER_AVAILABLE = False
    print("Warning: faster-whisper not installed. CPU tests will be skipped.")
    print("Install with: pip install faster-whisper")

from modules.hailo_stt import HailoSTT


@dataclass
class TranscriptionResult:
    """Result of a single transcription"""
    text: str
    time_ms: float
    model: str
    variant: str  # tiny or base
    backend: str  # cpu or hailo


@dataclass
class TestCase:
    """Audio test case"""
    id: int
    file: str
    expected_command: str
    expected_intent: str
    command_start_s: float


def load_test_cases(metadata_path: Path) -> List[TestCase]:
    """Load test cases from metadata JSON"""
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    suite = metadata['suites']['e2e_french']
    command_start_s = suite["structure"]["command_start_s"]
    test_cases = []

    for test in suite['tests']['positive']:
        test_cases.append(TestCase(
            id=test['id'],
            file=test['file'],
            expected_command=test['command'].lower(),
            expected_intent=test['intent'],
            command_start_s=float(test.get("command_start_s", command_start_s)),
        ))

    return test_cases


def extract_command_audio(audio_path: Path, command_start_s: float) -> bytes:
    """Extract just the command portion (skip wake word)"""
    with wave.open(str(audio_path), 'rb') as wav:
        params = wav.getparams()
        frames = wav.readframes(wav.getnframes())

        # Calculate frame offset for command start
        bytes_per_sample = params.sampwidth
        frame_size = params.nchannels * bytes_per_sample
        start_frame = int(command_start_s * params.framerate)
        start_byte = start_frame * frame_size

        # Extract command audio
        command_audio = frames[start_byte:]

    return command_audio


_CPU_MODELS: Dict[str, "WhisperModel"] = {}


def _get_cpu_model(variant: str) -> "WhisperModel":
    if variant not in _CPU_MODELS:
        _CPU_MODELS[variant] = WhisperModel(variant, device="cpu", compute_type="int8")
    return _CPU_MODELS[variant]


def transcribe_cpu_whisper(audio_bytes: bytes, variant: str = "base") -> TranscriptionResult:
    """Transcribe using CPU Whisper (faster-whisper)"""
    if not CPU_WHISPER_AVAILABLE:
        return TranscriptionResult(
            text="",
            time_ms=0,
            model=f"whisper-{variant}",
            variant=variant,
            backend="cpu-unavailable"
        )

    start = time.time()
    model = _get_cpu_model(variant)

    # Save audio to temp file (faster-whisper needs file path)
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        # Write WAV header + audio
        with wave.open(tmp.name, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(16000)
            wav.writeframes(audio_bytes)

        tmp_path = tmp.name

    # Transcribe
    segments, info = model.transcribe(tmp_path, language="fr", beam_size=1)
    text = " ".join([segment.text for segment in segments]).strip()

    elapsed_ms = (time.time() - start) * 1000

    # Cleanup
    Path(tmp_path).unlink()

    return TranscriptionResult(
        text=text,
        time_ms=elapsed_ms,
        model=f"whisper-{variant}",
        variant=variant,
        backend="cpu"
    )


def transcribe_hailo_whisper(audio_bytes: bytes, stt: HailoSTT, variant: str = "base") -> TranscriptionResult:
    """Transcribe using Hailo Whisper (preloaded instance)"""
    model_name = f"whisper-{variant}"
    start = time.time()
    text = stt.transcribe(audio_bytes)
    elapsed_ms = (time.time() - start) * 1000

    return TranscriptionResult(
        text=text,
        time_ms=elapsed_ms,
        model=model_name,
        variant=variant,
        backend="hailo"
    )


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate text similarity (simple word overlap)"""
    from thefuzz import fuzz
    return fuzz.token_set_ratio(text1.lower(), text2.lower()) / 100.0


def run_comparison(test_cases: List[TestCase], variants: List[str] = ["tiny", "base"]):
    """Run full comparison across models and variants"""
    results = []

    print(f"\n{'='*80}")
    print(f"Whisper Model Comparison: CPU vs Hailo")
    print(f"{'='*80}\n")
    print(f"Test cases: {len(test_cases)}")
    print(f"Variants: {', '.join(variants)}")
    print(f"Backends: CPU (faster-whisper), Hailo")
    print()

    if CPU_WHISPER_AVAILABLE:
        print(f"\n{'-'*80}")
        print("CPU (faster-whisper)")
        print(f"{'-'*80}")
        for variant in variants:
            print(f"\nVARIANT: {variant.upper()}")
            for i, test in enumerate(test_cases, 1):
                print(f"\n[{i}/{len(test_cases)}] Test {test.id}: {test.file}")
                print(f"Expected: \"{test.expected_command}\"")
                print()

                audio_path = Path(test.file)
                if not audio_path.exists():
                    print(f"  ⚠️  Audio file not found: {audio_path}")
                    continue

                audio_bytes = extract_command_audio(audio_path, command_start_s=test.command_start_s)

                try:
                    result_cpu = transcribe_cpu_whisper(audio_bytes, variant)
                    similarity_cpu = calculate_similarity(result_cpu.text, test.expected_command)
                    results.append({
                        'test_id': test.id,
                        'backend': 'cpu',
                        'variant': variant,
                        'text': result_cpu.text,
                        'expected': test.expected_command,
                        'similarity': similarity_cpu,
                        'time_ms': result_cpu.time_ms,
                        'correct': similarity_cpu >= 0.8
                    })
                    print(f"    CPU:   {result_cpu.text[:60]:60} | {result_cpu.time_ms:6.0f}ms | {similarity_cpu*100:5.1f}%")
                except Exception as e:
                    print(f"    CPU:   ERROR: {e}")

    print(f"\n{'-'*80}")
    print("Hailo")
    print(f"{'-'*80}")
    for variant in variants:
        print(f"\nVARIANT: {variant.upper()}")
        stt = HailoSTT(debug=False, language="fr", model=f"whisper-{variant}")
        if not stt.is_available():
            print("  ⚠️  Hailo STT not available for this variant")
            continue

        try:
            for i, test in enumerate(test_cases, 1):
                print(f"\n[{i}/{len(test_cases)}] Test {test.id}: {test.file}")
                print(f"Expected: \"{test.expected_command}\"")
                print()

                audio_path = Path(test.file)
                if not audio_path.exists():
                    print(f"  ⚠️  Audio file not found: {audio_path}")
                    continue

                audio_bytes = extract_command_audio(audio_path, command_start_s=test.command_start_s)

                try:
                    result_hailo = transcribe_hailo_whisper(audio_bytes, stt, variant)
                    similarity_hailo = calculate_similarity(result_hailo.text, test.expected_command)
                    results.append({
                        'test_id': test.id,
                        'backend': 'hailo',
                        'variant': variant,
                        'text': result_hailo.text,
                        'expected': test.expected_command,
                        'similarity': similarity_hailo,
                        'time_ms': result_hailo.time_ms,
                        'correct': similarity_hailo >= 0.8
                    })
                    print(f"    Hailo: {result_hailo.text[:60]:60} | {result_hailo.time_ms:6.0f}ms | {similarity_hailo*100:5.1f}%")
                except Exception as e:
                    print(f"    Hailo: ERROR: {e}")
        finally:
            try:
                stt.cleanup()
            except Exception:
                pass

    return results


def print_summary(results: List[Dict]):
    """Print summary statistics"""
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}\n")

    # Group by backend and variant
    configs = {}
    for r in results:
        key = f"{r['backend']}-{r['variant']}"
        if key not in configs:
            configs[key] = []
        configs[key].append(r)

    # Print table header
    print(f"{'Config':<15} {'Avg Time':<12} {'Accuracy':<12} {'Correct':<10}")
    print(f"{'-'*15} {'-'*12} {'-'*12} {'-'*10}")

    # Print each config
    for config_name in sorted(configs.keys()):
        config_results = configs[config_name]
        avg_time = sum(r['time_ms'] for r in config_results) / len(config_results)
        avg_similarity = sum(r['similarity'] for r in config_results) / len(config_results)
        correct_count = sum(1 for r in config_results if r['correct'])
        total = len(config_results)

        print(f"{config_name:<15} {avg_time:>8.0f}ms    {avg_similarity*100:>6.1f}%      {correct_count}/{total}")

    print()

    # Best performer
    best_speed = min(configs.items(), key=lambda x: sum(r['time_ms'] for r in x[1])/len(x[1]))
    best_accuracy = max(configs.items(), key=lambda x: sum(r['similarity'] for r in x[1])/len(x[1]))

    print(f"🏆 Fastest: {best_speed[0]}")
    print(f"🏆 Most Accurate: {best_accuracy[0]}")
    print()


def main():
    """Main entry point"""
    project_root = Path(__file__).resolve().parent.parent
    metadata_path = project_root / "tests" / "audio_samples" / "test_metadata.json"

    if not metadata_path.exists():
        print(f"Error: Test metadata not found: {metadata_path}")
        return

    # Load test cases
    test_cases = load_test_cases(metadata_path)

    # Run comparison
    variants = ["tiny", "base"]
    results = run_comparison(test_cases, variants)

    # Print summary
    print_summary(results)

    # Save results
    output_path = project_root / "whisper_comparison_results.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    main()
