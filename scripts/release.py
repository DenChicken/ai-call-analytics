import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
import zipfile
from datetime import datetime, timezone
from pathlib import Path

MODULE_FETCHER = "fetcher"
MODULE_PIPELINE = "pipeline"
MODULE_WEBUI = "webui"

ALL_MODULES = (MODULE_FETCHER, MODULE_PIPELINE, MODULE_WEBUI)
PRIVATE_KEY_STEM = "license_private_key"
KEYGEN_SCRIPT = "keygen.py"
PRIVATE_NAMES = (KEYGEN_SCRIPT, PRIVATE_KEY_STEM)

COMPANY_NAME = "speech-analysis-engine"

OUTPUT_DIR_NAME = "release"
STAGE_DIR_NAME = "stage"
SCRIPTS_DIR_NAME = "scripts"
DOCKER_DIR_NAME = "docker"
IMAGES_DIR_NAME = "images"

DOCKER_COMMAND = "docker"
DOCKERFILE_TEMPLATE = "{module}.Dockerfile"
IMAGE_TEMPLATE = "{product}/{module}:{version}"
IMAGE_ARCHIVE_TEMPLATE = "{module}.tar"
STAMP_SUFFIX = ".id"
BUILD_ARGS = ("build", "-f")
BUILD_ARG_FLAG = "--build-arg"
TAG_FLAG = "-t"

BUILD_CONFIG_NAME = "build.toml"
LLAMA_SECTION = "llama"
LLAMA_CUDA_SECTION = "cuda"
BUILD_ARG_NAMES = {
    "LLAMA_VERSION": ("version",),
    "LLAMA_CPU_INDEX": ("cpu_index",),
    "LLAMA_CUDA_ARCHITECTURES": (LLAMA_CUDA_SECTION, "architectures"),
    "LLAMA_CUDA_CMAKE_ARGS": (LLAMA_CUDA_SECTION, "cmake_args"),
}
SAVE_ARGS = ("save", "-o")
INSPECT_ARGS = ("image", "inspect", "--format", "{{.Id}}")
DANGLING_ARGS = ("images", "-f", "dangling=true", "-q")

VERSION_PATTERN = r"^\d+(\.\d+)*$"
VERSION_TIMESTAMP_FORMAT = "%Y%m%d-%H%M"
ARCHIVE_NAME_TEMPLATE = "{product}_{version}_{timestamp}_{commit}.zip"
DIRTY_SUFFIX = "-dirty"
UNKNOWN_COMMIT = "nocommit"
COMMIT_LENGTH = 7

GIT_COMMAND = "git"
GIT_COMMIT_ARGS = ("rev-parse", "--short", "HEAD")
GIT_STATUS_ARGS = ("status", "--porcelain")

MANIFEST_NAME = "manifest.json"
MANIFEST_INDENT = 2
BYTES_IN_MIB = 1 << 20
CHECKSUM_CHUNK = BYTES_IN_MIB

BUNDLE_FILES = (
    (SCRIPTS_DIR_NAME, "db.py", SCRIPTS_DIR_NAME),
    (SCRIPTS_DIR_NAME, "user.py", SCRIPTS_DIR_NAME),
    (SCRIPTS_DIR_NAME, "fetch_models.py", SCRIPTS_DIR_NAME),
    (SCRIPTS_DIR_NAME, "schema.sql", SCRIPTS_DIR_NAME),
    (SCRIPTS_DIR_NAME, "requirements.txt", SCRIPTS_DIR_NAME),
    (SCRIPTS_DIR_NAME, "deploy.py", ""),
    (DOCKER_DIR_NAME, "compose.yaml", ""),
    (DOCKER_DIR_NAME, "compose.gpu.yaml", ""),
    (DOCKER_DIR_NAME, "deploy.toml", ""),
)
EXAMPLES_DIR_NAME = "examples"
DOCS_DIR_NAME = "docs"
PLATFORM_DIR_NAME = "platform"
SHELL_SUFFIX = ".sh"
IMAGE_SUFFIX = ".tar"
EXECUTABLE_MODE = 0o755
REGULAR_MODE = 0o644
ARCHIVE_CHUNK = BYTES_IN_MIB

