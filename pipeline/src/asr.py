import gc
import logging
import time
from pathlib import Path

import ctranslate2
from faster_whisper import WhisperModel

from src.config import Asr as AsrConfig
from src.constants import MILLISECONDS_PER_SECOND, SUSPICIOUS_COMPRESSION_RATIO
from src.errors import FatalError, is_device_failure
from src.transcript import Segment

logger = logging.getLogger(__name__)


class Asr:
    def __init__(self, config: AsrConfig, model_dir: Path):
        if not model_dir.is_dir():
            raise FatalError(f"asr model not found: {model_dir}, run scripts/fetch_models.py")
        _check_device(config)
        self._config = config
        self._model_dir = model_dir
        self._model = None

    def _load(self) -> WhisperModel:
        if self._model is None:
            logger.info("loading asr model from %s on %s", self._model_dir, self._config.device)
            try:
                self._model = WhisperModel(
                    str(self._model_dir),
                    device=self._config.device,
                    compute_type=self._config.compute_type,
                )
            except Exception as error:
                raise FatalError(f"asr model could not be loaded: {error}") from error
        return self._model

    def unload(self) -> None:
        if self._model is None:
            return
        logger.info("unloading asr model")
        if self._model.model.model_is_loaded:
            self._model.model.unload_model()
        self._model = None
        gc.collect()

    def transcribe(self, audio_path: Path) -> tuple[list[Segment], float]:
        logger.info("transcribing %s", audio_path.name)
        transcript = self._config.transcript
        logger.trace("asr parameters: %s", transcript)

        started = time.monotonic()
        model = self._load()
        try:
            raw_segments, info = model.transcribe(
                str(audio_path),
                language=transcript.language,
                beam_size=transcript.beam_size,
                condition_on_previous_text=transcript.condition_on_previous_text,
                hallucination_silence_threshold=transcript.hallucination_silence_threshold,
                word_timestamps=transcript.word_timestamps,
                vad_filter=transcript.vad_filter,
                vad_parameters={
                    "min_silence_duration_ms": transcript.min_silence_duration_ms,
                    "speech_pad_ms": transcript.speech_pad_ms,
                },
            )
            decoded = list(raw_segments)
        except Exception as error:
            if not is_device_failure(error):
                raise
            self.unload()
            raise FatalError(f"asr failed on {self._config.device}: {error}") from error

        segments = []
        suspicious = 0
        for segment in decoded:
            text = segment.text.strip()
            logger.trace(
                "segment %.1f-%.1fs: no_speech=%.2f logprob=%.2f compression=%.2f",
                segment.start,
                segment.end,
                segment.no_speech_prob,
                segment.avg_logprob,
                segment.compression_ratio,
            )
            if not text:
                continue
            if segment.compression_ratio > SUSPICIOUS_COMPRESSION_RATIO:
                suspicious += 1
            segments.append(
                Segment(
                    start_ms=_to_ms(segment.start),
                    end_ms=_to_ms(segment.end),
                    text=text,
                )
            )

        elapsed = time.monotonic() - started
        logger.info(
            "transcribed %s into %s segments: audio %.0fs, took %.0fs (%.1fx realtime)",
            audio_path.name,
            len(segments),
            info.duration,
            elapsed,
            info.duration / elapsed if elapsed else 0,
        )
        if suspicious:
            logger.warning(
                "%s of %s segments look like hallucinations", suspicious, len(segments)
            )
        if self._config.unload_after:
            self.unload()
        return segments, info.duration


def _check_device(config: AsrConfig) -> None:
    try:
        supported = ctranslate2.get_supported_compute_types(config.device)
    except (ValueError, RuntimeError) as error:
        raise FatalError(
            f"asr device {config.device} is not usable: {error}, "
            "fix 'device' in [asr] or make the device available"
        ) from error
    if config.compute_type not in supported:
        raise FatalError(
            f"asr compute_type {config.compute_type} is not supported on {config.device}, "
            f"set 'compute_type' in [asr] to one of: {', '.join(sorted(supported))}"
        )


def _to_ms(seconds: float) -> int:
    return int(seconds * MILLISECONDS_PER_SECOND)
