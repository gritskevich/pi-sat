#!/usr/bin/env python3
"""
Speech-to-Intent Test Suite

Tests the complete STT → Intent pipeline on pre-recorded French audio samples.
Reports failures and provides detailed diagnostics for analysis.

Usage:
    python scripts/test_stt_intent.py                    # Run all tests
    python scripts/test_stt_intent.py --failures-only    # Show only failures
    python scripts/test_stt_intent.py --verbose          # Show all details
    python scripts/test_stt_intent.py --export report.json  # Export results
"""

import sys
import os
import json
import argparse
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import soundfile as sf
import logging
from thefuzz import fuzz

# Keep test focus aligned with current intent scope.
SUPPORTED_INTENTS = {
    'play_music',
    'stop',
    'volume_up',
    'volume_down',
}

from modules.music_library import MusicLibrary
from modules.intent_engine import IntentEngine
from modules.music_resolver import MusicResolver

logger = logging.getLogger(__name__)
# Setup path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from modules.cleanup_context import HailoContext, force_exit


@dataclass
class TestResult:
    """Test result for a single audio file"""
    filename: str
    stt_transcription: str
    intent_request: str
    expected_intent: str
    actual_intent: str
    expected_params: Dict
    actual_params: Dict
    confidence: float
    success: bool
    error: Optional[str] = None
    duration_ms: int = 0
    expected_query: Optional[str] = None
    actual_query: Optional[str] = None
    expected_song_match: Optional[str] = None
    expected_song_confidence: Optional[float] = None
    actual_song_match: Optional[str] = None
    actual_song_confidence: Optional[float] = None

    def __repr__(self):
        status = "✓" if self.success else "✗"
        return f"{status} {self.filename}: {self.expected_intent} → {self.actual_intent} ({self.confidence:.2f})"


