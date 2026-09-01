import argparse
import base64
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from keygen.constants import LICENSE_ENCODING

PRIVATE_KEY_FILE = "license_private_key"
PUBLIC_KEY_MODULE = "public_key.py"
PUBLIC_KEY_CONSTANT = "PUBLIC_KEY"
PUBLIC_KEY_TEMPLATE = '{constant} = "{value}"\n'


def _encode(raw: bytes) -> str:
    return base64.b64encode(raw).decode(LICENSE_ENCODING)


def generate(private_key_path: Path, public_key_module_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    private_raw = private_key.private_bytes_raw()
    public_raw = private_key.public_key().public_bytes_raw()

    private_key_path.write_text(_encode(private_raw), encoding=LICENSE_ENCODING)
    public_key_module_path.write_text(
        PUBLIC_KEY_TEMPLATE.format(constant=PUBLIC_KEY_CONSTANT, value=_encode(public_raw)),
        encoding=LICENSE_ENCODING,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the Ed25519 key pair for license signing"
    )
    parser.add_argument(
        "--private-key",
        type=Path,
        required=True,
        help=f"path to write the private key (keep it secret, e.g. secrets/{PRIVATE_KEY_FILE})",
    )
    parser.add_argument(
        "--public-module",
        type=Path,
        default=Path(__file__).resolve().parent / PUBLIC_KEY_MODULE,
        help="path to write the public key module compiled into the components",
    )
    args = parser.parse_args()

    if args.private_key.exists():
        print(f"private key already exists: {args.private_key}", file=sys.stderr)
        return 1

    generate(args.private_key, args.public_module)
    print(f"private key written to {args.private_key}")
    print(f"public key module written to {args.public_module}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
