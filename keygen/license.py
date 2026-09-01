import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from keygen.constants import (
    FIELD_CONTACT,
    FIELD_EXPIRES,
    FIELD_SIGNATURE,
    LICENSE_DATE_FORMAT,
    LICENSE_ENCODING,
    LICENSE_FIELD_SEPARATOR,
    LICENSE_FIELDS,
    LICENSE_LINE_SEPARATOR,
)


class LicenseError(Exception):
    pass


@dataclass(frozen=True)
class License:
    expires: datetime
    contact: str


def format_expires(expires: datetime) -> str:
    return expires.astimezone(timezone.utc).strftime(LICENSE_DATE_FORMAT)


def _parse_expires(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, LICENSE_DATE_FORMAT)
    except ValueError as error:
        raise LicenseError(f"invalid {FIELD_EXPIRES} date '{value}'") from error
    return parsed.replace(tzinfo=timezone.utc)


def _field_line(field: str, value: str) -> str:
    return f"{field}{LICENSE_FIELD_SEPARATOR}{value}"


def payload_text(expires: str, contact: str) -> str:
    return LICENSE_LINE_SEPARATOR.join(
        (_field_line(FIELD_EXPIRES, expires), _field_line(FIELD_CONTACT, contact))
    )


def render(license: License, signature: bytes) -> str:
    payload = payload_text(format_expires(license.expires), license.contact)
    encoded = base64.b64encode(signature).decode(LICENSE_ENCODING)
    return LICENSE_LINE_SEPARATOR.join(
        (payload, _field_line(FIELD_SIGNATURE, encoded), "")
    )


def _parse_fields(text: str) -> dict:
    fields = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition(LICENSE_FIELD_SEPARATOR)
        if not separator:
            raise LicenseError(f"malformed line without a separator: '{line}'")
        key = key.strip()
        if key in fields:
            raise LicenseError(f"duplicate field '{key}'")
        fields[key] = value.strip()
    return fields


def _decode_signature(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except binascii.Error as error:
        raise LicenseError("signature is not valid base64") from error


def verify(public_key_bytes: bytes, text: str) -> License:
    fields = _parse_fields(text)
    for field in (*LICENSE_FIELDS, FIELD_SIGNATURE):
        if field not in fields:
            raise LicenseError(f"missing required field '{field}'")

    signature = _decode_signature(fields[FIELD_SIGNATURE])
    payload = payload_text(fields[FIELD_EXPIRES], fields[FIELD_CONTACT])

    key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
    try:
        key.verify(signature, payload.encode(LICENSE_ENCODING))
    except InvalidSignature as error:
        raise LicenseError("signature does not match the license contents") from error

    return License(
        expires=_parse_expires(fields[FIELD_EXPIRES]),
        contact=fields[FIELD_CONTACT],
    )
