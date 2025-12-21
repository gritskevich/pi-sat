import types


def test_play_wake_sound_called(monkeypatch):
    import modules.orchestrator as orch
    import modules.audio_player as audio_player

    called = {"count": 0}

    def fake_play():
        called["count"] += 1

    monkeypatch.setattr(audio_player, "play_wake_sound", fake_play)

    o = orch.Orchestrator(debug=True)

    # prevent real processing
    monkeypatch.setattr(o, "_process_command", lambda: None)

    # call the internal handler directly to avoid threading/audio
    o._on_wake_word_detected()

    assert called["count"] == 1


