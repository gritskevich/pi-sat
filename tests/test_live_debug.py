#!/usr/bin/env python3
"""
Test live debug features
KISS, DRY, minimal elegant code
"""

import unittest
import os
from tests.test_base import PiSatTestBase

class TestLiveDebug(PiSatTestBase):
    def setUp(self):
        if os.getenv("PISAT_RUN_LIVE_TESTS", "0") != "1":
            self.skipTest("Set PISAT_RUN_LIVE_TESTS=1 to run live debug tests")

        super().setUp()
        try:
            from modules.orchestrator import Orchestrator
            from modules.wake_word_listener import WakeWordListener
            from modules.speech_recorder import SpeechRecorder
        except ModuleNotFoundError as e:
            self.skipTest(f"Missing optional dependency: {e}")

        self.orchestrator = Orchestrator(verbose=True, debug=True)
        self.wake_word_listener = WakeWordListener(debug=True)
        self.speech_recorder = SpeechRecorder(debug=True)
    
    def tearDown(self):
        """Clean up after each test"""
        super().tearDown()
        
        # Clean up Hailo STT
        if hasattr(self.orchestrator, 'stt'):
            self.orchestrator.stt.cleanup()
        
        # Clean up wake word listener
        if hasattr(self.orchestrator, 'wake_word_listener') and self.orchestrator.wake_word_listener:
            self.orchestrator.wake_word_listener.stop_listening()
    
    def test_debug_mode_initialization(self):
        """Test that debug mode is properly initialized"""
        self.assertTrue(self.orchestrator.debug, "Orchestrator debug should be True")
        self.assertTrue(self.wake_word_listener.debug, "Wake word listener debug should be True")
        self.assertTrue(self.speech_recorder.debug, "Speech recorder debug should be True")
    
    def test_debug_logging(self):
        """Test that debug logging works"""
        logger = self.orchestrator.logger
        self.assertIsNotNone(logger, "Logger should be initialized")
    
    def test_live_components(self):
        """Test that all live components are available"""
        # Initialize wake word listener manually for testing
        self.orchestrator.wake_word_listener = WakeWordListener(debug=True)
        
        self.assertIsNotNone(self.orchestrator.wake_word_listener, "Wake word listener should be available")
        self.assertIsNotNone(self.orchestrator.speech_recorder, "Speech recorder should be available")
        self.assertIsNotNone(self.orchestrator.stt, "STT should be available")
        
        # Test debug mode propagation
        self.assertTrue(self.orchestrator.wake_word_listener.debug, "Wake word listener should have debug enabled")

    def test_signal_handling(self):
        """Test that signal handling works properly"""
        self.assertTrue(self.orchestrator.running, "Orchestrator should be running initially")
        
        # Test stop method
        self.orchestrator.stop()
        self.assertFalse(self.orchestrator.running, "Orchestrator should be stopped")
    
    def test_wake_word_listener_running_flag(self):
        """Test wake word listener running flag"""
        self.assertTrue(self.wake_word_listener.running, "Wake word listener should be running initially")
        
        # Test stop method
        self.wake_word_listener.stop_listening()
        self.assertFalse(self.wake_word_listener.running, "Wake word listener should be stopped")

if __name__ == "__main__":
    unittest.main(verbosity=2) 
