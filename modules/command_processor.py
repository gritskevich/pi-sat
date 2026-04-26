import logging
from typing import Optional
from modules.base_module import BaseModule
from modules.logging_utils import log_info, log_success, log_warning, log_error, log_debug, log_stt
from modules.interfaces import Intent
import config
from modules.music_resolver import MusicResolver
from modules.command_validator import CommandValidator
from modules.interaction_logger import append_interaction
from modules.control_events import (
    new_event,
    EVENT_PAUSE_REQUESTED,
    EVENT_CONTINUE_REQUESTED,
    EVENT_VOLUME_UP_REQUESTED,
    EVENT_VOLUME_DOWN_REQUESTED,
    EVENT_NEXT_TRACK_REQUESTED,
    EVENT_PREV_TRACK_REQUESTED,
    EVENT_SET_VOLUME_REQUESTED,
    EVENT_PLAY_REQUESTED,
    EVENT_PLAY_FAVORITES_REQUESTED,
    EVENT_ADD_FAVORITE_REQUESTED,
    EVENT_SLEEP_TIMER_REQUESTED,
    EVENT_REPEAT_MODE_REQUESTED,
    EVENT_SHUFFLE_REQUESTED,
    EVENT_QUEUE_ADD_REQUESTED,
    EVENT_MUSIC_SEARCH_REQUESTED,
    EVENT_INTENT_DETECTED,
    EVENT_INTENT_READY,
    EVENT_RECORDING_STARTED,
    EVENT_RECORDING_FINISHED,
    EVENT_TTS_CONFIRMATION,
)

