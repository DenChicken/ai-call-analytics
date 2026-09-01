import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from issuing.generate import (
    EXPIRES_EXAMPLE,
    GenerateError,
    generate_key,
    generate_license,
)
from issuing.naming import OutputError

COMMAND_KEY = "key"
COMMAND_LICENSE = "license"
PUBLIC_KEY_NOTICE = "paste this public key into PUBLIC_KEY in keygen/licensing/license.py:"


def _run_key(args: argparse.Namespace) -> int:
    try:
        result = generate_key(args.out_dir, datetime.now(timezone.utc))
    except OutputError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"private key written to {result.private_key_path}")
    print(PUBLIC_KEY_NOTICE)
    print(result.public_key)
    return 0


def _run_license(args: argparse.Namespace) -> int:
    try:
        path = generate_license(
            args.private_key, args.expires, args.contact, args.out_dir, datetime.now(timezone.utc)
        )
    except (GenerateError, OutputError) as error:
        print(error, file=sys.stderr)
        return 1
    print(f"license valid until {args.expires} written to {path}")
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
    lic.add_argument("--expires", required=True, help=f"expiry in UTC, like {EXPIRES_EXAMPLE}")
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
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
