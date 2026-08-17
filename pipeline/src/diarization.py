import logging
import threading
from pathlib import Path

import torch
from pyannote.audio import Pipeline

from src.config import DiarizationConfig
from src.transcript import Turn

CONFIG_FILE_NAME = "config.yaml"

logger = logging.getLogger(__name__)


class Diarization:
    def __init__(self, config: DiarizationConfig):
        pipeline_config = config.local_dir / CONFIG_FILE_NAME
        if not pipeline_config.is_file():
            raise FileNotFoundError(
                f"diarization config not found: {pipeline_config}, run scripts/fetch_models.py"
            )
        logger.info("loading diarization pipeline from %s on %s", config.local_dir, config.device)
        self._pipeline = Pipeline.from_pretrained(str(pipeline_config))
        self._pipeline.to(torch.device(config.device))
        self._config = config
        self._lock = threading.Lock()

    def diarize(self, audio_path: Path) -> list[Turn]:
        with self._lock:
            annotation = self._pipeline(
                str(audio_path), max_speakers=self._config.max_speakers
            )
        turns = [
            Turn(start=segment.start, end=segment.end, speaker=speaker)
            for segment, _, speaker in annotation.itertracks(yield_label=True)
        ]
        logger.info("diarized %s into %s turns", audio_path.name, len(turns))
        return turns
