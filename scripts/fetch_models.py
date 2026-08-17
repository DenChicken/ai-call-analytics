import argparse
import importlib
import inspect
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

import yaml
from huggingface_hub import HfApi, snapshot_download
from huggingface_hub.errors import GatedRepoError
from pyannote.audio.core.model import AssetFileName

MODEL_SECTIONS = ("asr", "diarization", "llm")
MODELS_SECTION = "models"
DIARIZATION_SECTION = "diarization"
TOKEN_KEY = "hf_token_file"
REQUIRED_MODEL_KEYS = ("repo_id", "local_dir")

OFFLINE_CONFIG_NAME = "config.offline.yaml"
DEPENDENCY_DIR_NAME = "dependencies"
CHECKPOINT_KEY = "checkpoint"
SUBFOLDER_KEY = "subfolder"
REPO_ID_SEPARATOR = "/"


class ScriptError(Exception):
    pass


@dataclass(frozen=True)
class ModelSpec:
    section: str
    repo_id: str
    local_dir: Path
    token: str


@dataclass(frozen=True)
class Dependency:
    param: str
    repo_id: str
    subfolder: str | None

    def download_dir(self, root: Path) -> Path:
        return root / DEPENDENCY_DIR_NAME / self.repo_id.split(REPO_ID_SEPARATOR)[-1]

    def checkpoint_dir(self, root: Path) -> Path:
        target = self.download_dir(root)
        return target / self.subfolder if self.subfolder else target


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

    if TOKEN_KEY not in section(MODELS_SECTION):
        raise ScriptError(f"missing required key '{TOKEN_KEY}' in [{MODELS_SECTION}]")
    token = read_secret_file(Path(section(MODELS_SECTION)[TOKEN_KEY]))

    specs = []
    for name in MODEL_SECTIONS:
        entry = section(name)
        for key in REQUIRED_MODEL_KEYS:
            if key not in entry:
                raise ScriptError(f"missing required key '{key}' in [{name}]")
        specs.append(
            ModelSpec(
                section=name,
                repo_id=entry["repo_id"],
                local_dir=Path(entry["local_dir"]).resolve(),
                token=token,
            )
        )
    return specs


def read_dependencies(spec: ModelSpec) -> list[Dependency]:
    """Repositories the pipeline pulls in beyond its own, resolved from its config and class."""
    config_path = spec.local_dir / AssetFileName.Pipeline.value
    if spec.section != DIARIZATION_SECTION or not config_path.is_file():
        return []

    pipeline = yaml.safe_load(config_path.read_text(encoding="utf-8"))["pipeline"]
    params = pipeline.get("params") or {}
    module_name, _, class_name = pipeline["name"].rpartition(".")
    pipeline_class = getattr(importlib.import_module(module_name), class_name)

    dependencies = []
    for param in inspect.signature(pipeline_class.__init__).parameters.values():
        declared = params.get(param.name)
        source = declared if declared is not None else param.default
        if isinstance(source, str) and REPO_ID_SEPARATOR in source:
            source = {CHECKPOINT_KEY: source}
        if not isinstance(source, dict) or CHECKPOINT_KEY not in source:
            continue
        repo_id = source[CHECKPOINT_KEY]
        if Path(repo_id).is_dir():
            continue
        dependencies.append(
            Dependency(
                param=param.name,
                repo_id=repo_id,
                subfolder=source.get(SUBFOLDER_KEY),
            )
        )
    return dependencies


def check_access(specs: list[ModelSpec]) -> int:
    api = HfApi()
    unreachable = []

    for spec in specs:
        dependencies = read_dependencies(spec)
        for repo_id in [spec.repo_id] + [d.repo_id for d in dependencies]:
            try:
                api.auth_check(repo_id, token=spec.token)
                print(f"[{spec.section}] {repo_id}: ok")
            except Exception as error:
                reason = "gated" if isinstance(error, GatedRepoError) else error
                print(f"[{spec.section}] {repo_id}: FAILED: {reason}")
                unreachable.append(repo_id)

        if spec.section == DIARIZATION_SECTION and not dependencies:
            print(
                f"[{spec.section}] nested dependencies stay unknown until {spec.repo_id} "
                "is downloaded, so re-run this check afterwards"
            )

    if unreachable:
        print("\naccept the conditions while signed in with the account owning", file=sys.stderr)
        print("the token, then run this check again:", file=sys.stderr)
        for repo_id in unreachable:
            print(f"  https://huggingface.co/{repo_id}", file=sys.stderr)
        return 1

    print("\nall repositories are reachable")
    return 0


def download_repo(repo_id: str, local_dir: Path, token: str) -> None:
    local_dir.mkdir(parents=True, exist_ok=True)
    try:
        snapshot_download(repo_id=repo_id, local_dir=str(local_dir), token=token)
    except GatedRepoError as error:
        raise ScriptError(f"{repo_id} is gated, run with --check for details") from error


def download(spec: ModelSpec) -> None:
    print(f"[{spec.section}] {spec.repo_id} -> {spec.local_dir}", flush=True)
    download_repo(spec.repo_id, spec.local_dir, spec.token)

    dependencies = read_dependencies(spec)
    if not dependencies:
        return

    config_path = spec.local_dir / AssetFileName.Pipeline.value
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    params = config["pipeline"].setdefault("params", {})

    for dependency in dependencies:
        print(f"[{spec.section}] {dependency.param}: {dependency.repo_id}", flush=True)
        download_repo(dependency.repo_id, dependency.download_dir(spec.local_dir), spec.token)
        params[dependency.param] = str(dependency.checkpoint_dir(spec.local_dir))

    offline_path = spec.local_dir / OFFLINE_CONFIG_NAME
    offline_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    print(f"[{spec.section}] offline config written to {offline_path}", flush=True)


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
