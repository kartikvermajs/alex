"""Alex Main Dashboard and Settings Window (PySide6)."""

import os
from pathlib import Path
import sys
from typing import Any, Optional

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QCloseEvent, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import CONFIG, LOG_FILE
from core.state_machine import AssistantState
from storage.logger import logger
from storage.settings import SETTINGS_STORE, UserSettings
from system.application_manager import AppInfo, GLOBAL_APP_MANAGER
from system.startup import is_startup_enabled, toggle_startup
from ui.icon_helper import create_alex_icon


DARK_STYLESHEET = """
QMainWindow, QDialog {
    background-color: #1a1b22;
    color: #e0e0e6;
    font-family: 'Segoe UI', Arial, sans-serif;
}
QTabWidget::pane {
    border: 1px solid #2e303d;
    background-color: #1a1b22;
    border-radius: 8px;
}
QTabBar::tab {
    background-color: #242633;
    color: #9ba0b4;
    padding: 10px 18px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 600;
}
QTabBar::tab:selected {
    background-color: #3b82f6;
    color: #ffffff;
}
QTabBar::tab:hover:!selected {
    background-color: #2d3040;
    color: #ffffff;
}
QGroupBox {
    background-color: #222430;
    border: 1px solid #2e303d;
    border-radius: 8px;
    margin-top: 18px;
    padding-top: 16px;
    font-weight: 600;
    color: #93c5fd;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QPushButton {
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #2563eb;
}
QPushButton:pressed {
    background-color: #1d4ed8;
}
QPushButton#secondaryBtn {
    background-color: #2d3040;
    color: #e0e0e6;
    border: 1px solid #3e4256;
}
QPushButton#secondaryBtn:hover {
    background-color: #373b4e;
}
QLineEdit, QComboBox, QSpinBox {
    background-color: #242633;
    color: #ffffff;
    border: 1px solid #373b4e;
    border-radius: 6px;
    padding: 6px 10px;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #3b82f6;
}
QTableWidget {
    background-color: #20222d;
    color: #e0e0e6;
    gridline-color: #2d3040;
    border: 1px solid #2e303d;
    border-radius: 6px;
}
QHeaderView::section {
    background-color: #282a38;
    color: #93c5fd;
    padding: 6px;
    border: none;
    font-weight: 600;
}
QTextEdit {
    background-color: #16171d;
    color: #a7f3d0;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 11px;
    border: 1px solid #2e303d;
    border-radius: 6px;
}
"""


