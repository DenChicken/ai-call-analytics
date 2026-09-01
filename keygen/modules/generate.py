import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from keygen.modules.constants import (
    LICENSE_DATE_FORMAT,
    LICENSE_ENCODING,
    LICENSE_STEM,
    PRIVATE_KEY_STEM,
)
from keygen.modules.license import format_expires, payload_text, render
from keygen.modules.naming import write_new

EXPIRES_EXAMPLE = "2027-01-01T00:00Z"


class GenerateError(Exception):
    pass


@dataclass(frozen=True)
class KeyResult:
    private_key_path: Path
    public_key: str


def _encode(raw: bytes) -> str:
    return base64.b64encode(raw).decode(LICENSE_ENCODING)


def generate_key(out_dir: Path, moment: datetime) -> KeyResult:
    private_key = Ed25519PrivateKey.generate()
    private_key_path = write_new(
        out_dir, PRIVATE_KEY_STEM, _encode(private_key.private_bytes_raw()), moment
    )
    public_key = _encode(private_key.public_key().public_bytes_raw())
    return KeyResult(private_key_path=private_key_path, public_key=public_key)


def _read_private_key(path: Path) -> Ed25519PrivateKey:
    if not path.is_file():
        raise GenerateError(f"private key not found: {path}")
    encoded = path.read_text(encoding=LICENSE_ENCODING).strip()
    try:
        raw = base64.b64decode(encoded, validate=True)
    except binascii.Error as error:
        raise GenerateError("private key is not valid base64") from error
    return Ed25519PrivateKey.from_private_bytes(raw)


def _parse_expires(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, LICENSE_DATE_FORMAT)
    except ValueError as error:
        raise GenerateError(
            f"invalid expiry '{value}', expected UTC like {EXPIRES_EXAMPLE}"
        ) from error
    return parsed.replace(tzinfo=timezone.utc)


def generate_license(
    private_key_path: Path, expires: str, contact: str, out_dir: Path, moment: datetime
) -> Path:
    private_key = _read_private_key(private_key_path)
    expires_at = _parse_expires(expires)
    payload = payload_text(format_expires(expires_at), contact)
    signature = private_key.sign(payload.encode(LICENSE_ENCODING))
    return write_new(out_dir, LICENSE_STEM, render(payload, signature), moment)
