"""Windows System Tray integration for Alex."""

import os
import subprocess
import sys
from typing import Callable, Optional
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from config import LOG_FILE
from storage.logger import logger
from ui.icon_helper import create_alex_icon


class AlexSystemTray(QSystemTrayIcon):
    """Manages the Windows system tray icon, context menu, and background actions."""

    show_window_signal = Signal()
    status_changed_signal = Signal(str)

    def __init__(self, assistant, parent=None):
        super().__init__(parent)
        self.assistant = assistant
        self._is_paused = False

        self.setIcon(create_alex_icon(64, active=True))
        self.setToolTip("Alex Voice Assistant — Listening")

        self._build_menu()
        self.activated.connect(self._on_tray_activated)

    def _build_menu(self) -> None:
        menu = QMenu()

        # Title
        title_action = QAction("Alex — Voice Assistant", menu)
        title_action.setEnabled(False)
        menu.addAction(title_action)

        # Status item
        self.status_action = QAction("Status: Listening", menu)
        self.status_action.setEnabled(False)
        menu.addAction(self.status_action)
        menu.addSeparator()

        # Pause / Resume Listening
        self.pause_resume_action = QAction("Pause Listening", menu)
        self.pause_resume_action.triggered.connect(self.toggle_listening)
        menu.addAction(self.pause_resume_action)

        # Open Dashboard / Settings
        open_action = QAction("Settings / Dashboard", menu)
        open_action.triggered.connect(self.open_dashboard)
        menu.addAction(open_action)
        menu.addSeparator()

        # Diagnostic actions
        test_mic_action = QAction("Test Microphone", menu)
        test_mic_action.triggered.connect(self.test_microphone)
        menu.addAction(test_mic_action)

        test_tts_action = QAction("Test Voice (TTS)", menu)
        test_tts_action.triggered.connect(self.test_voice)
        menu.addAction(test_tts_action)

        view_logs_action = QAction("View Logs", menu)
        view_logs_action.triggered.connect(self.view_logs)
        menu.addAction(view_logs_action)
        menu.addSeparator()

        # Exit Alex
        exit_action = QAction("Exit Alex", menu)
        exit_action.triggered.connect(self.exit_app)
        menu.addAction(exit_action)

        self.setContextMenu(menu)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.open_dashboard()

    def open_dashboard(self) -> None:
        self.show_window_signal.emit()

    def toggle_listening(self) -> None:
        if self._is_paused:
            self.assistant.wake_word.resume()
            self._is_paused = False
            self.pause_resume_action.setText("Pause Listening")
            self.update_status("Listening")
            self.showMessage("Alex", "Listening resumed. Say 'Hey Alex' to begin.", QSystemTrayIcon.Information, 2000)
        else:
            self.assistant.wake_word.pause()
            self._is_paused = True
            self.pause_resume_action.setText("Resume Listening")
            self.update_status("Paused")
            self.showMessage("Alex", "Listening paused.", QSystemTrayIcon.Information, 2000)

    def update_status(self, status_text: str) -> None:
        self.status_action.setText(f"Status: {status_text}")
        self.setToolTip(f"Alex Voice Assistant — {status_text}")
        is_active = (status_text.lower() != "paused" and status_text.lower() != "error")
        self.setIcon(create_alex_icon(64, active=is_active))
        self.status_changed_signal.emit(status_text)

    def test_microphone(self) -> None:
        mic_report = self.assistant.audio.test_microphone(test_duration=0.5)
        if mic_report.get("working"):
            msg = f"Microphone OK ({mic_report.get('device_name')}). RMS: {mic_report.get('rms_energy', 0):.4f}"
            self.showMessage("Microphone Test", msg, QSystemTrayIcon.Information, 3000)
        else:
            self.showMessage("Microphone Test", "Microphone check failed!", QSystemTrayIcon.Warning, 3000)

    def test_voice(self) -> None:
        self.assistant.tts.speak("Alex voice check successful.", block=False)
        self.showMessage("Voice Test", "Speaking voice check...", QSystemTrayIcon.Information, 2000)

    def view_logs(self) -> None:
        try:
            if os.path.exists(LOG_FILE):
                os.startfile(str(LOG_FILE))
            else:
                self.showMessage("Logs", "No log file found yet.", QSystemTrayIcon.Information, 2000)
        except Exception as e:
            logger.error("Failed to open log file: %s", e)

    def exit_app(self) -> None:
        logger.info("Exiting Alex via system tray.")
        self.assistant.shutdown()
        QApplication.quit()
