"""Speech recognition abstraction and local engine implementations (faster-whisper, Vosk)."""

from abc import ABC, abstractmethod
import json
import os
from pathlib import Path
from typing import Optional
import numpy as np

from config import STTConfig, CONFIG
from storage.logger import logger


class SpeechRecognizer(ABC):
    """Abstract base class for Speech Recognition engines."""

    @abstractmethod
    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribes a 1D float32 16kHz audio array into text."""
        pass

    @abstractmethod
    def is_ready(self) -> bool:
        """Returns True if the engine is loaded and ready."""
        pass


class FasterWhisperRecognizer(SpeechRecognizer):
    """Local offline speech recognition using faster-whisper."""

    def __init__(self, config: STTConfig | None = None):
        self.config = config or CONFIG.stt
        self.model_size = self.config.model_size
        self.device = self.config.device
        self.compute_type = self.config.compute_type
        self._model = None
        self._load_model()

    def _load_model(self) -> None:
        try:
            from faster_whisper import WhisperModel
            logger.info(
                "Loading faster-whisper model '%s' (device=%s, compute_type=%s)...",
                self.model_size,
                self.device,
                self.compute_type,
            )
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info("faster-whisper model '%s' loaded successfully.", self.model_size)
        except Exception as e:
            logger.error("Failed to load faster-whisper model: %s", e)
            self._model = None
            raise

    def is_ready(self) -> bool:
        return self._model is not None

    def transcribe(self, audio: np.ndarray) -> str:
        if not self.is_ready():
            raise RuntimeError("faster-whisper model is not loaded.")

        if audio is None or len(audio) == 0:
            return ""

        # Ensure float32 1D numpy array
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        if audio.ndim > 1:
            audio = audio.flatten()

        try:
            segments, info = self._model.transcribe(
                audio,
                language=self.config.language,
                beam_size=5,
                vad_filter=True,
            )
            text_parts = [segment.text.strip() for segment in segments]
            full_text = " ".join(text_parts).strip()
            logger.info("faster-whisper recognized: \"%s\"", full_text)
            return full_text
        except Exception as e:
            logger.error("Error during transcription: %s", e)
            return ""


class VoskRecognizer(SpeechRecognizer):
    """Local offline speech recognition using Vosk."""

    def __init__(self, model_path: str | None = None):
        self.model_path = model_path or CONFIG.stt.vosk_model_path
        self._model = None
        self._load_model()

    def _load_model(self) -> None:
        import vosk
        if not os.path.isdir(self.model_path):
            logger.warning("Vosk model path not found: %s", self.model_path)
            self._model = None
            return

        try:
            logger.info("Loading Vosk model from: %s", self.model_path)
            vosk.SetLogLevel(-1)
            self._model = vosk.Model(self.model_path)
            logger.info("Vosk model loaded successfully.")
        except Exception as e:
            logger.error("Failed to load Vosk model: %s", e)
            self._model = None

    def is_ready(self) -> bool:
        return self._model is not None

    def transcribe(self, audio: np.ndarray) -> str:
        if not self.is_ready():
            raise RuntimeError("Vosk model is not loaded.")

        if audio is None or len(audio) == 0:
            return ""

        import vosk

        # Convert float32 [-1.0, 1.0] to int16 PCM bytes
        audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
        raw_bytes = audio_int16.tobytes()

        recognizer = vosk.KaldiRecognizer(self._model, CONFIG.audio.sample_rate)
        recognizer.AcceptWaveform(raw_bytes)
        res = json.loads(recognizer.FinalResult())
        text = res.get("text", "").strip()
        logger.info("Vosk recognized: \"%s\"", text)
        return text


class MockSpeechRecognizer(SpeechRecognizer):
    """Mock recognizer for deterministic automated unit testing."""

    def __init__(self, predefined_response: str = ""):
        self.response = predefined_response
        self._ready = True

    def set_response(self, text: str) -> None:
        self.response = text

    def is_ready(self) -> bool:
        return self._ready

    def transcribe(self, audio: np.ndarray) -> str:
        return self.response


def create_speech_recognizer(config: STTConfig | None = None) -> SpeechRecognizer:
    """Factory to create speech recognizer according to configuration."""
    cfg = config or CONFIG.stt
    engine_type = cfg.engine.lower()
    if engine_type == "faster-whisper":
        return FasterWhisperRecognizer(cfg)
    elif engine_type == "vosk":
        return VoskRecognizer(cfg.vosk_model_path)
    else:
        raise ValueError(f"Unknown speech recognition engine: {cfg.engine}")
