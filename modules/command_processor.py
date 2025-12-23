"""
Command Processor - Voice Command Processing Pipeline

Handles the complete voice command pipeline:
- Audio recording with VAD
- Speech-to-text transcription
- Intent classification
- Intent execution
- TTS response

Completely testable without orchestrator lifecycle or audio hardware.
Accepts injected dependencies for easy mocking in tests.

Following KISS principle: Single responsibility, clear data flow.
"""

import logging
from typing import Optional
from modules.logging_utils import setup_logger, log_info, log_success, log_warning, log_error, log_debug, log_stt
from modules.interfaces import Intent
import config
from modules.music_resolver import MusicResolver
from modules.command_validator import CommandValidator

logger = setup_logger(__name__)


class CommandProcessor:
    """
    Processes voice commands from audio to action.

    Completely independent of orchestrator lifecycle.
    All dependencies are injected for testability.
    """

    def __init__(
        self,
        speech_recorder,
        stt_engine,
        intent_engine,
        mpd_controller,
        tts_engine,
        volume_manager,
        command_validator=None,
        time_scheduler=None,
        morning_alarm=None,
        activity_tracker=None,
        debug: bool = False,
        verbose: bool = True
    ):
        """
        Initialize Command Processor.

        Args:
            speech_recorder: SpeechRecorder instance
            stt_engine: STT engine instance (HailoSTT)
            intent_engine: Intent classifier instance
            mpd_controller: MPD controller instance
            tts_engine: TTS engine instance (PiperTTS)
            volume_manager: Volume manager instance
            command_validator: CommandValidator instance (optional, created if not provided)
            time_scheduler: TimeScheduler instance (optional)
            morning_alarm: MorningAlarm instance (optional)
            activity_tracker: ActivityTracker instance (optional)
            debug: Enable debug logging
            verbose: Enable verbose output
        """
        self.speech_recorder = speech_recorder
        self.stt = stt_engine
        self.intent_engine = intent_engine
        self.mpd_controller = mpd_controller
        self.tts = tts_engine
        self.volume_manager = volume_manager
        self.time_scheduler = time_scheduler
        self.morning_alarm = morning_alarm
        self.activity_tracker = activity_tracker
        self.debug = debug
        self.verbose = verbose
        self.logger = setup_logger(__name__, debug=debug, verbose=verbose)
        self.music_resolver = MusicResolver(self.mpd_controller.get_music_library())

        # Create validator if not provided (with music library for catalog validation)
        if command_validator is None:
            music_library = self.mpd_controller.get_music_library()
            self.validator = CommandValidator(
                music_library=music_library,
                language=getattr(config, 'HAILO_STT_LANGUAGE', 'fr'),
                debug=debug
            )
        else:
            self.validator = command_validator

        if debug:
            logger.setLevel(logging.DEBUG)

        logger.info("CommandProcessor initialized")

    def process_command(self, stream=None, input_rate=None, skip_initial_seconds=0.0) -> bool:
        """
        Process a single voice command through the complete pipeline.

        Args:
            stream: Optional active PyAudio stream (for immediate recording, eliminates latency)
            input_rate: Stream sample rate (required if stream provided)
            skip_initial_seconds: Seconds to skip at start of recording (e.g., 0.7 for wake sound)

        Pipeline steps:
        1. Duck music volume for better voice input
        2. Record audio with VAD silence detection
        3. Transcribe audio to text with STT
        4. Classify text into intent
        5. Validate command (catalog check, parameter validation, French TTS feedback)
        6. Execute intent (MPD control) - silent on success
        7. Speak execution response (only on errors or important info)
        8. Restore music volume

        Returns:
            True if command processed successfully, False otherwise
        """
        # Duck music volume before recording
        duck_level = config.VOLUME_DUCK_LEVEL
        self.volume_manager.duck_music_volume(duck_to=duck_level)

        try:
            # Step 1: Record audio
            log_info(self.logger, "🎤 Recording command...")
            audio_data = self._record_command(
                stream=stream,
                input_rate=input_rate,
                skip_initial_seconds=skip_initial_seconds
            )

            if not audio_data or len(audio_data) == 0:
                log_warning(self.logger, "No audio recorded")
                error_msg = self.tts.get_response_template('error')
                self.tts.speak(error_msg)
                return False

            # Step 2: Transcribe audio
            log_info(self.logger, "🔊 Transcribing...")
            text = self._transcribe_audio(audio_data)

            if not text.strip():
                log_warning(self.logger, "⚠️  No text transcribed - command not understood")
                error_msg = self.tts.get_response_template('error')
                self.tts.speak(error_msg)
                return False

            log_stt(self.logger, f"📝 TEXT: '{text}'")

            # Step 3: Classify intent
            intent = self._classify_intent(text)

            if not intent:
                log_warning(self.logger, "⚠️  No intent matched")
                error_msg = self.tts.get_response_template('unknown')
                self.tts.speak(error_msg)
                return False

            log_info(self.logger, f"🎯 INTENT: {intent.intent_type} (confidence: {intent.confidence:.2%})")

            # Step 4: Validate command
            validation = self.validator.validate(intent)

            if not validation.is_valid:
                # Validation failed - speak feedback and return
                log_warning(self.logger, f"⚠️  Validation failed: {validation.feedback_message}")
                self.tts.speak(validation.feedback_message)
                return False

            # Validation succeeded - speak feedback
            log_info(self.logger, f"✅ Validation: {validation.feedback_message}")
            self.tts.speak(validation.feedback_message)

            # Step 5: Execute intent with validated parameters
            response = self._execute_intent(intent, validation.validated_params)

            # Step 6: Speak execution response (if any)
            if response:
                log_info(self.logger, f"💬 EXECUTION RESPONSE: '{response}'")
                self.tts.speak(response)
            else:
                # No additional response - validation feedback was sufficient
                log_debug(self.logger, "No execution response (validation feedback was spoken)")

            return True

        except Exception as e:
            log_error(self.logger, f"Command processing error: {e}")
            error_msg = self.tts.get_response_template('error')
            self.tts.speak(error_msg)
            return False

        finally:
            # Always restore music volume (even on errors)
            self.volume_manager.restore_music_volume()

    def _record_command(self, stream=None, input_rate=None, skip_initial_seconds=0.0) -> bytes:
        """
        Record voice command with VAD.

        Args:
            stream: Optional active PyAudio stream (eliminates ~200ms stream creation latency)
            input_rate: Stream sample rate (required if stream provided)
            skip_initial_seconds: Seconds to discard at start (e.g., 0.7 for wake sound)

        Returns:
            Audio data as bytes
        """
        if self.debug:
            if stream is not None:
                log_debug(self.logger, "🎤 Recording with stream reuse (optimized!)")
            log_debug(self.logger, "🎤 Recording with VAD silence detection...")

        # Use existing stream if provided (FAST!), otherwise create new stream (legacy fallback)
        if stream is not None and input_rate is not None:
            audio_data = self.speech_recorder.record_from_stream(
                stream=stream,
                input_rate=input_rate,
                skip_initial_seconds=skip_initial_seconds
            )
        else:
            # Legacy fallback: create new stream (slower)
            audio_data = self.speech_recorder.record_command()

        if self.debug and audio_data:
            log_debug(self.logger, f"🎤 Recorded {len(audio_data)} bytes")

        return audio_data

    def _transcribe_audio(self, audio_data: bytes) -> str:
        """
        Transcribe audio to text using STT engine.

        Args:
            audio_data: Audio bytes

        Returns:
            Transcribed text (empty string on failure)
        """
        log_debug(self.logger, "Transcribing audio to text...")

        if len(audio_data) == 0:
            log_warning(self.logger, "Empty audio data - cannot transcribe")
            return ""

        # Check if STT is available
        if not self.stt.is_available():
            log_warning(self.logger, "STT not available - attempting reload")
            self.stt.reload()
            if not self.stt.is_available():
                log_error(self.logger, "STT still not available after reload - transcription failed")
                return ""

        # Convert numpy array to bytes if needed
        if hasattr(audio_data, 'tobytes'):
            audio_data = audio_data.tobytes()

        # STT.transcribe() has built-in retry logic
        text = self.stt.transcribe(audio_data)

        if text:
            if self.debug:
                log_debug(self.logger, f"Transcription successful: '{text}'")
            return text
        else:
            log_warning(self.logger, "Transcription returned empty result - no text detected")
            return ""

    def _classify_intent(self, text: str) -> Optional[Intent]:
        """
        Classify transcribed text into structured intent.

        Args:
            text: Transcribed voice command text

        Returns:
            Intent object or None if no match
        """
        if not text or not text.strip():
            return None

        try:
            # Primary classification (configured language)
            intent = self.intent_engine.classify(text)
            if intent:
                return intent

            # Fallback classification (FR <-> EN) for occasional wrong-language transcriptions
            primary_language = getattr(self.intent_engine, 'language', None) or getattr(config, 'HAILO_STT_LANGUAGE', 'fr')
            if primary_language in ('fr', 'en'):
                fallback_language = 'en' if primary_language == 'fr' else 'fr'
                if self.debug:
                    log_debug(self.logger, f"🌐 No intent in {primary_language}, trying fallback language: {fallback_language}")
                return self.intent_engine.classify(text, language=fallback_language)

            return None
        except Exception as e:
            log_error(self.logger, f"Intent classification error: {e}")
            return None

    def _execute_intent(self, intent: Intent, validated_params: Optional[dict] = None) -> str:
        """
        Execute intent and return TTS response.

        Args:
            intent: Intent object from classification
            validated_params: Validated parameters from CommandValidator (if available)

        Returns:
            Response message for TTS (empty if validation feedback was sufficient)
        """
        if not intent or not self.mpd_controller:
            return self.tts.get_response_template('error')

        try:
            intent_type = intent.intent_type
            # Use validated parameters if available, otherwise fallback to intent params
            parameters = validated_params if validated_params is not None else intent.parameters

            if intent_type == 'play_music':
                # Validation already provided user feedback with catalog match
                # Use the matched file directly (validator already searched the catalog)
                matched_file = parameters.get('matched_file')
                if matched_file:
                    # Play the file that validator found (skip redundant search)
                    success, message, confidence = self.mpd_controller.play(matched_file)
                else:
                    # Fallback: validator didn't provide matched file, search now
                    query = parameters.get('query')
                    resolution = self.music_resolver.resolve(intent.raw_text, intent.language, query)
                    success, message, confidence = self.mpd_controller.play(resolution.query or None)

                if success:
                    # Validation already spoke confirmation - no need for additional TTS
                    return ""
                else:
                    # Execution failed (MPD error) - speak error
                    return self.tts.get_response_template('error')

            elif intent_type == 'play_favorites':
                # Validation already spoke "Je joue tes favoris"
                success, message = self.mpd_controller.play_favorites()
                return "" if success else self.tts.get_response_template('error')

            elif intent_type == 'pause':
                # Validation already spoke "D'accord, je mets en pause"
                self.mpd_controller.pause()
                return ""

            elif intent_type == 'resume':
                # Validation already spoke "Je reprends la musique"
                self.mpd_controller.resume()
                return ""

            elif intent_type == 'stop':
                # Validation already spoke "D'accord, j'arrête"
                self.mpd_controller.stop()
                return ""

            elif intent_type == 'next':
                # Validation already spoke "Chanson suivante"
                success, message = self.mpd_controller.next()
                return "" if success else self.tts.get_response_template('error')

            elif intent_type == 'previous':
                # Validation already spoke "Chanson précédente"
                success, message = self.mpd_controller.previous()
                return "" if success else self.tts.get_response_template('error')

            elif intent_type == 'volume_up':
                # Validation already spoke "J'augmente le volume"
                self.volume_manager.music_volume_up(config.VOLUME_STEP)
                return ""

            elif intent_type == 'volume_down':
                # Validation already spoke "Je baisse le volume"
                self.volume_manager.music_volume_down(config.VOLUME_STEP)
                return ""

            elif intent_type == 'set_volume':
                # Validation already spoke "Je mets le volume à X%"
                volume = parameters.get('volume', 50)
                # Respect MAX_VOLUME safety limit
                max_vol = min(100, getattr(config, 'MAX_VOLUME', 100))
                volume = min(volume, max_vol)
                success = self.volume_manager.set_music_volume(volume)
                return "" if success else self.tts.get_response_template('error')

            elif intent_type == 'add_favorite':
                # Validation already spoke "D'accord, j'ajoute aux favoris"
                success, message = self.mpd_controller.add_to_favorites()
                return "" if success else self.tts.get_response_template('error')

            elif intent_type == 'sleep_timer':
                # Validation already spoke "D'accord, j'arrête dans X minutes"
                duration_minutes = parameters.get('duration_minutes', 30)
                success, message = self.mpd_controller.set_sleep_timer(duration_minutes)
                return "" if success else self.tts.get_response_template('error')

            # Repeat/Shuffle controls
            elif intent_type == 'repeat_song':
                # Validation already spoke "D'accord, je répète"
                self.mpd_controller.set_repeat('single')
                return ""

            elif intent_type == 'repeat_off':
                # Validation already spoke "D'accord, j'arrête de répéter"
                self.mpd_controller.set_repeat('off')
                return ""

            elif intent_type == 'shuffle_on':
                # Validation already spoke "D'accord, je mélange"
                self.mpd_controller.set_shuffle(True)
                return ""

            elif intent_type == 'shuffle_off':
                # Validation already spoke "D'accord, j'arrête de mélanger"
                self.mpd_controller.set_shuffle(False)
                return ""

            # Queue management
            elif intent_type == 'play_next':
                # Validation already spoke "D'accord, {song} sera joué ensuite"
                query = parameters.get('query')
                if query:
                    success, message = self.mpd_controller.add_to_queue(query, play_next=True)
                    return "" if success else self.tts.get_response_template('error')
                else:
                    return self.tts.get_response_template('error')

            elif intent_type == 'add_to_queue':
                # Validation already spoke "D'accord, j'ajoute {song} à la file"
                query = parameters.get('query')
                if query:
                    success, message = self.mpd_controller.add_to_queue(query, play_next=False)
                    return "" if success else self.tts.get_response_template('error')
                else:
                    return self.tts.get_response_template('error')

            # Morning alarm
            elif intent_type == 'set_alarm':
                if not self.morning_alarm:
                    return "Alarm feature is not enabled"

                # Validation already spoke "D'accord, alarme à {time}"
                wake_time = parameters.get('time')
                music_query = parameters.get('music_query')

                if wake_time:
                    success, message = self.morning_alarm.set_alarm(
                        wake_time=wake_time,
                        music_query=music_query,
                        gentle_wakeup=True,
                        recurring='once'
                    )
                    return "" if success else message  # Only speak on error
                else:
                    return self.tts.get_response_template('error')

            elif intent_type == 'cancel_alarm':
                if not self.morning_alarm:
                    return "Alarm feature is not enabled"

                # Validation already spoke "Alarme annulée"
                success, message = self.morning_alarm.cancel_alarm()
                return "" if success else message  # Only speak on error

            # Bedtime / Time scheduler
            elif intent_type == 'check_bedtime':
                if not self.time_scheduler:
                    return "Bedtime is not configured"

                # This is informational - no validation, speak the result
                return self.time_scheduler.get_schedule_info()

            elif intent_type == 'set_bedtime':
                if not self.time_scheduler:
                    return "Bedtime is not configured"

                bedtime = parameters.get('time')
                if bedtime:
                    message = self.time_scheduler.update_schedule(start_time=bedtime)
                    return message  # Speak confirmation
                else:
                    return self.tts.get_response_template('error')

            # Activity tracking
            elif intent_type == 'check_time_limit':
                if not self.activity_tracker:
                    return "Time limits are not enabled"

                # This is informational - no validation, speak the result
                return self.activity_tracker.get_usage_summary()

            else:
                log_warning(self.logger, f"Unknown intent type: {intent_type}")
                return self.tts.get_response_template('unknown')

        except Exception as e:
            log_error(self.logger, f"Intent execution error: {e}")
            return self.tts.get_response_template('error')


if __name__ == '__main__':
    print("CommandProcessor is a library module - import and use in orchestrator")
    print("\nExample usage:")
    print("""
    from modules.command_processor import CommandProcessor
    from modules.factory import create_command_processor

    # Create with factory
    processor = create_command_processor(debug=True)

    # Process a command
    success = processor.process_command()
    """)
