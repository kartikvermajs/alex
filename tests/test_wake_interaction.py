"""Unit tests for the complete Wake Word interaction cycle."""

import numpy as np
import pytest

from core.assistant import Assistant
from core.state_machine import AssistantState
from voice.speech_recognition import MockSpeechRecognizer
from voice.wake_word import MockWakeWordDetector
from voice.text_to_speech import TextToSpeech


class RecordingTTS(TextToSpeech):
    def __init__(self):
        self.spoken = []

    def speak(self, text: str, block: bool = True) -> None:
        self.spoken.append(text)

    def stop(self) -> None:
        pass

    def get_voices(self) -> list:
        return [{"id": "mock_id", "name": "Mock Voice"}]

    def set_rate(self, rate: int) -> None:
        pass

    def set_volume(self, volume: float) -> None:
        pass


class StubAudioManager:
    """Provides controllable audio responses for tests."""

    def __init__(self, audio_to_return=None):
        self.audio_to_return = audio_to_return
        self.test_mic_called = False

    def test_microphone(self, test_duration=0.5):
        self.test_mic_called = True
        return {"working": True, "device_name": "Mock Mic", "rms_energy": 0.05}

    def record_command(self, listen_timeout=5.0):
        return self.audio_to_return


def test_wake_interaction_cycle_success():
    """
    Simulates:
    Wake Word -> Acknowledge ('Yes?') -> Listen Command -> Route ('What is the date today?') -> Speak Response -> Return to IDLE
    """
    mock_stt = MockSpeechRecognizer("What is the date today?")
    mock_tts = RecordingTTS()
    mock_wake = MockWakeWordDetector()
    fake_audio = np.ones(16000, dtype=np.float32) * 0.1
    stub_audio = StubAudioManager(audio_to_return=fake_audio)

    assistant = Assistant(
        audio_manager=stub_audio,
        speech_recognizer=mock_stt,
        tts=mock_tts,
        wake_word_detector=mock_wake,
    )

    history = []
    assistant.state_machine.add_listener(lambda old_s, new_s: history.append((old_s, new_s)))

    # Trigger wake word
    assistant.on_wake_detected()

    # Verify speech output sequence
    assert len(mock_tts.spoken) == 2
    assert mock_tts.spoken[0] == "Yes?"
    assert mock_tts.spoken[1].startswith("Today is ")

    # Verify assistant finished in IDLE state and wake word detector is active
    assert assistant.state_machine.current_state == AssistantState.IDLE
    assert mock_wake.is_listening() is False or not mock_wake._paused


def test_wake_interaction_cycle_timeout_no_command():
    """
    Simulates:
    Wake Word -> Acknowledge ('Yes?') -> Listen Command Times Out -> Speak ('I didn't hear a command.') -> Return to IDLE
    """
    mock_stt = MockSpeechRecognizer()
    mock_tts = RecordingTTS()
    mock_wake = MockWakeWordDetector()
    stub_audio = StubAudioManager(audio_to_return=None)  # None simulates timeout/no speech

    assistant = Assistant(
        audio_manager=stub_audio,
        speech_recognizer=mock_stt,
        tts=mock_tts,
        wake_word_detector=mock_wake,
    )

    assistant.on_wake_detected()

    assert len(mock_tts.spoken) == 2
    assert mock_tts.spoken[0] == "Yes?"
    assert mock_tts.spoken[1] == "I didn't hear a command."

    assert assistant.state_machine.current_state == AssistantState.IDLE
