import argparse
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

import yaml
from huggingface_hub import snapshot_download
from huggingface_hub.errors import GatedRepoError
from pyannote.audio.core.model import AssetFileName

MODEL_SECTIONS = ("asr", "diarization", "llm")
MODELS_SECTION = "models"
DIARIZATION_SECTION = "diarization"
TOKEN_KEY = "hf_token_file"
GATED_REPO_HINT = (
    "this repository is gated: open https://huggingface.co/{repo_id} while signed in "
    "with the account owning the token and accept the conditions"
)

OFFLINE_CONFIG_NAME = "config.offline.yaml"
DEPENDENCY_DIR_NAME = "dependencies"
DEPENDENCY_KEYS = ("segmentation", "embedding")


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

    if MODELS_SECTION not in raw:
        raise ScriptError(f"missing required section [{MODELS_SECTION}] in {config_path}")
    if TOKEN_KEY not in raw[MODELS_SECTION]:
        raise ScriptError(f"missing required key '{TOKEN_KEY}' in [{MODELS_SECTION}]")
    token = read_secret_file(Path(raw[MODELS_SECTION][TOKEN_KEY]))

    specs = []
    for section in MODEL_SECTIONS:
        if section not in raw:
            raise ScriptError(f"missing required section [{section}] in {config_path}")
        entry = raw[section]
        for key in ("repo_id", "local_dir"):
            if key not in entry:
                raise ScriptError(f"missing required key '{key}' in [{section}]")
        specs.append(
            ModelSpec(
                section=section,
                repo_id=entry["repo_id"],
                local_dir=Path(entry["local_dir"]).resolve(),
                token=token,
            )
        )
    return specs


def download_repo(repo_id: str, local_dir: Path, token: str) -> None:
    local_dir.mkdir(parents=True, exist_ok=True)
    try:
        snapshot_download(repo_id=repo_id, local_dir=str(local_dir), token=token)
    except GatedRepoError as error:
        raise ScriptError(GATED_REPO_HINT.format(repo_id=repo_id)) from error


def download(spec: ModelSpec) -> None:
    print(f"[{spec.section}] {spec.repo_id} -> {spec.local_dir}", flush=True)
    download_repo(spec.repo_id, spec.local_dir, spec.token)
    if spec.section == DIARIZATION_SECTION:
        vendor_diarization_dependencies(spec)


def vendor_diarization_dependencies(spec: ModelSpec) -> None:
    source_path = spec.local_dir / AssetFileName.Pipeline.value
    if not source_path.is_file():
        raise ScriptError(f"{AssetFileName.Pipeline.value} not found in {spec.local_dir}")

    config = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    params = config["pipeline"]["params"]

    checkpoint_name = AssetFileName.Model.value
    for key in DEPENDENCY_KEYS:
        repo_id = params.get(key)
        if not repo_id:
            raise ScriptError(f"'{key}' missing in {source_path}")

        target = spec.local_dir / DEPENDENCY_DIR_NAME / repo_id.split("/")[-1]
        print(f"[{spec.section}] {key}: {repo_id} -> {target}", flush=True)
        download_repo(repo_id, target, spec.token)

        if not (target / checkpoint_name).is_file():
            raise ScriptError(f"{checkpoint_name} not found in {target}")
        params[key] = str(target)

    offline_path = spec.local_dir / OFFLINE_CONFIG_NAME
    offline_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    print(f"[{spec.section}] offline config written to {offline_path}", flush=True)


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
        print(f"\n{len(failures)} of {len(specs)} models could not be downloaded", file=sys.stderr)
        return 1

    print(f"\ndownloaded {len(specs)} models")
    return 0


if __name__ == "__main__":
    sys.exit(main())
