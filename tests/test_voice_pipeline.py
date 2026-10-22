"""Unit tests for Voice Pipeline: Speech Recognizer, TTS, and Assistant integration."""

import numpy as np
import pytest

from core.assistant import Assistant
from core.state_machine import AssistantState
from voice.speech_recognition import MockSpeechRecognizer
from voice.text_to_speech import TextToSpeech


class MockTTS(TextToSpeech):
    def __init__(self):
        self.spoken_texts = []

    def speak(self, text: str, block: bool = True) -> None:
        self.spoken_texts.append(text)

    def stop(self) -> None:
        pass

    def get_voices(self) -> list:
        return [{"id": "mock_voice", "name": "Mock Voice"}]

    def set_rate(self, rate: int) -> None:
        pass

    def set_volume(self, volume: float) -> None:
        pass


def test_assistant_with_mock_pipeline():
    mock_stt = MockSpeechRecognizer("What is the date today?")
    mock_tts = MockTTS()
    assistant = Assistant(
        speech_recognizer=mock_stt,
        tts=mock_tts,
    )

    status = assistant.initialize()
    assert status["microphone"] is True
    assert status["speech_recognition"] is True
    assert status["tts"] is True

    # Process fake audio array
    dummy_audio = np.zeros(16000, dtype=np.float32)
    response = assistant.process_audio(dummy_audio)

    assert response.startswith("Today is ")
    assert response in mock_tts.spoken_texts
    assert assistant.state_machine.current_state == AssistantState.IDLE


def test_assistant_unrecognized_speech():
    mock_stt = MockSpeechRecognizer("")
    mock_tts = MockTTS()
    assistant = Assistant(
        speech_recognizer=mock_stt,
        tts=mock_tts,
    )

    dummy_audio = np.zeros(16000, dtype=np.float32)
    response = assistant.process_audio(dummy_audio)

    assert response == "I didn't understand that."
    assert "I didn't understand that." in mock_tts.spoken_texts
    assert assistant.state_machine.current_state == AssistantState.IDLE


def test_assistant_process_text_command():
    mock_stt = MockSpeechRecognizer()
    mock_tts = MockTTS()
    assistant = Assistant(
        speech_recognizer=mock_stt,
        tts=mock_tts,
    )

    response = assistant.process_text_command("What time is it?")
    assert response.startswith("It's ")
    assert response in mock_tts.spoken_texts
    assert assistant.state_machine.current_state == AssistantState.IDLE
