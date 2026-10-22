"""Audio management and microphone recording module."""

import collections
import time
from typing import Any, List, Optional
import numpy as np
import sounddevice as sd

from config import AudioConfig, CONFIG
from storage.logger import logger


class AudioManager:
    """Manages audio devices and microphone recording with Voice Activity Detection (VAD)."""

    def __init__(self, config: AudioConfig | None = None):
        self.config = config or CONFIG.audio
        self._sample_rate = self.config.sample_rate
        self._channels = self.config.channels
        self._input_device = self.config.input_device

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def input_device(self) -> int | None:
        return self._input_device

    def list_devices(self) -> List[dict]:
        """Returns all audio input and output devices."""
        return sd.query_devices()

    def get_default_input_device(self) -> dict:
        """Returns info on the system default input device."""
        default_in_idx = sd.default.device[0]
        if default_in_idx < 0:
            raise RuntimeError("No default audio input device available.")
        return sd.query_devices(default_in_idx)

    def get_default_output_device(self) -> dict:
        """Returns info on the system default output device."""
        default_out_idx = sd.default.device[1]
        if default_out_idx < 0:
            raise RuntimeError("No default audio output device available.")
        return sd.query_devices(default_out_idx)

    def test_microphone(self, test_duration: float = 1.0) -> dict:
        """Tests microphone input and returns audio statistics."""
        try:
            device_info = self.get_default_input_device()
            logger.info("Testing microphone on device: %s", device_info.get("name"))
            samples = int(test_duration * self._sample_rate)
            data = sd.rec(
                samples,
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="float32",
                device=self._input_device,
            )
            sd.wait()
            rms = float(np.sqrt(np.mean(data**2)))
            max_amp = float(np.max(np.abs(data)))
            return {
                "status": "ok",
                "device_name": device_info.get("name"),
                "sample_rate": self._sample_rate,
                "rms_energy": rms,
                "peak_amplitude": max_amp,
                "working": True,
            }
        except Exception as e:
            logger.error("Microphone test failed: %s", e)
            return {
                "status": "error",
                "error": str(e),
                "working": False,
            }

    def calibrate_noise(self, duration: float = 1.0) -> float:
        """Samples ambient noise to establish baseline energy threshold."""
        try:
            samples = int(duration * self._sample_rate)
            data = sd.rec(
                samples,
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="float32",
                device=self._input_device,
            )
            sd.wait()
            ambient_rms = float(np.sqrt(np.mean(data**2)))
            # Set dynamic threshold at 2.5x ambient noise or config minimum
            threshold = max(self.config.silence_threshold, ambient_rms * 2.5)
            logger.info(
                "Calibrated ambient noise RMS: %.5f -> silence threshold: %.5f",
                ambient_rms,
                threshold,
            )
            return threshold
        except Exception as e:
            logger.warning("Could not calibrate noise, using default: %s", e)
            return self.config.silence_threshold

    def record_fixed(self, duration: float) -> np.ndarray:
        """Records a fixed duration of audio."""
        samples = int(duration * self._sample_rate)
        data = sd.rec(
            samples,
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype="float32",
            device=self._input_device,
        )
        sd.wait()
        return data.flatten()

    def record_command(
        self,
        listen_timeout: float = 5.0,
        silence_duration: float | None = None,
        max_duration: float | None = None,
        threshold: float | None = None,
    ) -> Optional[np.ndarray]:
        """
        Listens on the microphone for speech with VAD.
        
        - Waits up to listen_timeout seconds for speech to begin.
        - Once speech starts, records until silence persists for silence_duration
          or max_duration is reached.
        - Returns float32 1D numpy array, or None if no speech was detected.
        """
        silence_dur = silence_duration or self.config.silence_duration
        max_dur = max_duration or self.config.max_record_duration
        energy_thresh = threshold or self.config.silence_threshold

        chunk_size = self.config.chunk_size
        chunk_duration = chunk_size / self._sample_rate

        # Pre-roll buffer to retain 0.3s of audio before speech onset
        pre_roll_chunks = int(0.3 / chunk_duration)
        pre_roll_buffer = collections.deque(maxlen=pre_roll_chunks)

        recorded_chunks: list[np.ndarray] = []
        speech_started = False
        consecutive_silence_time = 0.0
        start_time = time.time()
        speech_start_time = 0.0

        with sd.InputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype="float32",
            blocksize=chunk_size,
            device=self._input_device,
        ) as stream:
            while True:
                chunk, overflow = stream.read(chunk_size)
                flat_chunk = chunk.flatten()
                rms = float(np.sqrt(np.mean(flat_chunk**2)))
                now = time.time()

                if not speech_started:
                    pre_roll_buffer.append(flat_chunk)
                    if rms > energy_thresh:
                        speech_started = True
                        speech_start_time = now
                        # Append buffered pre-roll
                        recorded_chunks.extend(list(pre_roll_buffer))
                        logger.debug("Speech onset detected (RMS: %.4f)", rms)
                    elif now - start_time > listen_timeout:
                        # Timed out waiting for speech
                        logger.info("Command listening timed out (no speech detected).")
                        return None
                else:
                    # Speech in progress
                    recorded_chunks.append(flat_chunk)
                    total_speech_time = now - speech_start_time

                    if rms < energy_thresh:
                        consecutive_silence_time += chunk_duration
                    else:
                        consecutive_silence_time = 0.0

                    if consecutive_silence_time >= silence_dur:
                        logger.debug("Speech ended after %.2fs silence.", consecutive_silence_time)
                        break

                    if total_speech_time >= max_dur:
                        logger.debug("Reached max recording duration (%.2fs).", max_dur)
                        break

        if not recorded_chunks:
            return None

        audio_data = np.concatenate(recorded_chunks)
        duration = len(audio_data) / self._sample_rate
        if duration < self.config.min_record_duration:
            logger.info("Recorded audio was too brief (%.2fs), ignored.", duration)
            return None

        return audio_data