class AddAppDialog(QDialog):
    """Dialog to manually register a new application."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Application to Alex")
        self.setFixedSize(480, 260)
        self.setStyleSheet(DARK_STYLESHEET)

        layout = QFormLayout(self)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Spotify")

        self.proc_edit = QLineEdit()
        self.proc_edit.setPlaceholderText("e.g. Spotify.exe")

        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Full executable path or command")
        browse_btn = QPushButton("Browse...")
        browse_btn.setObjectName("secondaryBtn")
        browse_btn.clicked.connect(self._browse_path)
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(browse_btn)

        self.alias_edit = QLineEdit()
        self.alias_edit.setPlaceholderText("e.g. spotify, music app (comma separated)")

        layout.addRow("Application Name:", self.name_edit)
        layout.addRow("Process Name:", self.proc_edit)
        layout.addRow("Launch Path:", path_layout)
        layout.addRow("Voice Aliases:", self.alias_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_path(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Application Executable", "C:\\", "Executables (*.exe *.cmd *.bat)"
        )
        if file_path:
            self.path_edit.setText(file_path)
            if not self.proc_edit.text():
                self.proc_edit.setText(Path(file_path).name)
            if not self.name_edit.text():
                self.name_edit.setText(Path(file_path).stem.capitalize())

    def get_app_info(self) -> Optional[AppInfo]:
        name = self.name_edit.text().strip()
        proc = self.proc_edit.text().strip()
        path = self.path_edit.text().strip()
        if not name or not proc:
            return None
        aliases = [a.strip() for a in self.alias_edit.text().split(",") if a.strip()]
        aliases.append(name.lower())
        return AppInfo(
            key=name.lower().replace(" ", "_"),
            display_name=name,
            process_names=[proc],
            launch_command=path or proc,
            aliases=list(set(aliases)),
        )


class AlexMainWindow(QMainWindow):
    """Main dashboard and settings window for Alex."""

    def __init__(self, assistant, tray=None):
        super().__init__()
        self.assistant = assistant
        self.tray = tray
        self.settings = SETTINGS_STORE.get()

        self.setWindowTitle("Alex — Local Windows Voice Assistant")
        self.resize(780, 560)
        self.setWindowIcon(create_alex_icon(64, active=True))
        self.setStyleSheet(DARK_STYLESHEET)

        self._build_ui()
        self._load_settings_into_ui()

        # Connect state changes
        self.assistant.state_machine.add_listener(self._on_state_change)

        # Log refresh timer
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self._refresh_logs)
        self.log_timer.start(2500)

    def _build_ui(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Top Status Header ---
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 8, 10, 8)

        title_label = QLabel("ALEX")
        title_font = QFont("Segoe UI", 20, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #60a5fa;")

        self.status_badge = QLabel("● LISTENING")
        self.status_badge.setStyleSheet(
            "background-color: #064e3b; color: #34d399; font-weight: bold; padding: 6px 14px; border-radius: 12px;"
        )

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.status_badge)
        main_layout.addWidget(header_widget)

        # --- Tab Widget ---
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self._build_dashboard_tab()
        self._build_general_tab()
        self._build_audio_tab()
        self._build_wake_tab()
        self._build_apps_tab()
        self._build_logs_tab()

    def _build_dashboard_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Callout phrase
        hint_label = QLabel('"Say \'Hey Alex\' or speak a command below..."')
        hint_label.setStyleSheet("font-size: 14px; color: #93c5fd; font-style: italic; margin-bottom: 8px;")
        hint_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint_label)

        # Last Interaction Card
        card_group = QGroupBox("Recent Interaction")
        card_layout = QFormLayout(card_group)
        self.last_cmd_label = QLabel("None yet")
        self.last_cmd_label.setStyleSheet("color: #ffffff; font-weight: 600;")
        self.last_resp_label = QLabel("None yet")
        self.last_resp_label.setStyleSheet("color: #a7f3d0; font-weight: 600;")

        card_layout.addRow("Last Command:", self.last_cmd_label)
        card_layout.addRow("Last Response:", self.last_resp_label)
        layout.addWidget(card_group)

        # Component Health Checklist
        health_group = QGroupBox("System Health Diagnostics")
        health_layout = QHBoxLayout(health_group)

        self.mic_check = QLabel("Microphone: ✓ OK")
        self.mic_check.setStyleSheet("color: #34d399; font-weight: 600;")
        self.stt_check = QLabel("Speech Recognition: ✓ OK")
        self.stt_check.setStyleSheet("color: #34d399; font-weight: 600;")
        self.tts_check = QLabel("Voice (TTS): ✓ OK")
        self.tts_check.setStyleSheet("color: #34d399; font-weight: 600;")
        self.wake_check = QLabel("Wake Word: ✓ OK")
        self.wake_check.setStyleSheet("color: #34d399; font-weight: 600;")

        health_layout.addWidget(self.mic_check)
        health_layout.addWidget(self.stt_check)
        health_layout.addWidget(self.tts_check)
        health_layout.addWidget(self.wake_check)
        layout.addWidget(health_group)

        # Quick Test Bar
        test_group = QGroupBox("Quick Test Command")
        test_layout = QHBoxLayout(test_group)
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("Type a command (e.g. 'What is the date today?' or 'Restart Spotify')...")
        self.cmd_input.returnPressed.connect(self._execute_manual_command)

        send_btn = QPushButton("Execute Command")
        send_btn.clicked.connect(self._execute_manual_command)

        listen_now_btn = QPushButton("Listen Voice Now")
        listen_now_btn.setObjectName("secondaryBtn")
        listen_now_btn.clicked.connect(self._listen_voice_now)

        test_layout.addWidget(self.cmd_input)
        test_layout.addWidget(send_btn)
        test_layout.addWidget(listen_now_btn)
        layout.addWidget(test_group)

        layout.addStretch()
        self.tabs.addTab(tab, "Dashboard")

    def _build_general_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        general_group = QGroupBox("Startup & Behavior")
        form_layout = QFormLayout(general_group)

        self.startup_check = QCheckBox("Start Alex automatically with Windows")
        self.startup_check.setChecked(is_startup_enabled())
        self.startup_check.toggled.connect(self._on_startup_toggled)

        self.greeting_check = QCheckBox("Speak greeting when Alex starts")
        self.greeting_check.setChecked(self.settings.speak_startup_greeting)

        self.minimize_check = QCheckBox("Minimize Alex to System Tray on window close")
        self.minimize_check.setChecked(self.settings.minimize_to_tray)

        form_layout.addRow(self.startup_check)
        form_layout.addRow(self.greeting_check)
        form_layout.addRow(self.minimize_check)
        layout.addWidget(general_group)

        # Voice settings
        voice_group = QGroupBox("Text-to-Speech Settings")
        voice_layout = QFormLayout(voice_group)

        self.engine_combo = QComboBox()
        self.engine_combo.addItem("Kokoro (Natural Offline Neural Voice)", "kokoro")
        self.engine_combo.addItem("Windows SAPI (Desktop Voices)", "sapi")
        if self.settings.tts_engine == "sapi":
            self.engine_combo.setCurrentIndex(1)
        else:
            self.engine_combo.setCurrentIndex(0)

        self.voice_combo = QComboBox()
        self._populate_tts_voices()

        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(120, 260)
        self.speed_slider.setValue(self.settings.voice_speed)
        self.speed_label = QLabel(f"{self.settings.voice_speed} WPM")
        self.speed_slider.valueChanged.connect(lambda v: self.speed_label.setText(f"{v} WPM"))

        speed_box = QHBoxLayout()
        speed_box.addWidget(self.speed_slider)
        speed_box.addWidget(self.speed_label)

        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(int(self.settings.voice_volume * 100))
        self.vol_label = QLabel(f"{int(self.settings.voice_volume * 100)}%")
        self.vol_slider.valueChanged.connect(lambda v: self.vol_label.setText(f"{v}%"))

        vol_box = QHBoxLayout()
        vol_box.addWidget(self.vol_slider)
        vol_box.addWidget(self.vol_label)

        test_tts_btn = QPushButton("Test Voice Output")
        test_tts_btn.clicked.connect(self._test_voice)

        voice_layout.addRow("TTS Engine:", self.engine_combo)
        voice_layout.addRow("Active Voice:", self.voice_combo)
        voice_layout.addRow("Voice Speed:", speed_box)
        voice_layout.addRow("Voice Volume:", vol_box)
        voice_layout.addRow("", test_tts_btn)
        layout.addWidget(voice_group)

        save_btn = QPushButton("Save General Settings")
        save_btn.clicked.connect(self._save_general_settings)
        layout.addWidget(save_btn)

        layout.addStretch()
        self.tabs.addTab(tab, "General")

    def _build_audio_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        mic_group = QGroupBox("Microphone Configuration")
        form = QFormLayout(mic_group)

        self.device_combo = QComboBox()
        self._populate_audio_devices()

        test_mic_btn = QPushButton("Test Microphone Input")
        test_mic_btn.clicked.connect(self._test_microphone_input)

        self.mic_status_label = QLabel("Click 'Test Microphone Input' to measure input levels.")
        self.mic_status_label.setStyleSheet("color: #9ba0b4;")

        form.addRow("Input Device:", self.device_combo)
        form.addRow("", test_mic_btn)
        form.addRow("Test Result:", self.mic_status_label)
        layout.addWidget(mic_group)

        layout.addStretch()
        self.tabs.addTab(tab, "Microphone")

    def _build_wake_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        wake_group = QGroupBox("Wake-Word Settings")
        form = QFormLayout(wake_group)

        self.wake_toggle = QCheckBox("Enable Wake Word Detection")
        self.wake_toggle.setChecked(self.settings.wake_word_enabled)

        self.wake_phrase_edit = QLineEdit(self.settings.wake_phrase)
        self.ack_edit = QLineEdit(self.settings.acknowledgement_phrase)

        form.addRow(self.wake_toggle)
        form.addRow("Wake Phrase:", self.wake_phrase_edit)
        form.addRow("Acknowledgement Phrase:", self.ack_edit)
        layout.addWidget(wake_group)

        save_wake_btn = QPushButton("Save Wake Word Settings")
        save_wake_btn.clicked.connect(self._save_wake_settings)
        layout.addWidget(save_wake_btn)

        layout.addStretch()
        self.tabs.addTab(tab, "Wake Word")

    def _build_apps_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        bar = QHBoxLayout()
        add_btn = QPushButton("+ Add Application")
        add_btn.clicked.connect(self._on_add_app)

        auto_btn = QPushButton("Auto-Detect Applications")
        auto_btn.setObjectName("secondaryBtn")
        auto_btn.clicked.connect(self._on_autodetect_apps)

        bar.addWidget(add_btn)
        bar.addWidget(auto_btn)
        bar.addStretch()
        layout.addLayout(bar)

        self.app_table = QTableWidget()
        self.app_table.setColumnCount(4)
        self.app_table.setHorizontalHeaderLabels(["Name", "Process", "Launch Path", "Aliases"])
        self.app_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.app_table)

        self._refresh_apps_table()
        self.tabs.addTab(tab, "Applications")

    def _build_logs_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        bar = QHBoxLayout()
        open_log_btn = QPushButton("Open alex.log in Notepad")
        open_log_btn.clicked.connect(self._open_log_file)
        clear_btn = QPushButton("Clear View")
        clear_btn.setObjectName("secondaryBtn")
        clear_btn.clicked.connect(lambda: self.log_text.clear())

        bar.addWidget(open_log_btn)
        bar.addWidget(clear_btn)
        bar.addStretch()
        layout.addLayout(bar)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        self._refresh_logs()
        self.tabs.addTab(tab, "Logs")

    def _populate_tts_voices(self) -> None:
        self.voice_combo.clear()
        try:
            voices = self.assistant.tts.get_voices()
            for v in voices:
                self.voice_combo.addItem(v["name"], v["id"])
            # Set currently active voice
            for i in range(self.voice_combo.count()):
                if self.voice_combo.itemData(i) == self.settings.kokoro_voice:
                    self.voice_combo.setCurrentIndex(i)
                    break
        except Exception as e:
            logger.error("Failed to populate TTS voices: %s", e)

    def _populate_audio_devices(self) -> None:
        self.device_combo.clear()
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            for idx, dev in enumerate(devices):
                if dev.get("max_input_channels", 0) > 0:
                    self.device_combo.addItem(f"{idx}: {dev.get('name')}", idx)
        except Exception as e:
            logger.error("Failed to query sound devices: %s", e)

    def _load_settings_into_ui(self) -> None:
        pass

    def _on_startup_toggled(self, checked: bool) -> None:
        toggle_startup(checked)
        self.settings.start_with_windows = checked
        SETTINGS_STORE.save(self.settings)

    def _save_general_settings(self) -> None:
        self.settings.speak_startup_greeting = self.greeting_check.isChecked()
        self.settings.minimize_to_tray = self.minimize_check.isChecked()
        self.settings.voice_speed = self.speed_slider.value()
        self.settings.voice_volume = self.vol_slider.value() / 100.0
        self.settings.tts_engine = self.engine_combo.currentData()
        if self.voice_combo.currentData():
            self.settings.kokoro_voice = self.voice_combo.currentData()
            self.assistant.tts.set_voice(self.settings.kokoro_voice)

        self.assistant.tts.set_rate(self.settings.voice_speed)
        self.assistant.tts.set_volume(self.settings.voice_volume)

        SETTINGS_STORE.save(self.settings)
        QMessageBox.information(self, "Settings", "General settings saved successfully.")

    def _save_wake_settings(self) -> None:
        self.settings.wake_word_enabled = self.wake_toggle.isChecked()
        self.settings.wake_phrase = self.wake_phrase_edit.text().strip()
        self.settings.acknowledgement_phrase = self.ack_edit.text().strip()
        SETTINGS_STORE.save(self.settings)
        QMessageBox.information(self, "Settings", "Wake Word settings saved successfully.")

    def _test_voice(self) -> None:
        rate = self.speed_slider.value()
        vol = self.vol_slider.value() / 100.0
        self.assistant.tts.set_rate(rate)
        self.assistant.tts.set_volume(vol)
        self.assistant.tts.speak("Hello! I am Alex, your local Windows assistant.", block=False)

    def _test_microphone_input(self) -> None:
        rep = self.assistant.audio.test_microphone(test_duration=0.8)
        if rep.get("working"):
            self.mic_status_label.setText(
                f"✓ Microphone Working: {rep.get('device_name')} (RMS: {rep.get('rms_energy', 0):.4f})"
            )
            self.mic_status_label.setStyleSheet("color: #34d399;")
        else:
            self.mic_status_label.setText(f"✗ Test failed: {rep.get('error')}")
            self.mic_status_label.setStyleSheet("color: #f87171;")

    def _on_add_app(self) -> None:
        dialog = AddAppDialog(self)
        if dialog.exec() == QDialog.Accepted:
            app_info = dialog.get_app_info()
            if app_info:
                GLOBAL_APP_MANAGER.register_app(app_info)
                self._refresh_apps_table()
                QMessageBox.information(self, "Application Added", f"Added {app_info.display_name} successfully.")

    def _on_autodetect_apps(self) -> None:
        GLOBAL_APP_MANAGER._auto_detect_apps()
        self._refresh_apps_table()
        QMessageBox.information(
            self,
            "Auto-Detect",
            f"Auto-detection completed. Found {len(GLOBAL_APP_MANAGER.get_all_apps())} applications.",
        )

    def _refresh_apps_table(self) -> None:
        apps = GLOBAL_APP_MANAGER.get_all_apps()
        self.app_table.setRowCount(len(apps))
        for row, app in enumerate(apps):
            self.app_table.setItem(row, 0, QTableWidgetItem(app.display_name))
            self.app_table.setItem(row, 1, QTableWidgetItem(", ".join(app.process_names)))
            self.app_table.setItem(row, 2, QTableWidgetItem(app.launch_command))
            self.app_table.setItem(row, 3, QTableWidgetItem(", ".join(app.aliases)))

    def _refresh_logs(self) -> None:
        if not os.path.exists(LOG_FILE):
            return
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            # Show last 100 lines
            text = "".join(lines[-100:])
            if text != self.log_text.toPlainText():
                self.log_text.setPlainText(text)
                self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
        except Exception:
            pass

    def _open_log_file(self) -> None:
        if os.path.exists(LOG_FILE):
            os.startfile(str(LOG_FILE))

    def _execute_manual_command(self) -> None:
        cmd = self.cmd_input.text().strip()
        if not cmd:
            return
        self.cmd_input.clear()
        self.last_cmd_label.setText(cmd)
        resp = self.assistant.process_text_command(cmd)
        self.last_resp_label.setText(resp)

    def _listen_voice_now(self) -> None:
        self.status_badge.setText("● LISTENING")
        self.status_badge.setStyleSheet(
            "background-color: #064e3b; color: #34d399; font-weight: bold; padding: 6px 14px; border-radius: 12px;"
        )
        resp = self.assistant.listen_and_respond(timeout=6.0)
        self.last_cmd_label.setText(self.assistant.last_command or "None")
        self.last_resp_label.setText(resp or "None")

    @Slot(AssistantState, AssistantState)
    def _on_state_change(self, old_state: AssistantState, new_state: AssistantState) -> None:
        color_map = {
            AssistantState.IDLE: ("#064e3b", "#34d399", "● IDLE (LISTENING WAKE)"),
            AssistantState.WAKE_DETECTED: ("#1e3a8a", "#60a5fa", "● WAKE DETECTED"),
            AssistantState.LISTENING: ("#1e3a8a", "#93c5fd", "● LISTENING COMMAND"),
            AssistantState.PROCESSING: ("#78350f", "#fbbf24", "● PROCESSING"),
            AssistantState.EXECUTING: ("#78350f", "#f59e0b", "● EXECUTING"),
            AssistantState.SPEAKING: ("#581c87", "#c084fc", "● SPEAKING"),
            AssistantState.ERROR: ("#7f1d1d", "#f87171", "● ERROR"),
        }
        bg, fg, label = color_map.get(new_state, ("#242633", "#ffffff", new_state.name))
        self.status_badge.setText(label)
        self.status_badge.setStyleSheet(
            f"background-color: {bg}; color: {fg}; font-weight: bold; padding: 6px 14px; border-radius: 12px;"
        )
        if self.tray:
            self.tray.update_status(new_state.name)

        if self.assistant.last_command:
            self.last_cmd_label.setText(self.assistant.last_command)
        if self.assistant.last_response:
            self.last_resp_label.setText(self.assistant.last_response)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Minimizes window to tray when closed if minimize_to_tray is enabled."""
        if self.settings.minimize_to_tray and self.tray is not None:
            event.ignore()
            self.hide()
            self.tray.showMessage(
                "Alex",
                "Alex is continuing to listen in the background.\nOpen from the system tray.",
                QSystemTrayIcon.Information,
                2500,
            )
        else:
            event.accept()
