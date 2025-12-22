#!/usr/bin/env python3
"""
E2E Diagnostic - mic capture timing + STT language forcing (French-first).

What it does (per case):
- Play a generated E2E WAV through the speaker
- Record from the mic in parallel (full capture)
- Slice command audio using metadata timestamps
- Save WAVs to /tmp (timestamped + case id)
- Transcribe with Hailo STT (forced language from metadata, default fr)

Also:
- Simulates SpeechRecorder on the recorded mic audio starting at wake_word_end_s
  (helps detect "recording starts too late" issues due to VAD/calibration/skip).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
import time
import wave
from datetime import datetime
from pathlib import Path

import numpy as np
import pyaudio

# Add repo root to import path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import config
from modules.hailo_stt import HailoSTT
from modules.intent_engine import IntentEngine
from modules.mpd_controller import MPDController
from modules.speech_recorder import SpeechRecorder
from modules.wake_word_listener import WakeWordListener


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


DEFAULT_METADATA = Path("tests/audio_samples/test_metadata.json")
DEFAULT_SUITE_ID = "e2e_french"
DEFAULT_TEST_IDS = "1,6"  # Je veux écouter / Tu peux jouer
DEFAULT_COMMAND_TIMEOUT_S = 5.0  # Command recording timeout
# Volume configuration: System at 40% (voice level), MPD volumes calculated for desired output
# Music: 50% MPD × 40% system = 20% total output
# Duck:  12% MPD × 40% system = 5% total output (12.5% rounds to 12%)
DEFAULT_MUSIC_VOLUME = 50  # MPD music volume
DEFAULT_MUSIC_VOLUME_RECORDING = 12  # MPD music volume during recording (ducked)
DEFAULT_SYSTEM_VOLUME = 40  # System volume (voice/command playback level)


def _slug(text: str) -> str:
    safe = "".join(c if (c.isalnum() or c in ("-", "_")) else "_" for c in text.strip().lower())
    safe = "_".join(filter(None, safe.split("_")))
    return safe[:60] if safe else "case"


def _read_wav_int16(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wf:
        if wf.getnchannels() != 1:
            raise ValueError(f"expected mono WAV, got {wf.getnchannels()} channels: {path}")
        if wf.getsampwidth() != 2:
            raise ValueError(f"expected 16-bit PCM WAV, got sampwidth={wf.getsampwidth()}: {path}")
        rate = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype=np.int16), rate


def _write_wav_int16(path: Path, samples: np.ndarray, rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(samples.astype(np.int16, copy=False).tobytes())


def _resample_int16_linear(samples: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if src_rate == dst_rate or samples.size == 0:
        return samples.astype(np.int16, copy=False)

    src = samples.astype(np.float32)
    ratio = dst_rate / float(src_rate)
    new_len = max(1, int(round(src.size * ratio)))
    x_old = np.linspace(0.0, 1.0, num=src.size, dtype=np.float32)
    x_new = np.linspace(0.0, 1.0, num=new_len, dtype=np.float32)
    resampled = np.interp(x_new, x_old, src)
    return np.clip(resampled, -32768, 32767).astype(np.int16)


class FakeStream:
    """Minimal stream adapter that feeds pyaudio-sized reads from a numpy buffer."""

    def __init__(self, samples: np.ndarray):
        self._samples = samples.astype(np.int16, copy=False)
        self._pos = 0

    def read(self, chunk_size, exception_on_overflow=False):  # noqa: ARG002
        # chunk_size is in samples (pyaudio)
        chunk_size = int(chunk_size)
        end = min(self._pos + chunk_size, self._samples.size)
        chunk = self._samples[self._pos : end]
        self._pos = end
        if chunk.size < chunk_size:
            chunk = np.concatenate([chunk, np.zeros(chunk_size - chunk.size, dtype=np.int16)])
        return chunk.tobytes()


class TimingCapture:
    """Capture timing events with millisecond precision."""

    def __init__(self):
        self.events: list[dict] = []
        self.start_time: float | None = None

    def start(self) -> None:
        self.start_time = time.time()
        self.log("SESSION_START", "Session started")

    def log(self, event: str, description: str = "") -> None:
        timestamp = time.time()
        offset_ms = int((timestamp - self.start_time) * 1000) if self.start_time else 0
        self.events.append(
            {
                "timestamp": timestamp,
                "offset_ms": offset_ms,
                "event": event,
                "description": description,
            }
        )
        logger.info(f"[+{offset_ms:6d}ms] {event}: {description}")

    def offset_ms(self, event_name: str) -> int | None:
        for ev in self.events:
            if ev.get("event") == event_name:
                return int(ev.get("offset_ms", 0))
        return None

    def save_summary(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(self.events, indent=2), encoding="utf-8")


def play_test_command(filepath: str, start_event: threading.Event, timing: TimingCapture) -> None:
    """Play WAV through speaker and signal recording start."""
    timing.log("PLAYBACK_START", f"Playing: {Path(filepath).name}")

    p = pyaudio.PyAudio()
    wf = wave.open(filepath, "rb")
    stream = p.open(
        format=p.get_format_from_width(wf.getsampwidth()),
        channels=wf.getnchannels(),
        rate=wf.getframerate(),
        output=True,
    )

    start_event.set()

    data = wf.readframes(1024)
    while data:
        stream.write(data)
        data = wf.readframes(1024)

    stream.stop_stream()
    stream.close()
    wf.close()
    p.terminate()
    timing.log("PLAYBACK_END", "Playback finished")


def record_from_mic(output_file: Path, duration_s: float, start_event: threading.Event, timing: TimingCapture) -> None:
    """Record mic for fixed duration and save WAV."""
    start_event.wait()
    timing.log("RECORDING_START", f"Recording {duration_s:.2f}s at {config.RATE}Hz")

    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=int(config.RATE),
        input=True,
        frames_per_buffer=1024,
    )

    frames: list[bytes] = []
    total_frames = int(int(config.RATE) / 1024 * duration_s)
    for i in range(total_frames):
        data = stream.read(1024, exception_on_overflow=False)
        frames.append(data)
        if i == 0:
            timing.log("FIRST_FRAME", "First mic frame captured")

    stream.stop_stream()
    stream.close()

    output_file.parent.mkdir(parents=True, exist_ok=True)
    wf = wave.open(str(output_file), "wb")
    wf.setnchannels(1)
    wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
    wf.setframerate(int(config.RATE))
    wf.writeframes(b"".join(frames))
    wf.close()
    p.terminate()

    timing.log("RECORDING_END", f"Saved: {output_file}")


def save_audio_segment(samples: np.ndarray, rate: int, out_dir: Path, name: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"{ts}_{name}.wav"
    _write_wav_int16(path, samples, rate)
    logger.info(f"Saved WAV: {path}")
    return path


def _load_suite(metadata_path: Path, suite_id: str) -> dict:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return metadata["suites"][suite_id]


def _find_case_by_id(suite: dict, case_id: int) -> dict:
    for group in ("positive", "negative"):
        for case in suite["tests"][group]:
            if int(case.get("id", -1)) == int(case_id):
                return case
    raise KeyError(f"case id not found: {case_id}")


def _start_mpd_music(volume: int) -> MPDController | None:
    mpd = MPDController(debug=False)
    if not mpd.connect():
        return None

    # Start MPD playback with specified volume (optional - may not work on all systems)
    mpd.client.clear()
    mpd.client.add("playlist")
    try:
        mpd.client.setvol(volume)
    except Exception as e:
        logger.warning(f"MPD volume control not available: {e}")
        logger.warning("Falling back to system volume control only")
    mpd.client.play(0)
    return mpd


def duck_music_after_wake(wake_word_end_s: float, music_volume_recording: int, mpd: MPDController, timing: TimingCapture) -> None:
    """Duck music after wake word time (based on METADATA timing, simulates orchestrator)."""
    if mpd is None:
        return

    # Wait until wake word should end (based on metadata, not actual detection)
    time.sleep(wake_word_end_s)

    # Duck MPD music volume to recording level (independent from system volume)
    timing.log("VOLUME_DUCK", f"Metadata wake_word_end @ {wake_word_end_s:.2f}s - ducking MPD to {music_volume_recording}%")
    try:
        mpd.client.setvol(music_volume_recording)
    except Exception as e:
        logger.warning(f"Failed to duck MPD volume: {e}")


def run_case(
    *,
    suite: dict,
    case: dict,
    record_duration_s: float,
    music_volume: int,
    music_volume_recording: int,
    system_volume: int,
    out_dir: Path,
    mpd: MPDController | None,
    stt: HailoSTT | None,
) -> int:
    timing = TimingCapture()
    timing.start()

    case_id = int(case["id"])
    case_slug = _slug(case["command"])

    logger.info("=" * 70)
    logger.info(f"E2E DIAGNOSTIC - case {case_id:02d}: {case['full_phrase']}")
    logger.info("=" * 70)
    logger.info(f"language:          {case.get('language', 'fr')}")
    logger.info(f"wake_word_end_s:   {case.get('wake_word_end_s')}")
    logger.info(f"command_start_s:   {case.get('command_start_s')}")
    logger.info(f"wake_sound_skip_s: {config.WAKE_SOUND_SKIP_SECONDS:.2f}")
    logger.info(f"record_duration_s: {record_duration_s:.2f}")
    logger.info(f"system_volume:     {system_volume}% (constant for command playback)")
    logger.info(f"mpd_music_volume:  {music_volume}% (ducks to {music_volume_recording}% after wake)")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    recorded_file = out_dir / f"{ts}_case{case_id:02d}_{case_slug}_mic_full.wav"
    timing_file = out_dir / f"{ts}_case{case_id:02d}_{case_slug}_timing.json"

    wake_listener = None

    try:
        # Set system volume (constant, affects command playback)
        timing.log("SYSTEM_VOLUME_SET", f"System volume set to {system_volume}%")
        import subprocess
        subprocess.run(["amixer", "set", "Master", f"{system_volume}%"], capture_output=True)

        test_file = REPO_ROOT / case["file"]
        if not test_file.exists():
            logger.error(f"Missing test audio: {test_file}")
            return 1

        # Set MPD music volume to normal level (independent from system)
        if mpd is not None:
            try:
                mpd.client.setvol(music_volume)
                timing.log("MPD_VOLUME_SET", f"MPD volume set to {music_volume}%")
            except Exception as e:
                logger.warning(f"Failed to set MPD volume: {e}")

        start_event = threading.Event()

        # Thread to play command (system volume independent)
        t_play = threading.Thread(target=play_test_command, args=(str(test_file), start_event, timing))

        # Thread to record from mic
        t_rec = threading.Thread(target=record_from_mic, args=(recorded_file, record_duration_s, start_event, timing))

        # Thread to duck music after wake word (if present in metadata)
        wake_word_end_s = float(case.get("wake_word_end_s", 0.0))
        t_duck = None
        if wake_word_end_s > 0 and mpd is not None:
            t_duck = threading.Thread(target=duck_music_after_wake,
                                     args=(wake_word_end_s, music_volume_recording, mpd, timing))

        timing.log("THREADS_START", "Launching playback + recording" + (" + wake duck" if t_duck else ""))
        t_play.start()
        t_rec.start()
        if t_duck:
            t_duck.start()

        # Join with timeout (record_duration + 5s buffer)
        timeout_s = record_duration_s + 5.0
        t_play.join(timeout=timeout_s)
        t_rec.join(timeout=timeout_s)
        if t_duck:
            t_duck.join(timeout=1.0)

        if t_play.is_alive() or t_rec.is_alive():
            logger.error(f"Threads timed out after {timeout_s:.1f} seconds!")
            return 1

        # Restore MPD music volume after recording
        if mpd is not None:
            timing.log("VOLUME_RESTORE", f"Restoring MPD music to {music_volume}%")
            try:
                mpd.client.setvol(music_volume)
            except Exception as e:
                logger.warning(f"Failed to restore MPD volume: {e}")

        # Analyze
        mic_i16, sr = _read_wav_int16(recorded_file)
        timing.log("AUDIO_LOADED", f"{mic_i16.size} samples @ {sr}Hz ({mic_i16.size/sr:.2f}s)")

        # Wake word detection on the full recording (post-analysis)
        timing.log("WAKE_DETECT_START", "Detect wake word in recording (post-analysis)")
        wake_listener = WakeWordListener(debug=False)
        detected = wake_listener.detect_wake_word(mic_i16)
        timing.log("WAKE_DETECT_END", f"wake_word_detected={detected}")

        # Log discrepancy if metadata says wake word but detection failed
        has_metadata_wake = float(case.get("wake_word_end_s", 0.0)) > 0
        if has_metadata_wake and not detected:
            logger.warning(f"DETECTION MISMATCH: Metadata indicates wake word @ {case.get('wake_word_end_s')}s but detection returned False")
            logger.warning("Note: Duck happened based on metadata timing, not actual detection")
        elif has_metadata_wake and detected:
            logger.info(f"✓ Wake word detection confirmed (metadata and actual agree)")

        # Slice command based on metadata
        command_start_s = float(case.get("command_start_s", 0.0))
        command_start = int(command_start_s * sr)
        if command_start >= mic_i16.size:
            logger.error("Command start beyond recording length (recording started too late?)")
            return 1

        command_raw = mic_i16[command_start:]
        timing.log("COMMAND_EXTRACT", f"{command_raw.size} samples ({command_raw.size/sr:.2f}s)")
        command_raw_file = save_audio_segment(command_raw, sr, out_dir, f"case{case_id:02d}_{case_slug}_command_raw")

        # Resample to 16k and save exact STT input used below
        command_16k = _resample_int16_linear(command_raw, sr, 16000)
        stt_input_file = save_audio_segment(command_16k, 16000, out_dir, f"case{case_id:02d}_{case_slug}_stt_input_16k")

        # Simulate SpeechRecorder starting at wake_word_end_s (pipeline-ish)
        simulated_file = None
        try:
            wake_word_end_s = float(case.get("wake_word_end_s", 0.0))
            sim_start = int(max(0.0, wake_word_end_s) * sr)
            fake_stream = FakeStream(mic_i16[sim_start:])
            recorder = SpeechRecorder(debug=False)
            timing.log("SIM_REC_START", f"SpeechRecorder(start={wake_word_end_s:.2f}s)")
            recorded_bytes = recorder.record_from_stream(
                fake_stream,
                input_rate=sr,
                max_duration=float(config.MAX_RECORDING_TIME),
                skip_initial_seconds=float(config.WAKE_SOUND_SKIP_SECONDS),
            )
            timing.log("SIM_REC_END", f"bytes={len(recorded_bytes)}")
            if recorded_bytes:
                rec_i16 = np.frombuffer(recorded_bytes, dtype=np.int16)
                simulated_file = save_audio_segment(rec_i16, 16000, out_dir, f"case{case_id:02d}_{case_slug}_speech_recorder_16k")
        except Exception as e:
            logger.warning(f"SpeechRecorder simulation failed: {e}")

        # STT (use shared instance or create if needed)
        expected_lang = case.get("language") or "fr"
        if stt is None:
            timing.log("STT_INIT", f"Init STT language={expected_lang}")
            stt_local = HailoSTT(language=expected_lang, debug=True)
        else:
            stt_local = stt
            actual_lang = stt_local.get_language()
            if actual_lang != expected_lang:
                logger.warning(f"STT language mismatch: expected={expected_lang} actual={actual_lang}")

        actual_lang = stt_local.get_language()
        logger.info(f"STT language: expected={expected_lang} actual={actual_lang}")

        timing.log("STT_START", f"Transcribing {stt_input_file.name}")
        transcript = stt_local.transcribe(command_16k.tobytes())
        timing.log("STT_END", "done")
        logger.info(f"Expected:   {case['command']}")
        logger.info(f"Transcript: {transcript!r}")

        # Intent classification
        timing.log("INTENT_START", "Classifying intent")
        intent_engine = IntentEngine(debug=True)
        intent = intent_engine.classify(transcript)
        timing.log("INTENT_END", "done")

        # Handle intent being either string or dict in metadata
        expected_intent_raw = case.get("intent", "unknown")
        if isinstance(expected_intent_raw, dict):
            expected_intent = expected_intent_raw.get("name", "unknown")
        else:
            expected_intent = expected_intent_raw if expected_intent_raw else "unknown"

        logger.info(f"Expected intent:  {expected_intent}")
        logger.info(f"Detected intent:  {intent.name if intent else 'None'}")
        if intent:
            logger.info(f"Intent params:    {intent.params}")
            logger.info(f"Intent confidence: {intent.confidence}")

        playback_ms = timing.offset_ms("PLAYBACK_START")
        record_ms = timing.offset_ms("RECORDING_START")
        if playback_ms is not None and record_ms is not None:
            logger.info(f"Playback→recording delay: {record_ms - playback_ms}ms")

        timing.save_summary(timing_file)
        logger.info(f"Saved timing log: {timing_file}")

        logger.info("Saved files:")
        logger.info(f"  - {recorded_file}")
        logger.info(f"  - {command_raw_file}")
        logger.info(f"  - {stt_input_file}")
        if simulated_file is not None:
            logger.info(f"  - {simulated_file}")
        logger.info(f"  - {timing_file}")
        logger.info("=" * 70)
        return 0

    except Exception as e:
        logger.error(f"Test case failed: {e}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="E2E diagnostic (French-first)")
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--suite", type=str, default=DEFAULT_SUITE_ID)
    parser.add_argument("--ids", type=str, default=DEFAULT_TEST_IDS, help="Comma-separated case ids (default: 1,6)")
    parser.add_argument("--out-dir", type=Path, default=Path("/tmp"))
    parser.add_argument("--music-volume", type=int, default=DEFAULT_MUSIC_VOLUME, help=f"MPD music volume during playback (default: {DEFAULT_MUSIC_VOLUME}%%)")
    parser.add_argument("--music-volume-recording", type=int, default=DEFAULT_MUSIC_VOLUME_RECORDING,
                        help=f"MPD music volume during command recording/ducked (default: {DEFAULT_MUSIC_VOLUME_RECORDING}%%)")
    parser.add_argument("--system-volume", type=int, default=DEFAULT_SYSTEM_VOLUME,
                        help=f"System volume (constant, affects command playback, default: {DEFAULT_SYSTEM_VOLUME}%%)")
    parser.add_argument("--no-mpd", action="store_true", help="Disable background MPD music")
    parser.add_argument("--command-timeout", type=float, default=DEFAULT_COMMAND_TIMEOUT_S,
                        help=f"Command recording timeout in seconds (default: {DEFAULT_COMMAND_TIMEOUT_S}s)")
    parser.add_argument("--test-pause", type=float, default=2.0, help="Pause between tests in seconds (default: 2.0s)")
    args = parser.parse_args()

    if not args.metadata.exists():
        logger.error(f"Missing metadata: {args.metadata}")
        return 2

    suite = _load_suite(args.metadata, args.suite)
    case_ids = [int(x.strip()) for x in args.ids.split(",") if x.strip()]
    if not case_ids:
        logger.error("No ids provided")
        return 2

    # Initialize shared resources
    mpd = None
    stt = None

    try:
        # Start MPD once if enabled
        if not args.no_mpd:
            logger.info("=" * 70)
            logger.info("INITIALIZING MPD")
            logger.info("=" * 70)
            mpd = _start_mpd_music(args.music_volume)
            if mpd is None:
                logger.warning("MPD not available - continuing without background music")
            else:
                logger.info(f"MPD playing at {args.music_volume}%")
                time.sleep(1)

        # Initialize Hailo STT once (French by default)
        logger.info("=" * 70)
        logger.info("INITIALIZING HAILO STT")
        logger.info("=" * 70)
        # Get language from first test case
        first_case = _find_case_by_id(suite, case_ids[0])
        lang = first_case.get("language", "fr")
        stt = HailoSTT(language=lang, debug=True)
        logger.info(f"Hailo STT initialized with language: {stt.get_language()}")
        logger.info("")

        # Run all test cases in sequence
        status = 0
        for i, case_id in enumerate(case_ids):
            try:
                case = _find_case_by_id(suite, case_id)
            except KeyError as e:
                logger.error(str(e))
                status = 1
                continue

            # Use fixed command timeout instead of calculating from duration
            status = status or run_case(
                suite=suite,
                case=case,
                record_duration_s=args.command_timeout,
                music_volume=args.music_volume,
                music_volume_recording=args.music_volume_recording,
                system_volume=args.system_volume,
                out_dir=args.out_dir,
                mpd=mpd,
                stt=stt,
            )

            # Pause between tests (except after last one)
            if i < len(case_ids) - 1:
                logger.info(f"Pausing {args.test_pause}s before next test...")
                time.sleep(args.test_pause)

        return status

    finally:
        # Cleanup shared resources
        if mpd is not None:
            logger.info("")
            logger.info("=" * 70)
            logger.info("CLEANUP: Stopping MPD")
            logger.info("=" * 70)
            try:
                mpd.client.stop()
            except Exception as e:
                logger.warning(f"MPD stop failed: {e}")
            try:
                mpd.disconnect()
            except Exception as e:
                logger.warning(f"MPD disconnect failed: {e}")

        if stt is not None:
            logger.info("=" * 70)
            logger.info("CLEANUP: Shutting down Hailo STT")
            logger.info("=" * 70)
            try:
                stt.cleanup()
            except Exception as e:
                logger.warning(f"STT cleanup failed: {e}")


if __name__ == "__main__":
    raise SystemExit(main())

