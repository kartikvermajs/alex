"""Alex configuration module."""

from dataclasses import dataclass, field
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "alex.log"

MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class AudioConfig:
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    input_device: int | None = None  # None selects default Windows input device
    silence_threshold: float = 0.015  # RMS energy threshold for speech detection
    silence_duration: float = 1.2     # Seconds of silence to conclude speech
    max_record_duration: float = 8.0  # Maximum speech record duration in seconds
    min_record_duration: float = 0.5  # Minimum speech duration to process


@dataclass
class TTSConfig:
    engine: str = "kokoro"  # "kokoro" (natural offline neural voice) or "sapi" (legacy Windows TTS)
    voice_name: str = "af_bella"  # e.g. af_bella, af_sarah, am_michael, am_adam, bf_emma
    speed: float = 1.05   # Playback speed (1.0 = normal, 1.05 = slightly brisk and natural)
    rate: int = 190       # Words per minute (used for SAPI fallback)
    volume: float = 1.0   # 0.0 to 1.0
    voice_id: str | None = None  # None selects system default for SAPI
    kokoro_model_path: str = str(MODELS_DIR / "kokoro" / "kokoro-v1.0.onnx")
    kokoro_voices_path: str = str(MODELS_DIR / "kokoro" / "voices-v1.0.bin")


@dataclass
class STTConfig:
    engine: str = "faster-whisper"  # "faster-whisper" or "vosk"
    model_size: str = "tiny.en"     # tiny.en, base.en
    device: str = "cpu"             # cpu or cuda
    compute_type: str = "int8"      # int8, float16
    language: str = "en"
    vosk_model_path: str = str(MODELS_DIR / "vosk-model-small-en-us")


@dataclass
class WakeWordConfig:
    enabled: bool = True
    wake_phrase: str = "hey alex"
    secondary_phrases: list[str] = field(default_factory=lambda: ["alex"])
    model_name: str = "vosk-model-small-en-us-0.15"
    sensitivity: float = 0.5
    acknowledgement_phrase: str = "Yes?"
    listen_timeout: float = 6.0  # Short command-listening timeout after wake acknowledgement


@dataclass
class AssistantConfig:
    name: str = "Alex"
    wake_phrase: str = "hey alex"
    speak_startup_greeting: bool = False
    audio: AudioConfig = field(default_factory=AudioConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    wake_word: WakeWordConfig = field(default_factory=WakeWordConfig)


# Default global config instance
CONFIG = AssistantConfig()
