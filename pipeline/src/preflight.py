import logging
import shutil

FFMPEG_EXECUTABLE = "ffmpeg"
FFMPEG_HINT = (
    "pyannote decodes audio through torchcodec, which needs a system FFmpeg "
    "(versions 4 to 9, shared build with DLLs on Windows). "
    "Install it and make sure it is on PATH, then start the pipeline again."
)

logger = logging.getLogger(__name__)


class PreflightError(Exception):
    pass


def check_audio_decoder() -> None:
    from torchcodec._core._decoder_utils import load_core_libraries

    try:
        load_core_libraries()
    except Exception as error:
        found = shutil.which(FFMPEG_EXECUTABLE)
        location = f"ffmpeg found at {found}" if found else "ffmpeg not found on PATH"
        raise PreflightError(f"{FFMPEG_HINT} ({location})") from error

    logger.info("audio decoder ready")