ROOT = Path(__file__).resolve().parent.parent


class ReleaseError(Exception):
    pass


def _run_git(args: tuple[str, ...]) -> str | None:
    try:
        result = subprocess.run(
            [GIT_COMMAND, *args], cwd=ROOT, capture_output=True, text=True, check=False
        )
    except FileNotFoundError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _commit_label() -> str:
    commit = _run_git(GIT_COMMIT_ARGS)
    if commit is None:
        print("warning: git is unavailable, the archive will not name a commit", file=sys.stderr)
        return UNKNOWN_COMMIT
    if _run_git(GIT_STATUS_ARGS):
        print(
            f"warning: working tree has uncommitted changes, marking the build {DIRTY_SUFFIX}",
            file=sys.stderr,
        )
        return f"{commit[:COMMIT_LENGTH]}{DIRTY_SUFFIX}"
    return commit[:COMMIT_LENGTH]


def read_build_config() -> dict[str, str]:
    path = ROOT / DOCKER_DIR_NAME / BUILD_CONFIG_NAME
    if not path.is_file():
        raise ReleaseError(f"build config not found: {path}")

    with path.open("rb") as handle:
        raw = tomllib.load(handle).get(LLAMA_SECTION, {})

    arguments = {}
    for name, keys in BUILD_ARG_NAMES.items():
        value = raw
        for key in keys:
            value = value.get(key, {}) if isinstance(value, dict) else {}
        if not isinstance(value, str) or not value:
            location = ".".join((LLAMA_SECTION, *keys))
            raise ReleaseError(f"missing or empty '{location}' in {BUILD_CONFIG_NAME}")
        arguments[name] = value
    return arguments


def build_image(module: str, version: str, build_args: dict[str, str]) -> str:
    dockerfile = ROOT / DOCKER_DIR_NAME / DOCKERFILE_TEMPLATE.format(module=module)
    if not dockerfile.is_file():
        raise ReleaseError(f"dockerfile not found: {dockerfile}")

    arguments = []
    if module == MODULE_PIPELINE:
        for name, value in build_args.items():
            arguments += [BUILD_ARG_FLAG, f"{name}={value}"]

    tag = IMAGE_TEMPLATE.format(product=COMPANY_NAME, module=module, version=version)
    started = time.monotonic()
    print(f"[{module}] building {tag}", flush=True)
    result = subprocess.run(
        [DOCKER_COMMAND, *BUILD_ARGS, str(dockerfile), *arguments, TAG_FLAG, tag, str(ROOT)],
        check=False,
    )
    if result.returncode != 0:
        raise ReleaseError(f"docker build failed for {module} with exit code {result.returncode}")
    print(f"[{module}] built in {time.monotonic() - started:.0f}s", flush=True)
    return tag


def _report_dangling() -> None:
    result = subprocess.run(
        [DOCKER_COMMAND, *DANGLING_ARGS], capture_output=True, text=True, check=False
    )
    count = len(result.stdout.split()) if result.returncode == 0 else 0
    if count:
        print(f"{count} untagged images left from earlier builds, remove them with:")
        print(f"  {DOCKER_COMMAND} image prune -f")


