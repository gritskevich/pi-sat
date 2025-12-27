from unittest.mock import Mock

import config


def test_orchestrator_delegates_with_skip_seconds():
    """Orchestrator delegates to command processor without stream context."""
    from modules.orchestrator import Orchestrator

    command_processor = Mock()
    orchestrator = Orchestrator(
        command_processor=command_processor,
        wake_word_listener=Mock(),
        verbose=False,
        debug=True,
    )

    # No stream context passed - command processor creates its own
    orchestrator._on_wake_word_detected()

    # Command processor called with no parameters (creates fresh stream internally)
    command_processor.process_command.assert_called_once_with()

