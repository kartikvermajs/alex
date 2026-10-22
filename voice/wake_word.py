"""Local, lightweight offline wake-word detector using Vosk grammar keyword spotting."""

from abc import ABC, abstractmethod
import json
import os
import threading
import time
from typing import Callable, List, Optional
import numpy as np
import sounddevice as sd

from config import WakeWordConfig, CONFIG
from storage.logger import logger


class WakeWordDetector(ABC):
    """Abstract base class for local wake-word detectors."""

    @abstractmethod
    def start(self, on_wake: Callable[[], None]) -> None:
        """Starts background listening for wake word."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stops listening."""
        pass

    @abstractmethod
    def pause(self) -> None:
        """Temporarily pauses detection (e.g. while Alex is listening or speaking)."""
        pass

    @abstractmethod
    def resume(self) -> None:
        """Resumes wake word detection."""
        pass

    @abstractmethod
    def is_listening(self) -> bool:
        """Returns True if detector is actively running."""
        pass

    @abstractmethod
    def process_audio(self, audio: np.ndarray) -> bool:
        """Processes an audio buffer directly and returns True if wake word is detected."""
        pass


class VoskWakeWordDetector(WakeWordDetector):
    """
    Lightweight, offline keyword spotter using Kaldi grammar constrained to wake phrases.
    Uses ultra-low CPU by skipping Kaldi decoding during acoustic silence.
    """

    def __init__(self, config: WakeWordConfig | None = None, sample_rate: int = 16000):
        self.config = config or CONFIG.wake_word
        self.sample_rate = sample_rate
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._on_wake_callback: Optional[Callable[[], None]] = None
        self._model = None
        self._recognizer = None
        self._lock = threading.Lock()

        self._init_model()

    def _init_model(self) -> None:
        """Loads local Vosk model with grammar restriction."""
        try:
            import vosk
            vosk.SetLogLevel(-1)
            local_model_dir = str(CONFIG.stt.vosk_model_path)
            if os.path.isdir(local_model_dir):
                logger.info("Initializing Vosk wake word detector from local directory '%s'...", local_model_dir)
                self._model = vosk.Model(model_path=local_model_dir)
            else:
                logger.info("Initializing Vosk wake word detector with model '%s'...", self.config.model_name)
                self._model = vosk.Model(model_name=self.config.model_name)

            # Build grammar: wake phrase, secondary phrases, and [unk] (unknown word token)
            phrases = [self.config.wake_phrase.lower()] + [p.lower() for p in self.config.secondary_phrases]
            phrases.append("[unk]")
            grammar_json = json.dumps(list(set(phrases)))

            self._recognizer = vosk.KaldiRecognizer(self._model, self.sample_rate, grammar_json)
            logger.info("Vosk wake word detector ready for phrases: %s", phrases[:-1])
        except Exception as e:
            logger.error("Failed to initialize Vosk wake word detector: %s", e)
            raise

    def is_listening(self) -> bool:
        return self._running and not self._paused

    def pause(self) -> None:
        with self._lock:
            self._paused = True
            logger.debug("Wake word detection paused.")

    def resume(self) -> None:
        with self._lock:
            if self._recognizer:
                self._recognizer.Reset()
            self._paused = False
            logger.debug("Wake word detection resumed.")

    def _matches_wake_phrase(self, text: str) -> bool:
        """Checks if recognized text contains wake phrase or secondary phrases."""
        cleaned = text.strip().lower()
        if not cleaned or cleaned == "[unk]":
            return False

        if self.config.wake_phrase.lower() in cleaned:
            return True
        for phrase in self.config.secondary_phrases:
            if phrase.lower() in cleaned:
                return True
        return False

    def process_audio(self, audio: np.ndarray) -> bool:
        """Directly checks an audio array for wake phrase."""
        if audio is None or len(audio) == 0:
            return False

        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # Convert float32 [-1.0, 1.0] to int16 PCM bytes
        int_data = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16).tobytes()

        import vosk
        phrases = [self.config.wake_phrase.lower()] + [p.lower() for p in self.config.secondary_phrases] + ["[unk]"]
        temp_rec = vosk.KaldiRecognizer(self._model, self.sample_rate, json.dumps(list(set(phrases))))

        chunk_size = 3200
        for i in range(0, len(int_data), chunk_size):
            chunk = int_data[i : i + chunk_size]
            if temp_rec.AcceptWaveform(chunk):
                res = json.loads(temp_rec.Result())
                if self._matches_wake_phrase(res.get("text", "")):
                    return True

        final_res = json.loads(temp_rec.FinalResult())
        return self._matches_wake_phrase(final_res.get("text", ""))

    def start(self, on_wake: Callable[[], None]) -> None:
        """Starts background audio capture thread for continuous wake word monitoring."""
        if self._running:
            return

        self._on_wake_callback = on_wake
        self._running = True
        self._paused = False
        self._thread = threading.Thread(
            target=self._listen_loop,
            name="Alex-WakeWord-Thread",
            daemon=True,
        )
        self._thread.start()
        logger.info("Wake-word detector listening started in background.")

    def stop(self) -> None:
        """Stops background audio capture thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("Wake-word detector stopped.")

    def _listen_loop(self) -> None:
        """Continuous audio input stream loop."""
        block_size = 2048
        silence_thresh = CONFIG.audio.silence_threshold

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=block_size,
                device=CONFIG.audio.input_device,
            ) as stream:
                while self._running:
                    chunk, overflow = stream.read(block_size)
                    with self._lock:
                        if self._paused or not self._running:
                            time.sleep(0.05)
                            continue

                    flat_chunk = chunk.flatten()
                    rms = float(np.sqrt(np.mean(flat_chunk**2)))

                    # Optimize CPU: Skip decoding if room is silent
                    if rms < silence_thresh:
                        continue

                    int_chunk = (np.clip(flat_chunk, -1.0, 1.0) * 32767).astype(np.int16).tobytes()

                    wake_detected = False
                    if self._recognizer.AcceptWaveform(int_chunk):
                        result = json.loads(self._recognizer.Result())
                        text = result.get("text", "")
                        if self._matches_wake_phrase(text):
                            wake_detected = True
                    else:
                        partial = json.loads(self._recognizer.PartialResult())
                        partial_text = partial.get("partial", "")
                        if self._matches_wake_phrase(partial_text):
                            wake_detected = True

                    if wake_detected:
                        logger.info("Wake word detected!")
                        self._recognizer.Reset()
                        if self._on_wake_callback:
                            # Invoke callback
                            try:
                                self._on_wake_callback()
                            except Exception as e:
                                logger.error("Error executing on_wake callback: %s", e)
        except Exception as e:
            if self._running:
                logger.error("Wake word stream encountered error: %s", e)


class MockWakeWordDetector(WakeWordDetector):
    """Mock wake word detector for automated unit testing."""

    def __init__(self):
        self._running = False
        self._paused = False
        self._callback: Optional[Callable[[], None]] = None

    def start(self, on_wake: Callable[[], None]) -> None:
        self._running = True
        self._callback = on_wake

    def stop(self) -> None:
        self._running = False

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def is_listening(self) -> bool:
        return self._running and not self._paused

    def trigger_wake(self) -> None:
        """Simulates wake word detection."""
        if self._running and not self._paused and self._callback:
            self._callback()

    def process_audio(self, audio: np.ndarray) -> bool:
        return True


def create_wake_word_detector(config: WakeWordConfig | None = None) -> WakeWordDetector:
    """Factory creating the wake-word detector."""
    return VoskWakeWordDetector(config)
