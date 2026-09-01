import base64
import binascii
from datetime import datetime, timezone
from pathlib import Path

from keygen import license as license_file
from keygen.constants import LICENSE_ENCODING
from keygen.license import License, LicenseError
from keygen.public_key import PUBLIC_KEY

EXPIRED_MESSAGE = "license expired on {expires}, contact the supplier: {contact}"
BROKEN_KEY_MESSAGE = "compiled public key is invalid, the build is corrupted"


def _public_key_bytes() -> bytes:
    try:
        return base64.b64decode(PUBLIC_KEY, validate=True)
    except binascii.Error as error:
        raise LicenseError(BROKEN_KEY_MESSAGE) from error


def load(path: str | Path) -> License:
    path = Path(path)
    if not path.is_file():
        raise LicenseError(f"license file not found: {path}")
    return license_file.verify(_public_key_bytes(), path.read_text(encoding=LICENSE_ENCODING))


def is_expired(license: License, moment: datetime | None = None) -> bool:
    now = moment or datetime.now(timezone.utc)
    return now >= license.expires


def check(license: License, moment: datetime | None = None) -> None:
    if is_expired(license, moment):
        raise LicenseError(
            EXPIRED_MESSAGE.format(expires=license.expires, contact=license.contact)
        )
