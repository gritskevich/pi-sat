from unittest.mock import Mock

import config


def test_orchestrator_delegates_with_skip_seconds():
    """Orchestrator should pass WAKE_SOUND_SKIP_SECONDS into command processing."""
    from modules.orchestrator import Orchestrator

    command_processor = Mock()
    orchestrator = Orchestrator(
        command_processor=command_processor,
        wake_word_listener=Mock(),
        verbose=False,
        debug=True,
    )

    stream = Mock()
    orchestrator._on_wake_word_detected(stream=stream, input_rate=48000)

    command_processor.process_command.assert_called_once_with(
        stream=stream,
        input_rate=48000,
        skip_initial_seconds=config.WAKE_SOUND_SKIP_SECONDS,
    )

