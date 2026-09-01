from datetime import datetime, timezone
from pathlib import Path

from issuing.constants import FILE_NAME_TEMPLATE, FILE_SUFFIX, FILE_TIMESTAMP_FORMAT
from licensing.constants import LICENSE_ENCODING


class OutputError(Exception):
    pass


def timestamped_name(stem: str, moment: datetime) -> str:
    timestamp = moment.astimezone(timezone.utc).strftime(FILE_TIMESTAMP_FORMAT)
    return FILE_NAME_TEMPLATE.format(stem=stem, timestamp=timestamp, suffix=FILE_SUFFIX)


def write_new(directory: Path, stem: str, content: str, moment: datetime) -> Path:
    if not directory.is_dir():
        raise OutputError(f"output directory not found: {directory}")
    path = directory / timestamped_name(stem, moment)
    if path.exists():
        raise OutputError(f"refusing to overwrite existing file: {path}")
    path.write_text(content, encoding=LICENSE_ENCODING)
    return path
