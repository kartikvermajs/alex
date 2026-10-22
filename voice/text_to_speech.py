"""Text-to-speech abstraction supporting Kokoro offline neural TTS and Windows SAPI fallback."""

from abc import ABC, abstractmethod
import os
from pathlib import Path
import queue
import re
import threading
import time
from typing import Any, List, Optional
import numpy as np
import sounddevice as sd

from config import TTSConfig, CONFIG
from storage.logger import logger


class TextToSpeech(ABC):
    """Abstract base class for Text-to-Speech engines."""

    @abstractmethod
    def speak(self, text: str, block: bool = True) -> None:
        """Speak the provided text."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop current speech output."""
        pass

    @abstractmethod
    def get_voices(self) -> List[dict]:
        """List available voices."""
        pass

    def set_rate(self, rate: int) -> None:
        """Set speaking rate (or speed multiplier)."""
        pass

    def set_volume(self, volume: float) -> None:
        """Set speaking volume (0.0 to 1.0)."""
        pass

    def set_voice(self, voice_name_or_id: str) -> None:
        """Set the active voice."""
        pass


def clean_text_for_speech(text: str) -> str:
    """
    Cleans text of markdown links, URLs, and formatting so it speaks naturally
    without spelling out raw URL protocols or syntax.
    """
    if not text:
        return ""
    # Convert markdown links: [Anchor](url) -> Anchor
    cleaned = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Remove raw URLs
    cleaned = re.sub(r'https?://\S+', '', cleaned)
    # Remove markdown formatting characters
    cleaned = re.sub(r'[*#_`]', '', cleaned)
    # Format bullet lines: "- Item" -> "Item,"
    lines = cleaned.splitlines()
    processed_lines = []
    for line in lines:
        line_s = line.strip()
        if line_s.startswith("- ") or line_s.startswith("• "):
            processed_lines.append(line_s[2:].strip() + ",")
        else:
            processed_lines.append(line_s)
    joined = " ".join([l for l in processed_lines if l])
    # Clean trailing commas
    joined = re.sub(r',\s*\.', '.', joined)
    joined = re.sub(r',\s*$', '.', joined)
    return " ".join(joined.split()).strip()


class KokoroTTS(TextToSpeech):
    """
    Ultra-natural, human-like offline Text-to-Speech powered by Kokoro ONNX.
    Operates 100% locally with zero cloud API dependencies.
    """

    DEFAULT_VOICES = [
        {"id": "af_bella", "name": "Bella (American Female - Warm & Natural)", "lang": "en-us"},
        {"id": "af_sarah", "name": "Sarah (American Female - Professional)", "lang": "en-us"},
        {"id": "af_nicole", "name": "Nicole (American Female - Gentle)", "lang": "en-us"},
        {"id": "af_sky", "name": "Sky (American Female - Bright)", "lang": "en-us"},
        {"id": "am_michael", "name": "Michael (American Male - Smooth & Clear)", "lang": "en-us"},
        {"id": "am_adam", "name": "Adam (American Male - Deep)", "lang": "en-us"},
        {"id": "bf_emma", "name": "Emma (British Female - Expressive)", "lang": "en-gb"},
        {"id": "bm_george", "name": "George (British Male - Classic)", "lang": "en-gb"},
    ]

    def __init__(self, config: TTSConfig | None = None):
        self.config = config or CONFIG.tts
        self._voice = self.config.voice_name
        self._speed = self.config.speed
        self._volume = max(0.0, min(1.0, self.config.volume))
        self._model_path = Path(self.config.kokoro_model_path)
        self._voices_path = Path(self.config.kokoro_voices_path)
        self._kokoro = None

        self._queue: queue.Queue = queue.Queue()
        self._running = True
        self._is_speaking = False
        self._lock = threading.Lock()

        self._load_kokoro()

        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="Alex-Kokoro-Worker",
            daemon=True,
        )
        self._worker_thread.start()

    def _load_kokoro(self) -> None:
        if not self._model_path.exists() or not self._voices_path.exists():
            raise FileNotFoundError(
                f"Kokoro model files missing: {self._model_path} or {self._voices_path}"
            )
        try:
            import kokoro_onnx
            logger.info("Initializing Kokoro ONNX engine from %s...", self._model_path.name)
            self._kokoro = kokoro_onnx.Kokoro(
                model_path=str(self._model_path),
                voices_path=str(self._voices_path),
            )
            logger.info("Kokoro offline TTS engine ready (active voice: %s).", self._voice)
        except Exception as e:
            logger.error("Failed to initialize Kokoro engine: %s", e)
            raise

    def _worker_loop(self) -> None:
        while self._running:
            try:
                item = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if item is None:
                break

            action, data, done_event = item
            try:
                if action == "speak":
                    text = data
                    logger.info("Alex speaking (Kokoro): \"%s\"", text)
                    with self._lock:
                        self._is_speaking = True

                    # Determine language from voice prefix
                    lang = "en-gb" if self._voice.startswith("b") else "en-us"
                    samples, sr = self._kokoro.create(
                        text=text,
                        voice=self._voice,
                        speed=self._speed,
                        lang=lang,
                    )

                    if self._volume != 1.0:
                        samples = samples * self._volume

                    sd.play(samples, samplerate=sr)
                    sd.wait()

                elif action == "stop":
                    sd.stop()
                    with self._lock:
                        self._is_speaking = False

                elif action == "voice":
                    self._voice = data
                elif action == "speed":
                    self._speed = data
                elif action == "volume":
                    self._volume = max(0.0, min(1.0, data))

            except Exception as e:
                logger.error("Error in Kokoro synthesis/playback: %s", e)
            finally:
                with self._lock:
                    self._is_speaking = False
                if done_event is not None:
                    done_event.set()
                self._queue.task_done()

    def speak(self, text: str, block: bool = True) -> None:
        if not text or not text.strip():
            return
        spoken_text = clean_text_for_speech(text)
        if not spoken_text:
            return
        done_event = threading.Event() if block else None
        self._queue.put(("speak", spoken_text, done_event))
        if block and done_event is not None:
            done_event.wait()

    def stop(self) -> None:
        sd.stop()
        self._queue.put(("stop", None, None))

    def get_voices(self) -> List[dict]:
        return list(self.DEFAULT_VOICES)

    def set_rate(self, rate: int) -> None:
        """Translates rate (WPM) to speed multiplier (180 WPM ~ 1.0x)."""
        speed = max(0.5, min(2.0, rate / 180.0))
        self._speed = speed
        self._queue.put(("speed", speed, None))

    def set_speed(self, speed: float) -> None:
        self._speed = max(0.5, min(2.0, speed))
        self._queue.put(("speed", self._speed, None))

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(1.0, volume))
        self._queue.put(("volume", self._volume, None))

    def set_voice(self, voice_name_or_id: str) -> None:
        clean = voice_name_or_id.strip().lower()
        self._voice = clean
        self._queue.put(("voice", clean, None))

    def shutdown(self) -> None:
        self._running = False
        self.stop()
        self._queue.put(None)
        self._worker_thread.join(timeout=2.0)


