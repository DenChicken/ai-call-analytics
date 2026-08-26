import argparse
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download
from huggingface_hub.errors import GatedRepoError

MODEL_SECTIONS = ("asr", "llm")
HUGGINGFACE_SECTION = "huggingface"
PATHS_SECTION = "paths"
MODELS_DIR_KEY = "models_dir"
SECRETS_DIR_KEY = "secrets_dir"
TOKEN_KEY = "token_file"
REQUIRED_MODEL_KEYS = ("repo_id", "local_dir")


class ScriptError(Exception):
    pass


@dataclass(frozen=True)
class ModelSpec:
    section: str
    repo_id: str
    local_dir: Path
    token: str


def read_secret_file(path: Path) -> str:
    if not path.is_file():
        raise ScriptError(f"secret file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        value = handle.readline().strip()
    if not value:
        raise ScriptError(f"secret file is empty: {path}")
    return value


def load_specs(config_path: Path) -> list[ModelSpec]:
    if not config_path.is_file():
        raise ScriptError(f"config file not found: {config_path}")

    with config_path.open("rb") as handle:
        raw = tomllib.load(handle)

    def section(name: str) -> dict:
        if name not in raw:
            raise ScriptError(f"missing required section [{name}] in {config_path}")
        return raw[name]

    def anchor(key: str) -> Path:
        paths = section(PATHS_SECTION)
        if key not in paths:
            raise ScriptError(f"missing required key '{key}' in [{PATHS_SECTION}]")
        value = Path(paths[key])
        if not value.is_absolute():
            raise ScriptError(
                f"'{key}' in [{PATHS_SECTION}] must be an absolute path, got {value}"
            )
        return value.resolve()

    models_dir = anchor(MODELS_DIR_KEY)
    secrets_dir = anchor(SECRETS_DIR_KEY)

    if TOKEN_KEY not in section(HUGGINGFACE_SECTION):
        raise ScriptError(f"missing required key '{TOKEN_KEY}' in [{HUGGINGFACE_SECTION}]")
    token = read_secret_file(secrets_dir / section(HUGGINGFACE_SECTION)[TOKEN_KEY])

    specs = []
    seen = set()
    for name in MODEL_SECTIONS:
        entry = section(name)
        for key in REQUIRED_MODEL_KEYS:
            if key not in entry:
                raise ScriptError(f"missing required key '{key}' in [{name}]")
        if entry["repo_id"] in seen:
            continue
        seen.add(entry["repo_id"])
        specs.append(
            ModelSpec(
                section=name,
                repo_id=entry["repo_id"],
                local_dir=models_dir / entry["local_dir"],
                token=token,
            )
        )
    return specs


def check_access(specs: list[ModelSpec]) -> int:
    api = HfApi()
    unreachable = []

    for spec in specs:
        try:
            api.auth_check(spec.repo_id, token=spec.token)
            print(f"[{spec.section}] {spec.repo_id}: ok")
        except Exception as error:
            reason = "gated" if isinstance(error, GatedRepoError) else error
            print(f"[{spec.section}] {spec.repo_id}: FAILED: {reason}")
            unreachable.append(spec.repo_id)

    if unreachable:
        print("\naccept the conditions while signed in with the account owning", file=sys.stderr)
        print("the token, then run this check again:", file=sys.stderr)
        for repo_id in unreachable:
            print(f"  https://huggingface.co/{repo_id}", file=sys.stderr)
        return 1

    print("\nall repositories are reachable")
    return 0


def download(spec: ModelSpec) -> None:
    print(f"[{spec.section}] {spec.repo_id} -> {spec.local_dir}", flush=True)
    spec.local_dir.mkdir(parents=True, exist_ok=True)
    try:
        snapshot_download(
            repo_id=spec.repo_id, local_dir=str(spec.local_dir), token=spec.token
        )
    except GatedRepoError as error:
        raise ScriptError(f"{spec.repo_id} is gated, run with --check for details") from error


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download pipeline models declared in the pipeline config"
    )
    parser.add_argument("-c", "--config", required=True, type=Path, help="path to pipeline config")
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify token access to every repository without downloading anything",
    )
    args = parser.parse_args()

    try:
        specs = load_specs(args.config)
    except ScriptError as error:
        print(error, file=sys.stderr)
        return 1

    if args.check:
        return check_access(specs)

    failures = {}
    for spec in specs:
        try:
            download(spec)
        except Exception as error:
            failures[spec.section] = error

    print()
    for spec in specs:
        error = failures.get(spec.section)
        print(f"[{spec.section}] {spec.repo_id}: {f'FAILED: {error}' if error else 'ok'}")

    if failures:
        print(f"\n{len(failures)} of {len(specs)} models failed", file=sys.stderr)
        print("run with --check to see which repositories the token cannot reach", file=sys.stderr)
        return 1

    print(f"\ndownloaded {len(specs)} models")
    return 0


if __name__ == "__main__":
    sys.exit(main())
