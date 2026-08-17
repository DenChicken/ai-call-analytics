import logging
import threading
from pathlib import Path

from faster_whisper import WhisperModel

from src.config import AsrConfig
from src.transcript import Word

logger = logging.getLogger(__name__)


class Asr:
    def __init__(self, config: AsrConfig):
        if not config.local_dir.is_dir():
            raise FileNotFoundError(
                f"asr model directory not found: {config.local_dir}, run scripts/fetch_models.py"
            )
        logger.info("loading asr model from %s on %s", config.local_dir, config.device)
        self._model = WhisperModel(
            str(config.local_dir),
            device=config.device,
            compute_type=config.compute_type,
        )
        self._config = config
        self._lock = threading.Lock()

    @property
    def model_name(self) -> str:
        return self._config.repo_id

    def transcribe(self, audio_path: Path) -> list[Word]:
        logger.info("transcribing %s", audio_path.name)
        with self._lock:
            segments, _ = self._model.transcribe(
                str(audio_path),
                language=self._config.language,
                beam_size=self._config.beam_size,
                vad_filter=self._config.vad_filter,
                word_timestamps=True,
            )
            words = [
                Word(start=word.start, end=word.end, text=word.word)
                for segment in segments
                for word in (segment.words or [])
            ]
        logger.info("transcribed %s into %s words", audio_path.name, len(words))
        return words
