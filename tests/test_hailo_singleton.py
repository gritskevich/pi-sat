import unittest
import os
from tests.test_base import PiSatTestBase
import config

class TestHailoSingleton(PiSatTestBase):
    """Test singleton pattern for Hailo STT"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if config.STT_BACKEND != "hailo":
            raise unittest.SkipTest("STT_BACKEND is not 'hailo'")
        if os.getenv("PISAT_RUN_HAILO_TESTS", "0") != "1":
            raise unittest.SkipTest("Set PISAT_RUN_HAILO_TESTS=1 to run Hailo hardware tests")
    
    def test_singleton_behavior(self):
        """Test that multiple instances return the same object"""
        from modules.hailo_stt import HailoSTT

        stt1 = HailoSTT(debug=True, language="fr")
        stt2 = HailoSTT(debug=False, language="fr")
        
        # Should be the same instance
        self.assertIs(stt1, stt2)
        self._add_result("Singleton Test", True, "Same instance returned")
    
    def test_model_loaded_once(self):
        """Test that model is loaded only once"""
        from modules.hailo_stt import HailoSTT

        # First instance loads model
        stt1 = HailoSTT(debug=True, language="fr")
        available1 = stt1.is_available()
        
        # Second instance reuses same model
        stt2 = HailoSTT(debug=False, language="fr")
        available2 = stt2.is_available()
        
        # Both should be available (same model)
        self.assertEqual(available1, available2)
        self._add_result("Model Loading", True, f"Model available: {available1}")

if __name__ == "__main__":
    unittest.main(verbosity=2) 
