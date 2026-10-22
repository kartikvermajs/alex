"""Core Assistant coordination module."""

import threading
import time
from typing import Optional
import numpy as np

from config import AssistantConfig, CONFIG
from core.command_router import CommandRouter
from core.state_machine import AssistantState, StateMachine
from storage.logger import logger
from voice.audio_manager import AudioManager
from voice.speech_recognition import SpeechRecognizer, create_speech_recognizer
from voice.text_to_speech import TextToSpeech, create_tts_engine
from voice.wake_word import WakeWordDetector, create_wake_word_detector


class Assistant:
    """Orchestrates wake-word detection, audio capture, speech recognition, command execution, and TTS."""

    def __init__(
        self,
        config: AssistantConfig | None = None,
        audio_manager: AudioManager | None = None,
        speech_recognizer: SpeechRecognizer | None = None,
        tts: TextToSpeech | None = None,
        router: CommandRouter | None = None,
        wake_word_detector: WakeWordDetector | None = None,
    ):
        self.config = config or CONFIG
        self.audio = audio_manager or AudioManager(self.config.audio)
        self.tts = tts or create_tts_engine(self.config.tts)
        self.stt = speech_recognizer or create_speech_recognizer(self.config.stt)
        self.router = router or CommandRouter()
        self.wake_word = wake_word_detector or create_wake_word_detector(self.config.wake_word)
        self.state_machine = StateMachine()

        # Tracking variables
        self.last_command: str = ""
        self.last_response: str = ""
        self._running = False
        self._interaction_lock = threading.Lock()

    def initialize(self) -> dict:
        """Verifies and initializes all system components."""
        logger.info("Initializing %s voice assistant...", self.config.name)

        # 1. Test microphone
        mic_status = self.audio.test_microphone(test_duration=0.5)
        logger.info("Microphone status: %s", "OK" if mic_status.get("working") else "FAILED")

        # 2. Verify STT
        stt_ready = self.stt.is_ready()
        logger.info("Speech Recognizer status: %s", "OK" if stt_ready else "FAILED")

        # 3. Verify TTS
        tts_voices = self.tts.get_voices()
        tts_ready = len(tts_voices) > 0
        logger.info("TTS status: %s (Found %d voices)", "OK" if tts_ready else "FAILED", len(tts_voices))

        # 4. Verify Wake Word Detector
        wake_ready = self.wake_word is not None
        logger.info("Wake Word Detector status: %s", "OK" if wake_ready else "FAILED")

        if self.config.speak_startup_greeting and tts_ready:
            self.tts.speak(f"{self.config.name} is ready.", block=False)

        status_report = {
            "microphone": mic_status.get("working", False),
            "speech_recognition": stt_ready,
            "tts": tts_ready,
            "wake_word": wake_ready,
            "overall_healthy": mic_status.get("working", False) and stt_ready and tts_ready and wake_ready,
        }
        return status_report

    def on_wake_detected(self) -> None:
        """Handler triggered when the wake word is detected."""
        # Ensure only one interaction runs at a time
        if not self._interaction_lock.acquire(blocking=False):
            logger.debug("Interaction already in progress, ignoring duplicate wake event.")
            return

        try:
            logger.info("Wake phrase '%s' detected! Activating conversation mode.", self.config.wake_word.wake_phrase)
            self.wake_word.pause()

            # State: WAKE_DETECTED
            self.state_machine.transition_to(AssistantState.WAKE_DETECTED)

            # Acknowledge user: "Yes?"
            ack = self.config.wake_word.acknowledgement_phrase
            logger.info("Alex acknowledging: \"%s\"", ack)
            self.state_machine.transition_to(AssistantState.SPEAKING)
            self.tts.speak(ack, block=True)

            # Listen for command
            self.state_machine.transition_to(AssistantState.LISTENING)
            logger.info("Listening for command (timeout: %.1fs)...", self.config.wake_word.listen_timeout)
            audio = self.audio.record_command(listen_timeout=self.config.wake_word.listen_timeout)

            if audio is None:
                # No command heard
                self.state_machine.transition_to(AssistantState.SPEAKING)
                msg = "I didn't hear a command."
                self.last_response = msg
                self.tts.speak(msg, block=True)
            else:
                # Command received, transcribe and execute
                self.process_audio(audio)

        except Exception as e:
            logger.error("Error during wake interaction: %s", e)
            self.state_machine.transition_to(AssistantState.ERROR)
            self.state_machine.reset_to_idle()
        finally:
            self.state_machine.reset_to_idle()
            self.wake_word.resume()
            self._interaction_lock.release()

    def start_wake_listening(self) -> None:
        """Starts background continuous listening for the wake word."""
        if not self.config.wake_word.enabled:
            logger.info("Wake-word detection is disabled in configuration.")
            return

        self._running = True
        self.wake_word.start(on_wake=self.on_wake_detected)
        logger.info("Alex is idle and listening for wake phrase: \"%s\"...", self.config.wake_word.wake_phrase)

    def stop_wake_listening(self) -> None:
        """Stops background wake word listener."""
        self._running = False
        self.wake_word.stop()

    def process_text_command(self, text: str) -> str:
        """Processes a string command through router and TTS (useful for direct testing)."""
        self.last_command = text
        self.state_machine.transition_to(AssistantState.PROCESSING)
        self.state_machine.transition_to(AssistantState.EXECUTING)
        response = self.router.route(text)
        self.last_response = response

        self.state_machine.transition_to(AssistantState.SPEAKING)
        self.tts.speak(response, block=True)
        self.state_machine.transition_to(AssistantState.IDLE)
        return response

    def process_audio(self, audio: np.ndarray) -> str:
        """Transcribes provided audio array and executes the resulting command."""
        self.state_machine.transition_to(AssistantState.PROCESSING)
        transcribed_text = self.stt.transcribe(audio)
        self.last_command = transcribed_text

        if not transcribed_text:
            self.state_machine.transition_to(AssistantState.SPEAKING)
            msg = "I didn't understand that."
            self.last_response = msg
            self.tts.speak(msg, block=True)
            self.state_machine.transition_to(AssistantState.IDLE)
            return msg

        self.state_machine.transition_to(AssistantState.EXECUTING)
        response = self.router.route(transcribed_text)
        self.last_response = response

        self.state_machine.transition_to(AssistantState.SPEAKING)
        self.tts.speak(response, block=True)
        self.state_machine.transition_to(AssistantState.IDLE)
        return response

    def listen_and_respond(self, timeout: float = 5.0) -> Optional[str]:
        """Listens directly without wake word, executes, and speaks response."""
        self.state_machine.transition_to(AssistantState.LISTENING)
        logger.info("Listening for command...")

        audio = self.audio.record_command(listen_timeout=timeout)

        if audio is None:
            self.state_machine.transition_to(AssistantState.SPEAKING)
            msg = "I didn't hear a command."
            self.last_response = msg
            self.tts.speak(msg, block=True)
            self.state_machine.transition_to(AssistantState.IDLE)
            return msg

        return self.process_audio(audio)

    def shutdown(self) -> None:
        """Stops background threads and cleans up resources."""
        self.stop_wake_listening()
        if hasattr(self.tts, "shutdown"):
            self.tts.shutdown()
        logger.info("%s assistant shut down cleanly.", self.config.name)
