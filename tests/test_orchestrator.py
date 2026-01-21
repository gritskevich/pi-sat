import unittest
from modules.orchestrator import Orchestrator


class TestOrchestrator(unittest.TestCase):
    class _FakeCommandProcessor:
        def __init__(self):
            self.calls = []

        def process_command(self, **kwargs):
            self.calls.append(kwargs)
            return True

    class _FakeWakeWordListener:
        def __init__(self):
            self.stopped = False

        def stop_listening(self):
            self.stopped = True

    def setUp(self):
        self.command_processor = self._FakeCommandProcessor()
        self.wake_word_listener = self._FakeWakeWordListener()
        self.orchestrator = Orchestrator(
            command_processor=self.command_processor,
            wake_word_listener=self.wake_word_listener,
            verbose=False,
            debug=True,
        )

    def tearDown(self):
        self.orchestrator.stop()

    def test_wake_word_detection_delegates_to_command_processor(self):
        self.orchestrator._on_wake_word_detected()
        self.assertEqual(len(self.command_processor.calls), 1)

    def test_stop_stops_wake_word_listener(self):
        self.orchestrator.stop()
        self.assertFalse(self.orchestrator.running)
        self.assertTrue(self.wake_word_listener.stopped)

if __name__ == "__main__":
    unittest.main(verbosity=2) 
