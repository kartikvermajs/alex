"""Unit tests for Wake Word detection (Vosk and Mock detectors)."""

import os
import numpy as np
import pytest
import pyttsx3
import soundfile as sf

from config import WakeWordConfig
from voice.wake_word import VoskWakeWordDetector, MockWakeWordDetector


def synthesize_speech(text: str, output_path: str) -> np.ndarray:
    """Synthesizes speech audio using local Windows SAPI and returns 16kHz float32 array."""
    engine = pyttsx3.init()
    engine.save_to_file(text, output_path)
    engine.runAndWait()

    data, sr = sf.read(output_path)
    if sr != 16000:
        target_len = int(len(data) * 16000 / sr)
        data = np.interp(np.linspace(0, len(data), target_len), np.arange(len(data)), data)
    return data.astype(np.float32)


def test_mock_wake_word_detector():
    detector = MockWakeWordDetector()
    events = []

    def on_wake():
        events.append("wake")

    detector.start(on_wake)
    assert detector.is_listening() is True

    detector.trigger_wake()
    assert len(events) == 1

    detector.pause()
    assert detector.is_listening() is False

    detector.trigger_wake()
    assert len(events) == 1  # Should not trigger while paused

    detector.resume()
    assert detector.is_listening() is True

    detector.trigger_wake()
    assert len(events) == 2

    detector.stop()
    assert detector.is_listening() is False


def test_vosk_wake_word_detects_hey_alex(tmp_path):
    """Verifies that Vosk detects the wake phrase 'Hey Alex'."""
    wav_path = str(tmp_path / "hey_alex.wav")
    audio = synthesize_speech("Hey Alex", wav_path)

    detector = VoskWakeWordDetector()
    detected = detector.process_audio(audio)
    assert detected is True, "Expected 'Hey Alex' to trigger wake word detector."


def test_vosk_wake_word_ignores_random_conversation(tmp_path):
    """Verifies that Vosk does not falsely activate on random speech."""
    wav_path = str(tmp_path / "random_talk.wav")
    audio = synthesize_speech("Good morning everyone how are you doing today?", wav_path)

    detector = VoskWakeWordDetector()
    detected = detector.process_audio(audio)
    assert detected is False, "Random conversation should not trigger wake word detector."


def test_vosk_wake_word_ignores_silence():
    """Verifies that silence does not trigger wake word."""
    silence = np.zeros(16000 * 2, dtype=np.float32)
    detector = VoskWakeWordDetector()
    detected = detector.process_audio(silence)
    assert detected is False
