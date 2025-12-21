import unittest
import os
import time
from tests.test_base import PiSatTestBase

class TestSimple(PiSatTestBase):
    """Simple test to verify unified framework works"""
    
    def test_basic_functionality(self):
        """Test basic framework functionality"""
        self._add_result("Basic Test", True, "Framework working")
        self.assert_text_contains("hello world", ["hello"], "Text Contains")
        self.assert_text_equals("test", "test", "Text Equals")
    
    def test_failure_handling(self):
        """Test failure handling"""
        self.assert_text_contains("hello", ["missing"], "Should Fail")
        self.assert_text_equals("test", "wrong", "Should Fail")

if __name__ == "__main__":
    unittest.main(verbosity=2) 
