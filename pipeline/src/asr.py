import gc
import logging
import threading
from pathlib import Path

from faster_whisper import WhisperModel

from src.config import AsrConfig
from src.constants import MILLISECONDS_PER_SECOND
from src.transcript import Segment, Word

WORD_TIMESTAMPS = True
VAD_FILTER = True

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
        with self._lock:
            model = self._ensure_loaded()
            raw_segments, info = model.transcribe(
                str(audio_path),
                language=self._config.language,
                beam_size=self._config.beam_size,
                word_timestamps=WORD_TIMESTAMPS,
                vad_filter=VAD_FILTER,
                vad_parameters={"min_silence_duration_ms": self._config.min_silence_duration_ms},
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
        logger.info("transcribed %s into %s segments", audio_path.name, len(segments))
        if self._config.unload_after:
            self.unload()
        return segments, info.duration
