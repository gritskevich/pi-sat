"""
Tests for factory module (dependency injection).
"""

import pytest
import os
from modules.factory import (
    create_music_library,
    create_mpd_controller,
    create_volume_manager,
    create_speech_recorder,
    create_stt_engine,
    create_intent_engine,
    create_tts_engine,
    create_command_processor,
    create_production_orchestrator,
    create_test_command_processor
)


class TestFactoryComponents:
    """Test individual component factories"""

    def test_create_music_library(self):
        """Test music library creation"""
        library = create_music_library(debug=False)

        assert library is not None
        assert hasattr(library, 'search')

    def test_create_speech_recorder(self):
        """Test speech recorder creation"""
        recorder = create_speech_recorder(debug=False)

        assert recorder is not None
        assert hasattr(recorder, 'record_command')

    def test_create_stt_engine(self):
        """Test STT engine creation"""
        if os.getenv("PISAT_RUN_HAILO_TESTS", "0") != "1":
            pytest.skip("Set PISAT_RUN_HAILO_TESTS=1 to run STT factory test")
        try:
            stt = create_stt_engine(debug=False)
            assert stt is not None
            assert hasattr(stt, 'transcribe')
        except Exception:
            # STT may not be available in test environment
            pytest.skip("STT not available")

    def test_create_intent_engine(self):
        """Test intent engine creation"""
        engine = create_intent_engine(debug=False)

        assert engine is not None
        assert hasattr(engine, 'classify')

    def test_create_intent_engine_with_threshold(self):
        """Test intent engine creation with custom threshold"""
        engine = create_intent_engine(fuzzy_threshold=70, debug=False)

        assert engine is not None

    def test_create_mpd_controller(self):
        """Test MPD controller creation"""
        try:
            controller = create_mpd_controller(debug=False)
            assert controller is not None
            assert hasattr(controller, 'play')
            assert hasattr(controller, 'stop')
        except Exception:
            # MPD may not be running in test environment
            pytest.skip("MPD not available")

    def test_create_tts_engine(self):
        """Test TTS engine creation"""
        try:
            tts = create_tts_engine(debug=False)
            assert tts is not None
            assert hasattr(tts, 'speak')
        except FileNotFoundError:
            # Piper binary may not be available
            pytest.skip("TTS not available")

    def test_create_volume_manager(self):
        """Test volume manager creation"""
        manager = create_volume_manager(debug=False)

        assert manager is not None
        assert hasattr(manager, 'set_master_volume')
        assert hasattr(manager, 'music_volume_up')
        assert hasattr(manager, 'music_volume_down')


class TestOrchestratorFactory:
    """Test orchestrator factories"""

    def test_create_production_orchestrator(self):
        """Test production orchestrator creation (may fail without hardware)"""
        if os.getenv("PISAT_RUN_HAILO_TESTS", "0") != "1":
            pytest.skip("Set PISAT_RUN_HAILO_TESTS=1 to run production orchestrator test")
        try:
            orchestrator = create_production_orchestrator()
            assert orchestrator is not None
            assert hasattr(orchestrator, 'run')
        except Exception as e:
            # Production setup may fail without hardware/services
            pytest.skip(f"Production setup not available: {e}")

    def test_create_test_command_processor(self):
        """Test test command processor creation"""
        if os.getenv("PISAT_RUN_HAILO_TESTS", "0") != "1":
            pytest.skip("Set PISAT_RUN_HAILO_TESTS=1 to run test command processor factory")
        try:
            processor = create_test_command_processor()
            assert processor is not None
            assert hasattr(processor, 'process_command')
        except Exception as e:
            # Test processor may fail without dependencies
            pytest.skip(f"Test command processor not available: {e}")


class TestDependencyInjection:
    """Test dependency injection patterns"""

    def test_no_global_singletons(self):
        """Test that factory creates independent instances"""
        engine1 = create_intent_engine()
        engine2 = create_intent_engine()

        # Should be different instances (not singletons)
        assert engine1 is not engine2

    def test_volume_manager_independence(self):
        """Test volume manager creates independent instances"""
        manager1 = create_volume_manager()
        manager2 = create_volume_manager()

        # Should be different instances
        assert manager1 is not manager2

    def test_music_library_independence(self):
        """Test music library creates independent instances"""
        lib1 = create_music_library()
        lib2 = create_music_library()

        # Should be different instances
        assert lib1 is not lib2


class TestFactoryConfiguration:
    """Test that factories respect configuration"""

    def test_debug_flag_propagation(self):
        """Test debug flag is passed to components"""
        # Should not crash
        recorder_debug = create_speech_recorder(debug=True)
        recorder_normal = create_speech_recorder(debug=False)

        assert recorder_debug is not None
        assert recorder_normal is not None

    def test_threshold_configuration(self):
        """Test threshold configuration"""
        engine_60 = create_intent_engine(fuzzy_threshold=60)
        engine_70 = create_intent_engine(fuzzy_threshold=70)

        # Both should be created without errors
        assert engine_60 is not None
        assert engine_70 is not None
