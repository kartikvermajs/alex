"""Alex - Local Windows Voice Assistant.
Entry point application supporting CLI, Voice Wake Word, System Tray, and Settings Dashboard.
"""

import argparse
import sys
import time

from config import CONFIG
from core.assistant import Assistant
from storage.logger import logger


def run_gui_and_tray(assistant: Assistant, start_minimized: bool = False) -> int:
    """Runs the PySide6 application with System Tray and modern Settings Dashboard."""
    from PySide6.QtWidgets import QApplication
    from ui.main_window import AlexMainWindow
    from ui.tray import AlexSystemTray

    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    tray = AlexSystemTray(assistant)
    window = AlexMainWindow(assistant, tray=tray)
    tray.show_window_signal.connect(lambda: (window.showNormal(), window.activateWindow()))

    tray.show()

    # Start wake-word background listening
    assistant.start_wake_listening()

    if not start_minimized:
        window.show()

    return app.exec()


def main() -> int:
    parser = argparse.ArgumentParser(description="Alex - Local Windows Voice Assistant")
    parser.add_argument(
        "--test-pipeline",
        action="store_true",
        help="Run system component diagnostics and test voice pipeline",
    )
    parser.add_argument(
        "--text",
        type=str,
        help="Execute a text command directly through the command router and TTS",
    )
    parser.add_argument(
        "--listen",
        action="store_true",
        help="Listen for a single voice command on the microphone and respond verbally",
    )
    parser.add_argument(
        "--cli-wake",
        action="store_true",
        help="Run continuously in console without GUI",
    )
    parser.add_argument(
        "--tray",
        action="store_true",
        help="Start minimized directly to the Windows system tray",
    )

    args = parser.parse_args()

    logger.info("Starting Alex Voice Assistant...")
    assistant = Assistant()

    try:
        report = assistant.initialize()
        if not report["overall_healthy"]:
            logger.warning("Assistant initialized with degraded component status: %s", report)
        else:
            logger.info("All core components initialized successfully.")

        if args.test_pipeline:
            print("\n=== Alex Pipeline Diagnostics ===")
            print(f"Microphone: {'[OK]' if report['microphone'] else '[FAIL]'}")
            print(f"Speech Recognition: {'[OK]' if report['speech_recognition'] else '[FAIL]'}")
            print(f"TTS: {'[OK]' if report['tts'] else '[FAIL]'}")
            print(f"Wake Word: {'[OK]' if report['wake_word'] else '[FAIL]'}")

            print("\nTesting TTS output...")
            assistant.tts.speak("Alex voice pipeline and wake word detection operational.", block=True)

            print("\nTesting Date command...")
            date_resp = assistant.process_text_command("What is the date today?")
            print(f"Date Response: {date_resp}")

            print("\nTesting Time command...")
            time_resp = assistant.process_text_command("What time is it?")
            print(f"Time Response: {time_resp}")
            print("\n=== Diagnostics Complete ===")
            return 0

        elif args.text:
            logger.info("Executing text command: %s", args.text)
            response = assistant.process_text_command(args.text)
            print(f"\nResponse: {response}\n")
            return 0

        elif args.listen:
            print("\n" + "=" * 50)
            print("Alex is listening for your command...")
            print("Please speak now (e.g., 'What is the date today?')...")
            print("=" * 50 + "\n")

            response = assistant.listen_and_respond(timeout=6.0)
            print(f"\nAlex responded: {response}\n")
            return 0

        elif args.cli_wake:
            print("\n" + "=" * 60)
            print("  ALEX IS RUNNING (Console Wake Word Mode)")
            print(f"  Say '{CONFIG.wake_word.wake_phrase.title()}' to activate...")
            print("  Press Ctrl+C to stop.")
            print("=" * 60 + "\n")

            assistant.start_wake_listening()
            while True:
                time.sleep(0.5)

        else:
            # Default native Windows desktop experience: GUI + System Tray
            return run_gui_and_tray(assistant, start_minimized=args.tray)

    except KeyboardInterrupt:
        logger.info("Alex terminated by user.")
        return 0
    except Exception as e:
        logger.error("Unhandled exception in main: %s", e, exc_info=True)
        return 1
    finally:
        assistant.shutdown()


if __name__ == "__main__":
    sys.exit(main())
