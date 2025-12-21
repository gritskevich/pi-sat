import unittest
import os
import time
import signal
from modules.logging_utils import setup_logger, log_test, log_success, log_error

class PiSatTestBase(unittest.TestCase):
    """Base test class with unified logging and utilities"""
    
    def setUp(self):
        self.logger = setup_logger(f"{self.__class__.__name__}", debug=True)
        self.results = {}
        self.start_time = time.time()
        log_test(self.logger, f"Starting {self.__class__.__name__}")
        
        # Setup signal handler for clean shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def tearDown(self):
        duration = time.time() - self.start_time
        if hasattr(self, 'results') and self.results:
            self._print_summary()
        log_test(self.logger, f"Completed {self.__class__.__name__} in {duration:.2f}s")
    
    def _signal_handler(self, signum, frame):
        log_error(self.logger, f"Test interrupted by signal {signum}")
        # Force exit on signal
        os._exit(0)
    
    def _print_summary(self):
        """Print test results summary with emojis"""
        print(f"\n📊 {self.__class__.__name__.upper()} SUMMARY")
        print("=" * 60)
        for test_name, data in self.results.items():
            status = "✅" if data.get("success", False) else "❌"
            print(f"{status} {test_name}: {data.get('message', '')}")
        print("=" * 60)
    
    def _add_result(self, test_name, success, message=""):
        """Add test result to summary"""
        self.results[test_name] = {
            "success": success,
            "message": message
        }
        if success:
            log_success(self.logger, f"{test_name}: {message}")
        else:
            log_error(self.logger, f"{test_name}: {message}")
    
    def assert_audio_processed(self, result, test_name):
        """Assert audio was processed successfully"""
        success = len(result) > 0
        self._add_result(test_name, success, f"{len(result)} bytes processed")
        return success
    
    def assert_text_contains(self, text, keywords, test_name):
        """Assert text contains expected keywords"""
        if not text:
            self._add_result(test_name, False, "Empty text")
            return False
        
        text_lower = text.lower()
        missing = [kw for kw in keywords if kw.lower() not in text_lower]
        
        if missing:
            self._add_result(test_name, False, f"Missing keywords: {missing}")
            return False
        
        self._add_result(test_name, True, f"Contains: {keywords}")
        return True
    
    def assert_text_equals(self, text, expected, test_name):
        """Assert text equals expected value"""
        success = text.strip().lower() == expected.strip().lower()
        self._add_result(test_name, success, f"'{text}' == '{expected}'")
        return success 