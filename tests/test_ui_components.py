"""Unit tests for PySide6 GUI Dashboard and System Tray."""

import sys
import pytest
from PySide6.QtWidgets import QApplication

from core.assistant import Assistant
from voice.speech_recognition import MockSpeechRecognizer
from voice.wake_word import MockWakeWordDetector
from voice.text_to_speech import TextToSpeech
from ui.main_window import AlexMainWindow
from ui.tray import AlexSystemTray


class FakeTTS(TextToSpeech):
    def __init__(self):
        self.spoken = []

    def speak(self, text: str, block: bool = True) -> None:
        self.spoken.append(text)

    def stop(self) -> None:
        pass

    def get_voices(self) -> list:
        return [{"id": "v1", "name": "V1"}]

    def set_rate(self, rate: int) -> None:
        pass

    def set_volume(self, volume: float) -> None:
        pass


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_main_window_tabs_and_controls(qapp):
    mock_stt = MockSpeechRecognizer("What is the date today?")
    mock_tts = FakeTTS()
    mock_wake = MockWakeWordDetector()
    assistant = Assistant(
        speech_recognizer=mock_stt,
        tts=mock_tts,
        wake_word_detector=mock_wake,
    )

    tray = AlexSystemTray(assistant)
    window = AlexMainWindow(assistant, tray=tray)

    assert window.tabs.count() == 6
    tab_names = [window.tabs.tabText(i) for i in range(window.tabs.count())]
    assert "Dashboard" in tab_names
    assert "General" in tab_names
    assert "Microphone" in tab_names
    assert "Wake Word" in tab_names
    assert "Applications" in tab_names
    assert "Logs" in tab_names

    # Test quick manual command entry
    window.cmd_input.setText("What time is it?")
    window._execute_manual_command()
    assert window.last_cmd_label.text() == "What time is it?"
    assert window.last_resp_label.text().startswith("It's ")

    # Clean up
    tray.hide()
    window.close()