class STTIntentTester:
    """Test suite for STT → Intent pipeline"""

    def __init__(
        self,
        hailo_ctx: Optional[HailoContext],
        audio_dir: str,
        expected_file: str,
        intent_engine: Optional[IntentEngine] = None,
    ):
        self.ctx = hailo_ctx
        self.audio_dir = Path(audio_dir)
        self.expected_file = Path(expected_file)
        self.intent_engine = intent_engine or (hailo_ctx.intent if hailo_ctx else None)

        # Load expected results
        with open(self.expected_file, 'r', encoding='utf-8') as f:
            self.expected = json.load(f)

        self.results: List[TestResult] = []
        self.skipped: List[str] = []
        self.music_library = MusicLibrary(
            library_path=Path("/home/dmitry/pi-sat/playlist"),
            fuzzy_threshold=35,
            phonetic_enabled=True,
            phonetic_weight=0.6,
            debug=False,
        )
        self.music_library.load_from_filesystem()
        self.music_resolver = MusicResolver(self.music_library)

    def load_audio(self, filepath: Path) -> bytes:
        """Load audio file as bytes"""
        audio_data, sample_rate = sf.read(filepath)
        # Convert to bytes (int16 PCM)
        import numpy as np
        audio_int16 = (audio_data * 32767).astype(np.int16)
        return audio_int16.tobytes()

    def test_file(self, filename: str) -> TestResult:
        """Test a single audio file"""
        filepath = self.audio_dir / filename

        if filename not in self.expected:
            self.skipped.append(filename)
            return TestResult(
                filename=filename,
                stt_transcription="",
                expected_intent="SKIPPED",
                actual_intent="SKIPPED",
                expected_params={},
                actual_params={},
                confidence=0.0,
                success=False,
                error="No expected result defined"
            )

        expected = self.expected[filename]
        expected_intent = expected['intent']
        expected_params = expected.get('params', {})
        if expected_intent not in SUPPORTED_INTENTS:
            self.skipped.append(filename)
            return TestResult(
                filename=filename,
                stt_transcription="",
                intent_request="",
                expected_intent="SKIPPED",
                actual_intent="SKIPPED",
                expected_params=expected_params,
                actual_params={},
                confidence=0.0,
                success=False,
                error="Unsupported intent for current test scope"
            )

        try:
            # Load audio
            audio_data = self.load_audio(filepath)

            # Run STT
            start_time = time.time()
            transcription = self.ctx.stt.transcribe(audio_data)
            stt_duration = int((time.time() - start_time) * 1000)

            if not transcription:
                return TestResult(
                    filename=filename,
                    stt_transcription="",
                    intent_request="",
                    expected_intent=expected_intent,
                    actual_intent="UNKNOWN",
                    expected_params=expected_params,
                    actual_params={},
                    confidence=0.0,
                    success=False,
                    error="STT returned empty transcription",
                    duration_ms=stt_duration
                )

            # Classify intent
            start_time = time.time()
            if not self.intent_engine:
                raise RuntimeError("Intent engine not initialized")
            intent = self.intent_engine.classify(transcription)
            intent_duration = int((time.time() - start_time) * 1000)

            # Check if intent matches
            intent_match = intent.intent_type == expected_intent
            params_match, query_debug = self._params_match(expected_params, intent.parameters, transcription)
            success = intent_match and params_match

            return TestResult(
                filename=filename,
                stt_transcription=transcription,
                intent_request=intent.raw_text,
                expected_intent=expected_intent,
                actual_intent=intent.intent_type,
                expected_params=expected_params,
                actual_params=intent.parameters,
                expected_query=query_debug.get("expected_query"),
                actual_query=query_debug.get("actual_query"),
                expected_song_match=query_debug.get("expected_song_match"),
                expected_song_confidence=query_debug.get("expected_song_confidence"),
                actual_song_match=query_debug.get("actual_song_match"),
                actual_song_confidence=query_debug.get("actual_song_confidence"),
                confidence=intent.confidence,
                success=success,
                duration_ms=stt_duration + intent_duration
            )

        except Exception as e:
            return TestResult(
                filename=filename,
                stt_transcription="",
                intent_request="",
                expected_intent=expected_intent,
                actual_intent="ERROR",
                expected_params=expected_params,
                actual_params={},
                confidence=0.0,
                success=False,
                error=str(e)
            )

    def test_transcription(
        self,
        filename: str,
        transcription: str,
        expected_intent: str,
        expected_params: Dict,
    ) -> TestResult:
        """Test classification using an existing transcription (no STT)."""
        if expected_intent not in SUPPORTED_INTENTS:
            self.skipped.append(filename)
            return TestResult(
                filename=filename,
                stt_transcription=transcription,
                intent_request="",
                expected_intent="SKIPPED",
                actual_intent="SKIPPED",
                expected_params=expected_params,
                actual_params={},
                confidence=0.0,
                success=False,
                error="Unsupported intent for current test scope",
            )

        if not self.intent_engine:
            raise RuntimeError("Intent engine not initialized")
        intent = self.intent_engine.classify(transcription)
        if intent is None:
            return TestResult(
                filename=filename,
                stt_transcription=transcription,
                intent_request="",
                expected_intent=expected_intent,
                actual_intent="UNKNOWN",
                expected_params=expected_params,
                actual_params={},
                confidence=0.0,
                success=False,
                error="No intent matched",
            )

        intent_match = intent.intent_type == expected_intent
        params_match, query_debug = self._params_match(expected_params, intent.parameters, transcription)
        success = intent_match and params_match

        return TestResult(
            filename=filename,
            stt_transcription=transcription,
            intent_request=intent.raw_text,
            expected_intent=expected_intent,
            actual_intent=intent.intent_type,
            expected_params=expected_params,
            actual_params=intent.parameters,
            expected_query=query_debug.get("expected_query"),
            actual_query=query_debug.get("actual_query"),
            expected_song_match=query_debug.get("expected_song_match"),
            expected_song_confidence=query_debug.get("expected_song_confidence"),
            actual_song_match=query_debug.get("actual_song_match"),
            actual_song_confidence=query_debug.get("actual_song_confidence"),
            confidence=intent.confidence,
            success=success,
            duration_ms=0,
        )

    def _params_match(self, expected: Dict, actual: Dict, transcription: str) -> tuple[bool, Dict]:
        """Check if parameters match (fuzzy for query strings)"""
        if not expected:
            return True, {}  # No params to check

        for key, expected_value in expected.items():
            if key not in actual:
                if key == 'duration' and 'duration_minutes' in actual:
                    actual_value = actual['duration_minutes']
                elif key == 'query':
                    actual_value = self.music_resolver.extract_query(transcription, language="fr")
                else:
                    return False, {}
            else:
                actual_value = actual[key]

            # For query strings, allow fuzzy matching
            if key == 'query':
                if not actual_value:
                    return False, {}
                # Normalize and compare
                exp_norm = expected_value.lower().strip()
                act_norm = actual_value.lower().strip()
                query_debug = {
                    "expected_query": exp_norm,
                    "actual_query": act_norm,
                }
                logger.info(f"Song detection request (expected): '{exp_norm}'")
                expected_match = self.music_library.search_best(exp_norm)
                if expected_match:
                    logger.info(f"Song detection answer (expected): '{expected_match[0]}' ({expected_match[1]:.2%})")
                    query_debug["expected_song_match"] = expected_match[0]
                    query_debug["expected_song_confidence"] = expected_match[1]
                logger.info(f"Song detection request (actual): '{act_norm}'")
                actual_match = self.music_library.search_best(act_norm)
                if actual_match:
                    logger.info(f"Song detection answer (actual): '{actual_match[0]}' ({actual_match[1]:.2%})")
                    query_debug["actual_song_match"] = actual_match[0]
                    query_debug["actual_song_confidence"] = actual_match[1]
                # Simple contains check (more lenient)
                if exp_norm not in act_norm and act_norm not in exp_norm:
                    if expected_match and actual_match and expected_match[0] == actual_match[0]:
                        return True, query_debug
                    if fuzz.token_set_ratio(exp_norm, act_norm) < 60:
                        return False, query_debug
                return True, query_debug
            elif key == 'duration':
                try:
                    if int(expected_value) != int(actual_value):
                        return False, {}
                except (TypeError, ValueError):
                    return False, {}
            elif key in ('duration', 'time'):
                # For numbers, exact match
                if str(expected_value) != str(actual_value):
                    return False, {}
            else:
                # Other params - exact match
                if expected_value != actual_value:
                    return False, {}

        return True, {}

    def run_all_tests(self) -> List[TestResult]:
        """Run tests on all audio files"""
        audio_files = sorted([f.name for f in self.audio_dir.glob("*.wav")])
        print(f"\n📊 Running tests on {len(audio_files)} audio files...\n")

        for i, filename in enumerate(audio_files, 1):
            print(f"[{i}/{len(audio_files)}] Testing: {filename}...", end=" ")
            result = self.test_file(filename)
            self.results.append(result)

            # Progress indicator
            if result.expected_intent == "SKIPPED":
                print("⏭️  (skipped)")
            elif result.success:
                print(f"✓ ({result.confidence:.0%})")
            else:
                print(f"✗ ({result.actual_intent})")

        return self.results

    def print_summary(self, failures_only: bool = False, verbose: bool = False):
        """Print test summary"""
        total = len([r for r in self.results if r.expected_intent != "SKIPPED"])
        passed = sum(1 for r in self.results if r.success and r.expected_intent != "SKIPPED")
        failed = total - passed
        skipped = len(self.skipped)

        print("\n" + "=" * 80)
        print("📊 TEST SUMMARY")
        print("=" * 80)
        print(f"Total:  {total}")
        print(f"Passed: {passed} ({passed/total*100:.1f}%)")
        print(f"Failed: {failed} ({failed/total*100:.1f}%)")
        if skipped:
            print(f"Skipped: {skipped}")

        if failed == 0:
            print("\n🎉 All tests passed!")
            return

        # Failure breakdown by type
        print("\n📋 FAILURE BREAKDOWN:")
        failure_types = {}
        for r in self.results:
            if not r.success and r.expected_intent != "SKIPPED":
                key = f"{r.expected_intent} → {r.actual_intent}"
                failure_types[key] = failure_types.get(key, 0) + 1

        for failure_type, count in sorted(failure_types.items(), key=lambda x: -x[1]):
            print(f"  {count:3d}× {failure_type}")

        # Detailed failures
        if failures_only or verbose:
            print("\n" + "=" * 80)
            print("❌ FAILED TESTS:")
            print("=" * 80)

            for r in self.results:
                if not r.success and r.expected_intent != "SKIPPED":
                    self._print_result(r, verbose=verbose)

        # Success details (verbose mode only)
        if verbose and not failures_only:
            print("\n" + "=" * 80)
            print("✅ PASSED TESTS:")
            print("=" * 80)

            for r in self.results:
                if r.success:
                    self._print_result(r, verbose=verbose)

    def _print_result(self, r: TestResult, verbose: bool = False):
        """Print a single test result"""
        status = "✓ PASS" if r.success else "✗ FAIL"
        print(f"\n{status}: {r.filename}")
        print(f"  STT:      '{r.stt_transcription}'")
        print(f"  Expected: {r.expected_intent} {r.expected_params}")
        print(f"  Actual:   {r.actual_intent} {r.actual_params}")
        print(f"  Confidence: {r.confidence:.1%}")

        if r.error:
            print(f"  Error:    {r.error}")

        if verbose:
            print(f"  Duration: {r.duration_ms}ms")

    def export_results(self, output_file: str):
        """Export results to JSON"""
        total = len([r for r in self.results if r.expected_intent != "SKIPPED"])
        passed = sum(1 for r in self.results if r.success and r.expected_intent != "SKIPPED")
        failed = total - passed
        pass_rate = (passed / total * 100) if total else 0.0
        data = {
            'summary': {
                'total': total,
                'passed': passed,
                'failed': failed,
                'skipped': len(self.skipped),
                'pass_rate': pass_rate,
            },
            'results': [asdict(r) for r in self.results]
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\n📄 Results exported to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Test STT → Intent pipeline on French audio samples'
    )
    parser.add_argument(
        '--from-json',
        default=None,
        help='Use cached STT results JSON to re-run intent classification',
    )
    parser.add_argument(
        '--audio-dir',
        default='tests/audio_samples/language_tests/french_full',
        help='Directory containing audio files'
    )
    parser.add_argument(
        '--expected',
        default='tests/audio_samples/language_tests/french_full/expected_intents.json',
        help='JSON file with expected results'
    )
    parser.add_argument(
        '--language',
        default='fr',
        help='STT language (default: fr)'
    )
    parser.add_argument(
        '--threshold',
        type=int,
        default=35,
        help='Fuzzy match threshold (default: 35)'
    )
    parser.add_argument(
        '--failures-only',
        action='store_true',
        help='Show only failed tests'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed output for all tests'
    )
    parser.add_argument(
        '--export',
        help='Export results to JSON file'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )

    args = parser.parse_args()

    # Use context manager for automatic cleanup!
    try:
        if args.from_json:
            intent_engine = IntentEngine(
                fuzzy_threshold=args.threshold,
                language=args.language,
                debug=args.debug,
            )
            tester = STTIntentTester(
                hailo_ctx=None,
                audio_dir=args.audio_dir,
                expected_file=args.expected,
                intent_engine=intent_engine,
            )

            cached = json.loads(Path(args.from_json).read_text(encoding='utf-8'))
            cached_results = cached.get('results', [])
            print(f"\n📊 Re-running intent classification on {len(cached_results)} cached transcriptions...\n")
            for i, entry in enumerate(cached_results, 1):
                filename = entry.get('filename', f'cached_{i}.wav')
                transcription = entry.get('stt_transcription', '')
                expected_intent = entry.get('expected_intent', 'UNKNOWN')
                expected_params = entry.get('expected_params', {})
                print(f"[{i}/{len(cached_results)}] Testing: {filename}...", end=" ")
                result = tester.test_transcription(
                    filename=filename,
                    transcription=transcription,
                    expected_intent=expected_intent,
                    expected_params=expected_params,
                )
                tester.results.append(result)
                if result.expected_intent == "SKIPPED":
                    print("⏭️  (skipped)")
                elif result.success:
                    print(f"✓ ({result.confidence:.0%})")
                else:
                    print(f"✗ ({result.actual_intent})")
        else:
            with HailoContext(
                language=args.language,
                fuzzy_threshold=args.threshold,
                debug=args.debug,
                handle_signals=True  # Auto handle Ctrl+C
            ) as ctx:
                print(f"✅ Hailo context ready (model: {config.HAILO_STT_MODEL}, language: {ctx.stt.get_language()})")

                tester = STTIntentTester(
                    hailo_ctx=ctx,
                    audio_dir=args.audio_dir,
                    expected_file=args.expected,
                )

                tester.run_all_tests()

        tester.print_summary(
            failures_only=args.failures_only,
            verbose=args.verbose
        )

        if args.export:
            tester.export_results(args.export)

        # Exit code based on results
        failed = sum(1 for r in tester.results if not r.success and r.expected_intent != "SKIPPED")
        exit_code = 1 if failed > 0 else 0

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        exit_code = 130
    except Exception as e:
        print(f"\n❌ Error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        exit_code = 1

    # Cleanup happens automatically via context manager!
    # Force exit to avoid thread hangs
    force_exit(exit_code)


if __name__ == '__main__':
    main()
