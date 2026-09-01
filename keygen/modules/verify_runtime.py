from datetime import datetime, timezone
from pathlib import Path

from keygen.modules.constants import LICENSE_ENCODING
from keygen.modules.license import License, LicenseError, verify

EXPIRED_MESSAGE = "license expired on {expires}, contact the supplier: {contact}"


def load(path: str | Path) -> License:
    path = Path(path)
    if not path.is_file():
        raise LicenseError(f"license file not found: {path}")
    return verify(path.read_text(encoding=LICENSE_ENCODING))


def is_expired(license: License, moment: datetime | None = None) -> bool:
    now = moment or datetime.now(timezone.utc)
    return now >= license.expires


def check(license: License, moment: datetime | None = None) -> None:
    if is_expired(license, moment):
        raise LicenseError(
            EXPIRED_MESSAGE.format(expires=license.expires, contact=license.contact)
        )
