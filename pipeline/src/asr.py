import gc
import logging
import threading
import time
from pathlib import Path

from faster_whisper import WhisperModel

from src.config import AsrConfig
from src.constants import MILLISECONDS_PER_SECOND, SUSPICIOUS_COMPRESSION_RATIO
from src.transcript import Segment, Word

logger = logging.getLogger(__name__)


def _to_ms(seconds: float) -> int:
    return int(seconds * MILLISECONDS_PER_SECOND)


class Asr:
    def __init__(self, config: AsrConfig):
        if not config.local_dir.is_dir():
            raise FileNotFoundError(
                f"asr model directory not found: {config.local_dir}, run scripts/fetch_models.py"
            )
        self._config = config
        self._model = None
        self._lock = threading.Lock()

    @property
    def model_name(self) -> str:
        return self._config.repo_id

    def _ensure_loaded(self) -> WhisperModel:
        if self._model is None:
            logger.info(
                "loading asr model from %s on %s", self._config.local_dir, self._config.device
            )
            self._model = WhisperModel(
                str(self._config.local_dir),
                device=self._config.device,
                compute_type=self._config.compute_type,
            )
        return self._model

    def unload(self) -> None:
        with self._lock:
            if self._model is None:
                return
            logger.info("unloading asr model %s", self._config.repo_id)
            self._model = None
            gc.collect()

    def transcribe(self, audio_path: Path) -> tuple[list[Segment], float]:
        logger.info("transcribing %s", audio_path.name)
        transcript = self._config.transcript
        logger.debug(
            "asr parameters: language=%s beam_size=%s condition_on_previous_text=%s "
            "hallucination_silence_threshold=%s word_timestamps=%s vad_filter=%s "
            "min_silence_duration_ms=%s speech_pad_ms=%s",
            transcript.language,
            transcript.beam_size,
            transcript.condition_on_previous_text,
            transcript.hallucination_silence_threshold,
            transcript.word_timestamps,
            transcript.vad_filter,
            transcript.min_silence_duration_ms,
            transcript.speech_pad_ms,
        )
        started = time.monotonic()
        with self._lock:
            model = self._ensure_loaded()
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
            segments = [
                Segment(
                    start_ms=_to_ms(segment.start),
                    end_ms=_to_ms(segment.end),
                    text=text,
                    words=[
                        Word(
                            start_ms=_to_ms(word.start),
                            end_ms=_to_ms(word.end),
                            text=word.word,
                            probability=word.probability,
                        )
                        for word in segment.words or []
                    ],
                    no_speech_prob=segment.no_speech_prob,
                    avg_logprob=segment.avg_logprob,
                    compression_ratio=segment.compression_ratio,
                )
                for segment in raw_segments
                if (text := segment.text.strip())
            ]
        elapsed = time.monotonic() - started
        logger.info(
            "transcribed %s into %s segments: audio %.0fs, took %.0fs (%.1fx realtime)",
            audio_path.name,
            len(segments),
            info.duration,
            elapsed,
            info.duration / elapsed if elapsed else 0,
        )
        suspicious = [s for s in segments if s.compression_ratio > SUSPICIOUS_COMPRESSION_RATIO]
        if suspicious:
            logger.warning(
                "%s of %s segments look like hallucinations (compression_ratio > %s)",
                len(suspicious),
                len(segments),
                SUSPICIOUS_COMPRESSION_RATIO,
            )
        if self._config.unload_after:
            self.unload()
        return segments, info.duration
