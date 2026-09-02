import argparse
import base64
import binascii
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from licensing.constants import LICENSE_DATE_FORMAT, LICENSE_ENCODING
from licensing.license import format_expires, payload_text, render

COMMAND_KEY = "key"
COMMAND_LICENSE = "license"

FILE_TIMESTAMP_FORMAT = "%Y-%m-%dT%H-%M-%S-%fZ"
FILE_NAME_TEMPLATE = "{stem}_{timestamp}{suffix}"
FILE_SUFFIX = ".txt"
PRIVATE_KEY_STEM = "license_private_key"
LICENSE_STEM = "license"

RELATIVE_PREFIX = "+"
RELATIVE_PATTERN = r"^\+(\d+)([mhd])$"
RELATIVE_UNIT_SECONDS = {"m": 60, "h": 3600, "d": 86400}
RELATIVE_EXAMPLE = "+30d"
ABSOLUTE_EXAMPLE = "2027-01-01T00:00Z"

PUBLIC_KEY_FILE = "licensing/pubkey.py"
PUBLIC_KEY_NOTICE = (
    "keep the private key safe, it signs every license and is never delivered\n"
    f"put the public key below into PUBLIC_KEY in {PUBLIC_KEY_FILE}, then rebuild:\n"
    "licenses signed by the old key stop verifying once it changes"
)


class KeygenError(Exception):
    pass


@dataclass(frozen=True)
class KeyResult:
    private_key_path: Path
    public_key: str


@dataclass(frozen=True)
class LicenseResult:
    license_path: Path
    expires: str


def _encode(raw: bytes) -> str:
    return base64.b64encode(raw).decode(LICENSE_ENCODING)


def _timestamped_name(stem: str, moment: datetime) -> str:
    timestamp = moment.astimezone(timezone.utc).strftime(FILE_TIMESTAMP_FORMAT)
    return FILE_NAME_TEMPLATE.format(stem=stem, timestamp=timestamp, suffix=FILE_SUFFIX)


def _write_new(directory: Path, stem: str, content: str, moment: datetime) -> Path:
    if not directory.is_dir():
        raise KeygenError(f"output directory not found: {directory}")
    path = directory / _timestamped_name(stem, moment)
    if path.exists():
        raise KeygenError(f"refusing to overwrite existing file: {path}")
    path.write_text(content, encoding=LICENSE_ENCODING)
    return path


def generate_key(out_dir: Path, moment: datetime) -> KeyResult:
    private_key = Ed25519PrivateKey.generate()
    private_key_path = _write_new(
        out_dir, PRIVATE_KEY_STEM, _encode(private_key.private_bytes_raw()), moment
    )
    public_key = _encode(private_key.public_key().public_bytes_raw())
    return KeyResult(private_key_path=private_key_path, public_key=public_key)


def _read_private_key(path: Path) -> Ed25519PrivateKey:
    if not path.is_file():
        raise KeygenError(f"private key not found: {path}")
    encoded = path.read_text(encoding=LICENSE_ENCODING).strip()
    try:
        raw = base64.b64decode(encoded, validate=True)
    except binascii.Error as error:
        raise KeygenError("private key is not valid base64") from error
    try:
        return Ed25519PrivateKey.from_private_bytes(raw)
    except ValueError as error:
        raise KeygenError(f"private key in {path} is not a valid signing key: {error}") from error


def _parse_relative(value: str, moment: datetime) -> datetime:
    matched = re.match(RELATIVE_PATTERN, value)
    if matched is None:
        units = ", ".join(RELATIVE_UNIT_SECONDS)
        raise KeygenError(
            f"invalid relative expiry '{value}', expected a positive number and "
            f"one of the units {units}, like {RELATIVE_EXAMPLE}"
        )
    amount, unit = matched.groups()
    seconds = int(amount) * RELATIVE_UNIT_SECONDS[unit]
    if not seconds:
        raise KeygenError(f"relative expiry '{value}' is zero, the license would be expired")
    try:
        return moment.astimezone(timezone.utc) + timedelta(seconds=seconds)
    except (OverflowError, OSError) as error:
        raise KeygenError(f"relative expiry '{value}' is too far in the future") from error


def _parse_expires(value: str, moment: datetime) -> datetime:
    if value.startswith(RELATIVE_PREFIX):
        return _parse_relative(value, moment)
    try:
        parsed = datetime.strptime(value, LICENSE_DATE_FORMAT)
    except ValueError as error:
        raise KeygenError(
            f"invalid expiry '{value}', expected UTC like {ABSOLUTE_EXAMPLE} "
            f"or a relative offset like {RELATIVE_EXAMPLE}"
        ) from error
    return parsed.replace(tzinfo=timezone.utc)


def generate_license(
    private_key_path: Path, expires: str, contact: str, out_dir: Path, moment: datetime
) -> LicenseResult:
    private_key = _read_private_key(private_key_path)
    expires_at = _parse_expires(expires, moment)
    formatted = format_expires(expires_at)
    payload = payload_text(formatted, contact)
    signature = private_key.sign(payload.encode(LICENSE_ENCODING))
    path = _write_new(out_dir, LICENSE_STEM, render(payload, signature), moment)
    return LicenseResult(license_path=path, expires=formatted)


def _run_key(args: argparse.Namespace) -> int:
    result = generate_key(args.out_dir, datetime.now(timezone.utc))
    print(f"private key written to {result.private_key_path}")
    print(PUBLIC_KEY_NOTICE)
    print(result.public_key)
    return 0


def _run_license(args: argparse.Namespace) -> int:
    result = generate_license(
        args.private_key, args.expires, args.contact, args.out_dir, datetime.now(timezone.utc)
    )
    print(f"license valid until {result.expires} written to {result.license_path}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate signing keys and issue licenses")
    subparsers = parser.add_subparsers(dest="command", required=True)

    key = subparsers.add_parser(
        COMMAND_KEY, help="generate a private key and print its public key"
    )
    key.add_argument(
        "--out-dir",
        type=Path,
        default=Path.cwd(),
        help="directory to write the private key into (default: current directory)",
    )
    key.set_defaults(handler=_run_key)

    lic = subparsers.add_parser(COMMAND_LICENSE, help="issue a signed license file")
    lic.add_argument("--private-key", type=Path, required=True, help="path to the private key")
    lic.add_argument(
        "--expires",
        required=True,
        help=(
            f"expiry in UTC, like {ABSOLUTE_EXAMPLE}, or an offset from now "
            f"like {RELATIVE_EXAMPLE} (units: {', '.join(RELATIVE_UNIT_SECONDS)})"
        ),
    )
    lic.add_argument(
        "--contact", required=True, help="supplier contact shown to the customer"
    )
    lic.add_argument(
        "--out-dir",
        type=Path,
        default=Path.cwd(),
        help="directory to write the license file into (default: current directory)",
    )
    lic.set_defaults(handler=_run_license)

    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        return args.handler(args)
    except KeygenError as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
