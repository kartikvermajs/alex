"""Unit tests for offline Kokoro Neural TTS engine."""

import os
from pathlib import Path
import numpy as np
import pytest

from config import CONFIG, TTSConfig
from voice.text_to_speech import KokoroTTS, create_tts_engine


def test_kokoro_model_files_exist():
    model_path = Path(CONFIG.tts.kokoro_model_path)
    voices_path = Path(CONFIG.tts.kokoro_voices_path)
    assert model_path.exists(), f"Kokoro ONNX model missing at {model_path}"
    assert voices_path.exists(), f"Kokoro voice weights missing at {voices_path}"
    assert model_path.stat().st_size > 50 * 1024 * 1024, "Model file size too small"
    assert voices_path.stat().st_size > 5 * 1024 * 1024, "Voices file size too small"


def test_kokoro_tts_initialization():
    tts = create_tts_engine()
    assert isinstance(tts, KokoroTTS)

    voices = tts.get_voices()
    assert len(voices) >= 6
    voice_ids = [v["id"] for v in voices]
    assert "af_bella" in voice_ids
    assert "af_sarah" in voice_ids
    assert "am_michael" in voice_ids

    tts.shutdown()


def test_kokoro_synthesis_audio_waveform():
    import kokoro_onnx

    model_path = CONFIG.tts.kokoro_model_path
    voices_path = CONFIG.tts.kokoro_voices_path

    kokoro = kokoro_onnx.Kokoro(str(model_path), str(voices_path))
    samples, sr = kokoro.create(
        text="Alex local neural voice online.",
        voice="af_bella",
        speed=1.0,
        lang="en-us",
    )

    assert isinstance(samples, np.ndarray)
    assert sr == 24000
    assert len(samples) > 0
    # Check that amplitude is not entirely zero
    assert np.max(np.abs(samples)) > 0.01


def test_kokoro_fallback_on_missing_model():
    bad_config = TTSConfig(
        engine="kokoro",
        kokoro_model_path="nonexistent_model.onnx",
        kokoro_voices_path="nonexistent_voices.bin",
    )
    fallback_engine = create_tts_engine(bad_config)
    # Should safely fall back to Windows SAPI without crashing
    assert fallback_engine is not None
    assert type(fallback_engine).__name__ == "WindowsSAPITTS"
    fallback_engine.shutdown()