class CommandProcessor(BaseModule):
    def __init__(
        self,
        speech_recorder,
        stt_engine,
        intent_engine,
        mpd_controller,
        tts_engine,
        volume_manager,
        event_bus=None,
        command_validator=None,
        debug: bool = False,
        verbose: bool = True
    ):
        super().__init__(__name__, debug=debug, verbose=verbose, event_bus=event_bus)
        self.speech_recorder = speech_recorder
        self.stt = stt_engine
        self.intent_engine = intent_engine
        self.mpd_controller = mpd_controller
        self.tts = tts_engine
        self.volume_manager = volume_manager
        self.music_resolver = MusicResolver(self.mpd_controller.get_music_library())

        # Create validator if not provided (with music library for catalog validation)
        if command_validator is None:
            music_library = self.mpd_controller.get_music_library()
            self.validator = CommandValidator(
                music_library=music_library,
                language=getattr(config, 'LANGUAGE', 'fr'),
                debug=debug
            )
        else:
            self.validator = command_validator

        if debug:
            self.logger.setLevel(logging.DEBUG)

        self.logger.info("CommandProcessor initialized")

    def process_command(self) -> bool:
        # Signal recording start (policy decides whether to pause playback)
        if self.event_bus:
            self.event_bus.publish(new_event(EVENT_RECORDING_STARTED, source="command_processor"))
        else:
            log_warning(self.logger, "Event bus missing: recording_started not published")

        try:
            # Step 1: Record audio (creates fresh stream)
            log_info(self.logger, "🎤 Recording command...")
            audio_data = self._record_command()

            if not audio_data or len(audio_data) == 0:
                log_warning(self.logger, "No audio recorded")
                error_msg = self.tts.get_response_template('no_input')
                self.tts.speak(error_msg)
                if self.event_bus:
                    self.event_bus.publish(
                        new_event(
                            EVENT_TTS_CONFIRMATION,
                            {"intent_found": False, "reason": "no_input"},
                            source="command_processor",
                        )
                    )
                return False

            # Step 2: Transcribe audio
            log_info(self.logger, "🔊 Transcribing...")
            text = self._transcribe_audio(audio_data)

            if not text.strip():
                log_warning(self.logger, "⚠️  No text transcribed - command not understood")
                error_msg = self.tts.get_response_template('no_input')
                self.tts.speak(error_msg)
                if self.event_bus:
                    self.event_bus.publish(
                        new_event(
                            EVENT_TTS_CONFIRMATION,
                            {"intent_found": False, "reason": "no_text"},
                            source="command_processor",
                        )
                    )
                return False

            log_stt(self.logger, f"📝 TEXT: '{text}'")

            # Step 3: Classify intent
            intent = self._classify_intent(text)

            if not intent:
                log_warning(self.logger, "⚠️  No intent matched")
                append_interaction(
                    getattr(config, "INTERACTION_LOG_PATH", ""),
                    {
                        "text": text,
                        "intent": None,
                        "intent_confidence": 0.0,
                        "language": getattr(self.intent_engine, "language", getattr(config, "LANGUAGE", "fr")),
                    }
                )
                error_msg = self.tts.get_response_template('unknown')
                self.tts.speak(error_msg)
                if self.event_bus:
                    self.event_bus.publish(
                        new_event(
                            EVENT_TTS_CONFIRMATION,
                            {"intent_found": False, "reason": "no_intent"},
                            source="command_processor",
                        )
                    )
                return False

            log_info(self.logger, f"🎯 INTENT: {intent.intent_type} (confidence: {intent.confidence:.2%})")
            if self.event_bus:
                self.event_bus.publish(
                    new_event(
                        EVENT_INTENT_DETECTED,
                        {
                            "intent_type": intent.intent_type,
                            "confidence": intent.confidence,
                            "language": intent.language,
                            "text": intent.raw_text,
                            "parameters": intent.parameters,
                        },
                        source="intent_engine",
                    )
                )

            # Step 4: Validate command
            validation = self.validator.validate(intent)

            log_payload = {
                "text": text,
                "intent": intent.intent_type,
                "intent_confidence": intent.confidence,
                "language": intent.language,
                "validated": validation.is_valid,
            }
            params = validation.validated_params or {}
            if intent.intent_type == "play_music":
                log_payload["query"] = params.get("query") or intent.parameters.get("query")
                log_payload["matched_file"] = params.get("matched_file")
            append_interaction(getattr(config, "INTERACTION_LOG_PATH", ""), log_payload)

            if not validation.is_valid:
                # Validation failed - speak feedback and return
                log_warning(self.logger, f"⚠️  Validation failed: {validation.feedback_message}")
                self.tts.speak(validation.feedback_message)
                if self.event_bus:
                    self.event_bus.publish(
                        new_event(
                            EVENT_TTS_CONFIRMATION,
                            {"intent_found": False, "intent_type": intent.intent_type, "reason": "invalid"},
                            source="command_processor",
                        )
                    )
                return False

            # Validation succeeded - speak feedback
            log_info(self.logger, f"✅ Validation: {validation.feedback_message}")
            self.tts.speak(validation.feedback_message)
            if self.event_bus:
                payload = {
                    "intent_type": intent.intent_type,
                    "parameters": validation.validated_params or {},
                    "raw_text": intent.raw_text,
                    "language": intent.language,
                }
                self.event_bus.publish(
                    new_event(EVENT_INTENT_READY, payload, source="command_processor")
                )
                self.event_bus.publish(
                    new_event(
                        EVENT_TTS_CONFIRMATION,
                        {"intent_found": True, "intent_type": intent.intent_type},
                        source="command_processor",
                    )
                )
                return True

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
            if self.event_bus:
                self.event_bus.publish(
                    new_event(
                        EVENT_TTS_CONFIRMATION,
                        {"intent_found": False, "reason": "error"},
                        source="command_processor",
                    )
                )
            return False

        finally:
            # Signal recording end (policy decides whether to resume playback)
            if self.event_bus:
                self.event_bus.publish(new_event(EVENT_RECORDING_FINISHED, source="command_processor"))
            else:
                log_warning(self.logger, "Event bus missing: recording_finished not published")

    def _record_command(self) -> bytes:
        if self.debug:
            log_debug(self.logger, "🎤 Recording with VAD silence detection...")

        # Always create fresh stream (clean, simple, reliable)
        audio_data = self.speech_recorder.record_command()

        if self.debug and audio_data:
            log_debug(self.logger, f"🎤 Recorded {len(audio_data)} bytes")

        return audio_data

    def _transcribe_audio(self, audio_data: bytes) -> str:
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
        if not text or not text.strip():
            return None

        try:
            # Primary classification (configured language)
            intent = self.intent_engine.classify(text)
            if intent:
                return intent

            # Fallback classification (FR <-> EN) for occasional wrong-language transcriptions
            primary_language = getattr(self.intent_engine, 'language', None) or getattr(config, 'LANGUAGE', 'fr')
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
        if not intent or not self.mpd_controller:
            return self.tts.get_response_template('error')

        try:
            intent_type = intent.intent_type
            # Use validated parameters if available, otherwise fallback to intent params
            parameters = validated_params if validated_params is not None else intent.parameters

            if intent_type == 'play_music':
                if not self.event_bus:
                    log_warning(self.logger, "Event bus missing: cannot execute play_music")
                    return self.tts.get_response_template('error')
                # Validation already provided user feedback with catalog match
                # Use the matched file directly (validator already searched the catalog)
                matched_file = parameters.get('matched_file')
                if matched_file:
                    # Play the file that validator found (skip redundant search)
                    self.event_bus.publish(
                        new_event(
                            EVENT_PLAY_REQUESTED,
                            {"matched_file": matched_file, "query": parameters.get("query")},
                            source="intent",
                        )
                    )
                    success = True
                else:
                    # Fallback: validator didn't provide matched file, search now
                    query = parameters.get('query')
                    self.event_bus.publish(
                        new_event(
                            EVENT_MUSIC_SEARCH_REQUESTED,
                            {"query": query, "raw_text": intent.raw_text, "language": intent.language},
                            source="intent",
                        )
                    )
                    success = True

                if success:
                    # Validation already spoke confirmation - no need for additional TTS
                    return ""
                else:
                    # Execution failed (MPD error) - speak error
                    return self.tts.get_response_template('error')

            elif intent_type == 'play_favorites':
                # Validation already spoke "Je joue tes favoris"
                if not self.event_bus:
                    log_warning(self.logger, "Event bus missing: cannot execute play_favorites")
                    return self.tts.get_response_template('error')
                self.event_bus.publish(
                    new_event(EVENT_PLAY_FAVORITES_REQUESTED, source="intent")
                )
                return ""

            elif intent_type == 'pause':
                # Validation already spoke response
                if not self.event_bus:
                    log_warning(self.logger, "Event bus missing: cannot execute pause")
                    return self.tts.get_response_template('error')
                self.event_bus.publish(new_event(EVENT_PAUSE_REQUESTED, source="intent"))
                return ""

            elif intent_type == 'resume':
                # Validation already spoke "Je reprends la musique"
                if not self.event_bus:
                    log_warning(self.logger, "Event bus missing: cannot execute resume")
                    return self.tts.get_response_template('error')
                self.event_bus.publish(new_event(EVENT_CONTINUE_REQUESTED, source="intent"))
                return ""

            elif intent_type == 'continue':
                # Validation already spoke "Je reprends la musique"
                if not self.event_bus:
                    log_warning(self.logger, "Event bus missing: cannot execute continue")
                    return self.tts.get_response_template('error')
                self.event_bus.publish(new_event(EVENT_CONTINUE_REQUESTED, source="intent"))
                return ""

            elif intent_type == 'stop':
                # Backward compatibility: stop maps to pause
                if not self.event_bus:
                    log_warning(self.logger, "Event bus missing: cannot execute stop")
                    return self.tts.get_response_template('error')
                self.event_bus.publish(new_event(EVENT_PAUSE_REQUESTED, source="intent"))
                return ""

            elif intent_type == 'next':
                # Validation already spoke "Chanson suivante"
                if not self.event_bus:
                    log_warning(self.logger, "Event bus missing: cannot execute next")
                    return self.tts.get_response_template('error')
                self.event_bus.publish(new_event(EVENT_NEXT_TRACK_REQUESTED, source="intent"))
                return ""

            elif intent_type == 'previous':
                # Validation already spoke "Chanson précédente"
                if not self.event_bus:
                    log_warning(self.logger, "Event bus missing: cannot execute previous")
                    return self.tts.get_response_template('error')
                self.event_bus.publish(new_event(EVENT_PREV_TRACK_REQUESTED, source="intent"))
                return ""

            elif intent_type == 'volume_up':
                # Validation already spoke "J'augmente le volume"
                if not self.event_bus:
                    log_warning(self.logger, "Event bus missing: cannot execute volume_up")
                    return self.tts.get_response_template('error')
                self.event_bus.publish(new_event(EVENT_VOLUME_UP_REQUESTED, source="intent"))
                return ""

            elif intent_type == 'volume_down':
                # Validation already spoke "Je baisse le volume"
                if not self.event_bus:
                    log_warning(self.logger, "Event bus missing: cannot execute volume_down")
                    return self.tts.get_response_template('error')
                self.event_bus.publish(new_event(EVENT_VOLUME_DOWN_REQUESTED, source="intent"))
                return ""

            elif intent_type == 'set_volume':
                # Validation already spoke "Je mets le volume à X%"
                volume = parameters.get('volume', 50)
                # Respect MAX_VOLUME safety limit
                max_vol = min(100, getattr(config, 'MAX_VOLUME', 100))
                volume = min(volume, max_vol)
                if not self.event_bus:
                    log_warning(self.logger, "Event bus missing: cannot execute set_volume")
                    return self.tts.get_response_template('error')
                self.event_bus.publish(
                    new_event(EVENT_SET_VOLUME_REQUESTED, {"volume": volume}, source="intent")
                )
                return ""

            elif intent_type == 'add_favorite':
                # Validation already spoke response
                if not self.event_bus:
                    log_warning(self.logger, "Event bus missing: cannot execute add_favorite")
                    return self.tts.get_response_template('error')
                self.event_bus.publish(
                    new_event(EVENT_ADD_FAVORITE_REQUESTED, source="intent")
                )
                return ""

            elif intent_type == 'sleep_timer':
                # Validation already spoke response
                duration_minutes = parameters.get('duration_minutes', 30)
                if not self.event_bus:
                    log_warning(self.logger, "Event bus missing: cannot execute sleep_timer")
                    return self.tts.get_response_template('error')
                self.event_bus.publish(
                    new_event(
                        EVENT_SLEEP_TIMER_REQUESTED,
                        {"duration_minutes": duration_minutes},
                        source="intent",
                    )
                )
                return ""

            # Repeat/Shuffle controls
            elif intent_type == 'repeat_song':
                # Validation already spoke response
                if not self.event_bus:
                    log_warning(self.logger, "Event bus missing: cannot execute repeat_song")
                    return self.tts.get_response_template('error')
                self.event_bus.publish(
                    new_event(EVENT_REPEAT_MODE_REQUESTED, {"mode": "single"}, source="intent")
                )
                return ""

            elif intent_type == 'repeat_off':
                # Validation already spoke response
                if not self.event_bus:
                    log_warning(self.logger, "Event bus missing: cannot execute repeat_off")
                    return self.tts.get_response_template('error')
                self.event_bus.publish(
                    new_event(EVENT_REPEAT_MODE_REQUESTED, {"mode": "off"}, source="intent")
                )
                return ""

            elif intent_type == 'shuffle_on':
                # Validation already spoke response
                if not self.event_bus:
                    log_warning(self.logger, "Event bus missing: cannot execute shuffle_on")
                    return self.tts.get_response_template('error')
                self.event_bus.publish(
                    new_event(EVENT_SHUFFLE_REQUESTED, {"enabled": True}, source="intent")
                )
                return ""

            elif intent_type == 'shuffle_off':
                # Validation already spoke response
                if not self.event_bus:
                    log_warning(self.logger, "Event bus missing: cannot execute shuffle_off")
                    return self.tts.get_response_template('error')
                self.event_bus.publish(
                    new_event(EVENT_SHUFFLE_REQUESTED, {"enabled": False}, source="intent")
                )
                return ""

            # Queue management
            elif intent_type == 'play_next':
                # Validation already spoke response
                query = parameters.get('query')
                if query:
                    if not self.event_bus:
                        log_warning(self.logger, "Event bus missing: cannot execute play_next")
                        return self.tts.get_response_template('error')
                    self.event_bus.publish(
                        new_event(
                            EVENT_QUEUE_ADD_REQUESTED,
                            {"query": query, "play_next": True},
                            source="intent",
                        )
                    )
                    return ""
                else:
                    return self.tts.get_response_template('error')

            elif intent_type == 'add_to_queue':
                # Validation already spoke response
                query = parameters.get('query')
                if query:
                    if not self.event_bus:
                        log_warning(self.logger, "Event bus missing: cannot execute add_to_queue")
                        return self.tts.get_response_template('error')
                    self.event_bus.publish(
                        new_event(
                            EVENT_QUEUE_ADD_REQUESTED,
                            {"query": query, "play_next": False},
                            source="intent",
                        )
                    )
                    return ""
                else:
                    return self.tts.get_response_template('error')

            else:
                log_warning(self.logger, f"Unknown intent type: {intent_type}")
                return self.tts.get_response_template('unknown')

        except Exception as e:
            log_error(self.logger, f"Intent execution error: {e}")
            return self.tts.get_response_template('error')
