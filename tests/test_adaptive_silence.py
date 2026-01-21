from modules.adaptive_silence import AdaptiveSilenceDetector, AdaptiveSilenceConfig


def test_adaptive_silence_flags_low_rms_as_silence():
    detector = AdaptiveSilenceDetector(
        AdaptiveSilenceConfig(ambient_alpha=0.5, silence_ratio=1.5, min_silence_rms=300.0)
    )
    # Establish ambient around 200
    for _ in range(5):
        detector.update(200.0, vad_is_speech=False)

    # VAD says speech, but RMS below threshold -> treated as silence
    is_speech, threshold = detector.update(250.0, vad_is_speech=True)
    assert threshold >= 300.0
    assert is_speech is False


def test_adaptive_silence_allows_strong_speech():
    detector = AdaptiveSilenceDetector(
        AdaptiveSilenceConfig(ambient_alpha=0.5, silence_ratio=1.4, min_silence_rms=300.0)
    )
    for _ in range(5):
        detector.update(200.0, vad_is_speech=False)

    is_speech, _ = detector.update(800.0, vad_is_speech=True)
    assert is_speech is True


def test_adaptive_silence_set_ambient():
    detector = AdaptiveSilenceDetector(AdaptiveSilenceConfig())
    detector.set_ambient(500.0)
    is_speech, threshold = detector.update(800.0, vad_is_speech=True)
    assert threshold >= 300.0
    assert is_speech is True
