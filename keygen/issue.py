import argparse
import base64
import binascii
import sys
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from keygen.constants import LICENSE_DATE_FORMAT, LICENSE_ENCODING
from keygen.license import License, format_expires, payload_text, render

EXPIRES_EXAMPLE = "2027-01-01T00:00Z"


class IssueError(Exception):
    pass


def _read_private_key(path: Path) -> Ed25519PrivateKey:
    if not path.is_file():
        raise IssueError(f"private key not found: {path}")
    encoded = path.read_text(encoding=LICENSE_ENCODING).strip()
    try:
        raw = base64.b64decode(encoded, validate=True)
    except binascii.Error as error:
        raise IssueError("private key is not valid base64") from error
    return Ed25519PrivateKey.from_private_bytes(raw)


def _parse_expires(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, LICENSE_DATE_FORMAT)
    except ValueError as error:
        raise IssueError(
            f"invalid expiry '{value}', expected UTC like {EXPIRES_EXAMPLE}"
        ) from error
    return parsed.replace(tzinfo=timezone.utc)


def issue(private_key: Ed25519PrivateKey, expires: datetime, contact: str) -> str:
    license = License(expires=expires, contact=contact)
    payload = payload_text(format_expires(expires), contact)
    signature = private_key.sign(payload.encode(LICENSE_ENCODING))
    return render(license, signature)


def main() -> int:
    parser = argparse.ArgumentParser(description="Issue a signed license file")
    parser.add_argument("--private-key", type=Path, required=True, help="path to the private key")
    parser.add_argument(
        "--expires", required=True, help=f"expiry in UTC, like {EXPIRES_EXAMPLE}"
    )
    parser.add_argument("--contact", required=True, help="supplier contact shown to the customer")
    parser.add_argument("--out", type=Path, required=True, help="path to write the license file")
    args = parser.parse_args()

    try:
        private_key = _read_private_key(args.private_key)
        expires = _parse_expires(args.expires)
    except IssueError as error:
        print(error, file=sys.stderr)
        return 1

    args.out.write_text(issue(private_key, expires, args.contact), encoding=LICENSE_ENCODING)
    print(f"license valid until {args.expires} written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