class WindowsSAPITTS(TextToSpeech):
    """
    Local Windows SAPI Text-to-Speech using pyttsx3.
    Serves as reliable baseline and offline fallback.
    """

    def __init__(self, config: TTSConfig | None = None):
        self.config = config or CONFIG.tts
        self._rate = self.config.rate
        self._volume = self.config.volume
        self._voice_id = self.config.voice_id

        self._queue: queue.Queue = queue.Queue()
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="Alex-SAPI-Worker",
            daemon=True,
        )
        self._worker_thread.start()
        logger.info("Windows SAPI TTS engine initialized.")

    def _worker_loop(self) -> None:
        import pythoncom
        import pyttsx3

        pythoncom.CoInitialize()
        engine: Optional[pyttsx3.Engine] = None
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", self._rate)
            engine.setProperty("volume", self._volume)
            if self._voice_id:
                engine.setProperty("voice", self._voice_id)

            while self._running:
                try:
                    item = self._queue.get(timeout=0.2)
                except queue.Empty:
                    continue

                if item is None:
                    break

                action, data, done_event = item
                try:
                    if action == "speak":
                        logger.info("Alex speaking (SAPI): \"%s\"", data)
                        engine.say(data)
                        engine.runAndWait()
                    elif action == "rate":
                        self._rate = data
                        engine.setProperty("rate", data)
                    elif action == "volume":
                        self._volume = data
                        engine.setProperty("volume", data)
                    elif action == "voice":
                        self._voice_id = data
                        engine.setProperty("voice", data)
                    elif action == "stop":
                        engine.stop()
                except Exception as ex:
                    logger.error("SAPI TTS error: %s", ex)
                finally:
                    if done_event is not None:
                        done_event.set()
                    self._queue.task_done()
        finally:
            if engine:
                try:
                    engine.stop()
                except Exception:
                    pass
            pythoncom.CoUninitialize()

    def speak(self, text: str, block: bool = True) -> None:
        if not text or not text.strip():
            return
        spoken_text = clean_text_for_speech(text)
        if not spoken_text:
            return
        done_event = threading.Event() if block else None
        self._queue.put(("speak", spoken_text, done_event))
        if block and done_event is not None:
            done_event.wait()

    def stop(self) -> None:
        self._queue.put(("stop", None, None))

    def get_voices(self) -> List[dict]:
        try:
            import pythoncom
            import pyttsx3
            pythoncom.CoInitialize()
            engine = pyttsx3.init()
            voices = engine.getProperty("voices")
            res = [
                {"id": v.id, "name": v.name, "languages": getattr(v, "languages", [])}
                for v in voices
            ]
            pythoncom.CoUninitialize()
            return res
        except Exception as e:
            logger.error("Error retrieving SAPI voices: %s", e)
            return []

    def set_rate(self, rate: int) -> None:
        self._rate = rate
        self._queue.put(("rate", rate, None))

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(1.0, volume))
        self._queue.put(("volume", self._volume, None))

    def set_voice(self, voice_id: str) -> None:
        self._voice_id = voice_id
        self._queue.put(("voice", voice_id, None))

    def shutdown(self) -> None:
        self._running = False
        self._queue.put(None)
        self._worker_thread.join(timeout=2.0)


def create_tts_engine(config: TTSConfig | None = None) -> TextToSpeech:
    """Factory to create TTS engine based on configuration, with SAPI fallback."""
    cfg = config or CONFIG.tts
    if cfg.engine.lower() == "kokoro":
        try:
            return KokoroTTS(cfg)
        except Exception as e:
            logger.warning("Could not initialize Kokoro TTS (%s). Falling back to Windows SAPI.", e)
            return WindowsSAPITTS(cfg)
    return WindowsSAPITTS(cfg)
