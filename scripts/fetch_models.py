import argparse
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from huggingface_hub import snapshot_download

MODEL_SECTIONS = ("asr", "diarization", "llm")
TOKEN_KEY = "hf_token_file"


class ScriptError(Exception):
    pass


@dataclass(frozen=True)
class ModelSpec:
    section: str
    repo_id: str
    local_dir: Path
    token: str | None


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

    specs = []
    for section in MODEL_SECTIONS:
        if section not in raw:
            raise ScriptError(f"missing required section [{section}] in {config_path}")
        entry = raw[section]
        for key in ("repo_id", "local_dir"):
            if key not in entry:
                raise ScriptError(f"missing required key '{key}' in [{section}]")
        token_path = entry.get(TOKEN_KEY)
        specs.append(
            ModelSpec(
                section=section,
                repo_id=entry["repo_id"],
                local_dir=Path(entry["local_dir"]).resolve(),
                token=read_secret_file(Path(token_path)) if token_path else None,
            )
        )
    return specs


def download(spec: ModelSpec) -> None:
    print(f"[{spec.section}] {spec.repo_id} -> {spec.local_dir}")
    spec.local_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=spec.repo_id,
        local_dir=str(spec.local_dir),
        token=spec.token,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download pipeline models declared in the pipeline config"
    )
    parser.add_argument("-c", "--config", required=True, type=Path, help="path to pipeline config")
    args = parser.parse_args()

    try:
        specs = load_specs(args.config)
    except ScriptError as error:
        print(error, file=sys.stderr)
        return 1

    for spec in specs:
        try:
            download(spec)
        except Exception as error:
            print(f"failed to download {spec.repo_id}: {error}", file=sys.stderr)
            return 1

    print(f"downloaded {len(specs)} models")
    return 0


if __name__ == "__main__":
    sys.exit(main())
