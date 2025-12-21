#!/usr/bin/env python3
"""
Unified test runner for Pi-Sat voice assistant
KISS, DRY, minimal elegant code
"""

import unittest
import sys
import os
import time
import argparse
from modules.logging_utils import setup_logger, log_test, log_success, log_error, log_info

def run_test_suite(test_name=None, verbose=True, timeout=60):
    """Run specific test suite or all tests"""
    logger = setup_logger("TestRunner", debug=True)
    
    if test_name:
        log_test(logger, f"Running test suite: {test_name}")
        # Import and run specific test
        if test_name == "stt":
            from test_hailo_stt_suite import TestHailoSTTSuite
            suite = unittest.TestLoader().loadTestsFromTestCase(TestHailoSTTSuite)
        elif test_name == "stt_integration":
            from test_orchestrator_stt_integration import TestOrchestratorSTTIntegration
            suite = unittest.TestLoader().loadTestsFromTestCase(TestOrchestratorSTTIntegration)
        elif test_name == "wake_word":
            from test_wake_word import TestWakeWordDetection
            suite = unittest.TestLoader().loadTestsFromTestCase(TestWakeWordDetection)
        elif test_name == "speech_recorder":
            from test_speech_recorder import TestSpeechRecorder
            suite = unittest.TestLoader().loadTestsFromTestCase(TestSpeechRecorder)
        elif test_name == "noise_robustness":
            from test_noise_robustness import TestNoiseRobustness
            suite = unittest.TestLoader().loadTestsFromTestCase(TestNoiseRobustness)
        elif test_name == "simple":
            from test_simple import TestSimple
            suite = unittest.TestLoader().loadTestsFromTestCase(TestSimple)
        elif test_name == "hailo_singleton":
            from test_hailo_singleton import TestHailoSingleton
            suite = unittest.TestLoader().loadTestsFromTestCase(TestHailoSingleton)
        elif test_name == "e2e":
            from test_orchestrator_e2e import TestOrchestratorE2E
            suite = unittest.TestLoader().loadTestsFromTestCase(TestOrchestratorE2E)
        elif test_name == "integration":
            from test_orchestrator_integration import TestOrchestratorIntegration
            suite = unittest.TestLoader().loadTestsFromTestCase(TestOrchestratorIntegration)
        else:
            log_error(logger, f"Unknown test suite: {test_name}")
            return False
    else:
        log_test(logger, "Running all test suites")
        # Discover and run all tests
        suite = unittest.TestLoader().discover('.', pattern='test_*.py')
    
    start_time = time.time()
    runner = unittest.TextTestRunner(verbosity=2 if verbose else 1)
    
    # Run with timeout
    import signal
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Test suite timed out after {timeout} seconds")
    
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)
    
    try:
        result = runner.run(suite)
        signal.alarm(0)  # Cancel timeout
    except TimeoutError as e:
        log_error(logger, str(e))
        return False
    finally:
        signal.alarm(0)  # Ensure timeout is cancelled
        # Always unload Hailo between invocations (KISS/DRY)
        try:
            from modules.hailo_stt import HailoSTT
            if HailoSTT._pipeline:
                HailoSTT._pipeline.stop()
            HailoSTT._pipeline = None
            HailoSTT._initialized = False
        except Exception:
            pass
    
    duration = time.time() - start_time
    
    # Summary
    if result.wasSuccessful():
        log_success(logger, f"All tests passed in {duration:.2f}s")
        return True
    else:
        log_error(logger, f"Tests failed: {len(result.failures)} failures, {len(result.errors)} errors")
        return False

def list_available_tests():
    """List all available test suites"""
    logger = setup_logger("TestRunner")
    
    test_suites = [
        ("simple", "Simple framework validation tests"),
        ("hailo_singleton", "Hailo STT singleton pattern tests"),
        ("stt", "Hailo STT transcription tests"),
        ("stt_integration", "Orchestrator STT integration tests"),
        ("e2e", "End-to-end orchestrator pipeline tests"),
        ("integration", "Orchestrator integration tests"),
        ("wake_word", "Wake word detection tests"),
        ("speech_recorder", "Speech recording and VAD tests"),
        ("noise_robustness", "Noise robustness tests"),
    ]
    
    log_info(logger, "Available test suites:")
    for name, description in test_suites:
        print(f"  {name:20} - {description}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pi-Sat Test Runner")
    parser.add_argument("--test", "-t", help="Specific test suite to run")
    parser.add_argument("--list", "-l", action="store_true", help="List available tests")
    parser.add_argument("--quiet", "-q", action="store_true", help="Quiet mode")
    
    args = parser.parse_args()
    
    if args.list:
        list_available_tests()
        sys.exit(0)
    
    success = run_test_suite(args.test, verbose=not args.quiet)
    
    # Clean up any remaining Hailo resources
    try:
        from modules.hailo_stt import HailoSTT
        if HailoSTT._pipeline:
            HailoSTT._pipeline.stop()
            HailoSTT._pipeline = None
            HailoSTT._initialized = False
    except:
        pass
    
    sys.exit(0 if success else 1) 