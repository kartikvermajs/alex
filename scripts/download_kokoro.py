"""Download Kokoro ONNX model and voice weights for offline operation."""

import os
from pathlib import Path
import urllib.request
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
KOKORO_DIR = BASE_DIR / "models" / "kokoro"
KOKORO_DIR.mkdir(parents=True, exist_ok=True)

MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

MODEL_PATH = KOKORO_DIR / "kokoro-v1.0.onnx"
VOICES_PATH = KOKORO_DIR / "voices-v1.0.bin"


def download_file(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 1000:
        print(f"[EXISTS] {dest.name} ({dest.stat().st_size / (1024*1024):.1f} MB)")
        return

    print(f"[DOWNLOADING] {dest.name} from {url}...")
    temp_dest = dest.with_suffix(".tmp")
    
    def reporthook(count, block_size, total_size):
        if total_size > 0:
            percent = min(100.0, count * block_size * 100.0 / total_size)
            mb = (count * block_size) / (1024 * 1024)
            total_mb = total_size / (1024 * 1024)
            sys.stdout.write(f"\r  {dest.name}: {percent:.1f}% ({mb:.1f} / {total_mb:.1f} MB)")
            sys.stdout.flush()

    urllib.request.urlretrieve(url, temp_dest, reporthook=reporthook)
    temp_dest.replace(dest)
    print(f"\n[DONE] Saved to {dest}")


def main():
    print("=== Downloading Kokoro Offline Model Files ===")
    download_file(VOICES_URL, VOICES_PATH)
    download_file(MODEL_URL, MODEL_PATH)
    print("\nKokoro offline TTS model and voices are ready!")


if __name__ == "__main__":
    main()
