"""Phase 1 Acceptance Test: End-to-end voice pipeline verification.
Tests audio capture -> Speech recognition -> Intent routing -> Response generation -> TTS.
"""

from datetime import datetime
import os
import numpy as np
import pytest
import soundfile as sf
import pyttsx3

from config import CONFIG
from core.assistant import Assistant
from core.command_router import CommandRouter
from voice.speech_recognition import FasterWhisperRecognizer
from voice.audio_manager import AudioManager


def test_microphone_hardware_detection():
    audio = AudioManager()
    status = audio.test_microphone(test_duration=0.5)
    assert status["working"] is True, f"Microphone test failed: {status}"
    assert "device_name" in status
    assert status["rms_energy"] >= 0.0


def test_end_to_end_audio_pipeline_date_command(tmp_path):
    """Generates speech audio for 'What is the date today?', runs it through FasterWhisper, and verifies routing."""
    wav_path = str(tmp_path / "date_phrase.wav")

    # Synthesize audio file using Windows SAPI
    engine = pyttsx3.init()
    engine.save_to_file("What is the date today?", wav_path)
    engine.runAndWait()

    # Load audio waveform
    data, sr = sf.read(wav_path)
    if sr != 16000:
        target_len = int(len(data) * 16000 / sr)
        data = np.interp(np.linspace(0, len(data), target_len), np.arange(len(data)), data)
    data = data.astype(np.float32)

    # Transcribe with local faster-whisper
    stt = FasterWhisperRecognizer()
    recognized_text = stt.transcribe(data)
    assert "date" in recognized_text.lower()

    # Route command
    router = CommandRouter()
    response = router.route(recognized_text)

    now = datetime.now()
    assert response.startswith("Today is ")
    assert str(now.year) in response


def test_end_to_end_audio_pipeline_time_command(tmp_path):
    """Generates speech audio for 'What time is it?', runs it through FasterWhisper, and verifies routing."""
    wav_path = str(tmp_path / "time_phrase.wav")

    engine = pyttsx3.init()
    engine.save_to_file("What time is it?", wav_path)
    engine.runAndWait()

    data, sr = sf.read(wav_path)
    if sr != 16000:
        target_len = int(len(data) * 16000 / sr)
        data = np.interp(np.linspace(0, len(data), target_len), np.arange(len(data)), data)
    data = data.astype(np.float32)

    stt = FasterWhisperRecognizer()
    recognized_text = stt.transcribe(data)
    assert "time" in recognized_text.lower()

    router = CommandRouter()
    response = router.route(recognized_text)
    assert response.startswith("It's ")