def image_id(tag: str) -> str:
    result = subprocess.run(
        [DOCKER_COMMAND, *INSPECT_ARGS, tag], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise ReleaseError(f"docker inspect failed for {tag}")
    return result.stdout.strip()


def save_image(module: str, tag: str, images_dir: Path) -> None:
    archive = images_dir / IMAGE_ARCHIVE_TEMPLATE.format(module=module)
    stamp = archive.with_suffix(STAMP_SUFFIX)
    current = image_id(tag)

    if archive.is_file() and stamp.is_file() and stamp.read_text(encoding="utf-8") == current:
        print(f"[{module}] {archive.name} is up to date, keeping it", flush=True)
        return

    started = time.monotonic()
    print(f"[{module}] saving to {archive.name}", flush=True)
    if subprocess.run([DOCKER_COMMAND, *SAVE_ARGS, str(archive), tag], check=False).returncode != 0:
        raise ReleaseError(f"docker save failed for {module}")

    stamp.write_text(current, encoding="utf-8")
    size = archive.stat().st_size
    print(
        f"[{module}] saved {size / BYTES_IN_MIB:.0f} MiB in {time.monotonic() - started:.0f}s",
        flush=True,
    )


def build_modules(
    modules: tuple[str, ...], images_dir: Path, version: str, build_args: dict[str, str]
) -> None:
    images_dir.mkdir(parents=True, exist_ok=True)
    for module in modules:
        save_image(module, build_image(module, version, build_args), images_dir)


def collect_images(images_dir: Path, stage_dir: Path) -> None:
    target = stage_dir / IMAGES_DIR_NAME
    target.mkdir(parents=True, exist_ok=True)

    for module in ALL_MODULES:
        archive = images_dir / IMAGE_ARCHIVE_TEMPLATE.format(module=module)
        if not archive.is_file():
            raise ReleaseError(
                f"{archive} is missing: build every module before packing the bundle"
            )
        link = target / archive.name
        try:
            os.link(archive, link)
        except OSError:
            shutil.copy2(archive, link)
    print(f"[images] {len(ALL_MODULES)} images in the bundle", flush=True)


def collect_files(stage_dir: Path) -> None:
    for source_dir, name, target_dir in BUNDLE_FILES:
        source = ROOT / source_dir / name
        if not source.is_file():
            raise ReleaseError(f"deployment file not found: {source}")
        target = stage_dir / target_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    platform = _collect_platform(stage_dir)
    collected = _collect_configs(stage_dir)
    docs = _collect_docs(stage_dir)
    print(
        f"[collect] {len(BUNDLE_FILES)} files, {platform} platform scripts, "
        f"{collected} config examples and {docs} documentation pages",
        flush=True,
    )


def _collect_platform(stage_dir: Path) -> int:
    source_root = ROOT / SCRIPTS_DIR_NAME / PLATFORM_DIR_NAME
    if not source_root.is_dir():
        raise ReleaseError(f"platform scripts not found: {source_root}")

    collected = 0
    for script in sorted(source_root.rglob("*")):
        if not script.is_file():
            continue
        target = (
            stage_dir / SCRIPTS_DIR_NAME / PLATFORM_DIR_NAME / script.relative_to(source_root)
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(script, target)
        collected += 1

    if not collected:
        raise ReleaseError(f"no platform scripts found in {source_root}")
    return collected


def _collect_configs(stage_dir: Path) -> int:
    source_root = ROOT / EXAMPLES_DIR_NAME
    if not source_root.is_dir():
        raise ReleaseError(f"config examples not found: {source_root}")

    collected = 0
    for example in sorted(source_root.rglob("*")):
        if not example.is_file():
            continue
        target = stage_dir / EXAMPLES_DIR_NAME / example.relative_to(source_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(example, target)
        collected += 1

    if not collected:
        raise ReleaseError(f"no config examples found in {source_root}")
    return collected


def _collect_docs(stage_dir: Path) -> int:
    source_root = ROOT / DOCS_DIR_NAME
    if not source_root.is_dir():
        raise ReleaseError(f"documentation not found: {source_root}")

    collected = 0
    for page in sorted(source_root.rglob("*")):
        if not page.is_file():
            continue
        target = stage_dir / DOCS_DIR_NAME / page.relative_to(source_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(page, target)
        collected += 1

    if not collected:
        raise ReleaseError(f"no documentation found in {source_root}")
    return collected


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHECKSUM_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(
    stage_dir: Path, version: str, commit: str, built_at: datetime, build_args: dict[str, str]
) -> None:
    entries = {}
    for path in sorted(stage_dir.rglob("*")):
        if path.is_file():
            entries[path.relative_to(stage_dir).as_posix()] = _checksum(path)

    manifest = {
        "product": COMPANY_NAME,
        "version": version,
        "commit": commit,
        "built_at": built_at.isoformat(),
        "build": build_args,
        "files": entries,
    }
    (stage_dir / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=MANIFEST_INDENT, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[manifest] {len(entries)} files", flush=True)


def verify_no_private_content(stage_dir: Path) -> None:
    leaked = [
        path.relative_to(stage_dir).as_posix()
        for path in stage_dir.rglob("*")
        if any(
            name in (path.name, path.parent.name) or path.name.startswith(name)
            for name in PRIVATE_NAMES
        )
    ]
    if leaked:
        raise ReleaseError(
            f"private content must never be delivered, found in the bundle: {leaked}"
        )
    print("[verify] no private content in the bundle", flush=True)


def make_archive(stage_dir: Path, output_dir: Path, name: str) -> Path:
    archive = output_dir / name
    if archive.exists():
        raise ReleaseError(f"refusing to overwrite an existing archive: {archive}")

    started = time.monotonic()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(stage_dir.rglob("*")):
            if not path.is_file():
                continue
            name = path.relative_to(stage_dir).as_posix()
            info = zipfile.ZipInfo.from_file(path, name)
            info.compress_type = (
                zipfile.ZIP_STORED if path.suffix == IMAGE_SUFFIX else zipfile.ZIP_DEFLATED
            )
            mode = EXECUTABLE_MODE if path.suffix == SHELL_SUFFIX else REGULAR_MODE
            info.external_attr = mode << 16
            with path.open("rb") as source, bundle.open(info, "w") as target:
                shutil.copyfileobj(source, target, ARCHIVE_CHUNK)
    size = archive.stat().st_size
    print(
        f"[archive] {archive.name}, {size / BYTES_IN_MIB:.1f} MiB "
        f"in {time.monotonic() - started:.0f}s",
        flush=True,
    )
    return archive


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a versioned delivery bundle")
    parser.add_argument("--version", required=True, help="release version, like 1.1.2")
    parser.add_argument(
        "--modules",
        nargs="*",
        choices=ALL_MODULES,
        default=[],
        help="modules to build (default: all)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=ROOT / OUTPUT_DIR_NAME,
        help=f"output directory (default: {OUTPUT_DIR_NAME})",
    )
    parser.add_argument(
        "--keep-stage",
        action="store_true",
        help="keep the staging directory after the archive is written",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not re.match(VERSION_PATTERN, args.version):
        print(f"version error: '{args.version}' is not a dotted number like 1.1.2", file=sys.stderr)
        return 1

    built_at = datetime.now(timezone.utc)
    commit = _commit_label()
    modules = tuple(args.modules) or ALL_MODULES

    images_dir = args.output / IMAGES_DIR_NAME
    stage_dir = args.output / STAGE_DIR_NAME
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)

    name = ARCHIVE_NAME_TEMPLATE.format(
        product=COMPANY_NAME,
        version=args.version,
        timestamp=built_at.strftime(VERSION_TIMESTAMP_FORMAT),
        commit=commit,
    )

    try:
        build_args = read_build_config()
        build_modules(modules, images_dir, args.version, build_args)
        collect_images(images_dir, stage_dir)
        collect_files(stage_dir)
        verify_no_private_content(stage_dir)
        write_manifest(stage_dir, args.version, commit, built_at, build_args)
        archive = make_archive(stage_dir, args.output, name)
    except ReleaseError as error:
        print(f"release error: {error}", file=sys.stderr)
        print(f"staging directory kept for inspection: {stage_dir}", file=sys.stderr)
        return 1

    if not args.keep_stage:
        shutil.rmtree(stage_dir)

    print(f"\nrelease {args.version} ({commit}) ready: {archive}")
    _report_dangling()
    return 0


if __name__ == "__main__":
    sys.exit(main())
