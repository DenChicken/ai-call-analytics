import argparse
import compileall
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

MODULE_FETCHER = "fetcher"
MODULE_PIPELINE = "pipeline"
MODULE_WEBUI = "webui"

COMPILED_MODULES = (MODULE_FETCHER, MODULE_PIPELINE)
BYTECODE_MODULES = (MODULE_WEBUI,)
ALL_MODULES = (*COMPILED_MODULES, *BYTECODE_MODULES)
PRIVATE_KEY_STEM = "license_private_key"
KEYGEN_SCRIPT = "keygen.py"

ENTRY_POINT = "main.py"
SOURCE_PACKAGE = "src"
LICENSING_PACKAGE = "licensing"
PRIVATE_NAMES = (KEYGEN_SCRIPT, PRIVATE_KEY_STEM)

OUTPUT_DIR_NAME = "release"
STAGE_DIR_NAME = "stage"
SCRIPTS_DIR_NAME = "scripts"

NUITKA_MODULE = "nuitka"
NUITKA_FLAGS = (
    "--nofollow-imports",
    "--assume-yes-for-downloads",
    "--remove-output",
    "--no-deployment-flag=self-execution",
)
NUITKA_OUTPUT_FLAG = "--output-dir"
NUITKA_NAME_FLAG = "--output-filename"
NUITKA_FOLLOW_FLAG = "--follow-import-to"
NUITKA_INCLUDE_FLAG = "--include-package"
NUITKA_COMPANY_FLAG = "--company-name"
NUITKA_PRODUCT_FLAG = "--product-name"
COMPANY_NAME = "ai-call-analytics"

BYTECODE_OPTIMIZE_LEVEL = 2
BYTECODE_SOURCE_SUFFIX = ".py"
EXCLUDED_PATTERNS = ("__pycache__", ".web", ".states", "reflex.lock", ".gitignore")

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
CHECKSUM_CHUNK = 1 << 20

HELP_FLAG = "--help"
NO_USER_SITE_VAR = "PYTHONNOUSERSITE"
PYTHONPATH_VAR = "PYTHONPATH"
MISSING_LICENSING_MARKER = "No module named 'licensing'"

DEPLOY_FILES = ("db.py", "user.py", "schema.sql", "requirements.txt")

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


def _nuitka_command(module: str, output_dir: Path) -> list[str]:
    command = [
        sys.executable,
        "-m",
        NUITKA_MODULE,
        *NUITKA_FLAGS,
        f"{NUITKA_OUTPUT_FLAG}={output_dir}",
        f"{NUITKA_NAME_FLAG}={module}",
        f"{NUITKA_COMPANY_FLAG}={COMPANY_NAME}",
        f"{NUITKA_PRODUCT_FLAG}={module}",
    ]
    command.append(f"{NUITKA_FOLLOW_FLAG}={SOURCE_PACKAGE}")
    command.append(f"{NUITKA_INCLUDE_FLAG}={LICENSING_PACKAGE}")
    command.append(ENTRY_POINT)
    return command


def compile_binary(module: str, output_root: Path) -> Path:
    source_dir = ROOT / module
    if not (source_dir / ENTRY_POINT).is_file():
        raise ReleaseError(f"entry point not found: {source_dir / ENTRY_POINT}")

    output_dir = output_root / module
    output_dir.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    print(f"[{module}] compiling with nuitka", flush=True)
    result = subprocess.run(_nuitka_command(module, output_dir), cwd=source_dir, check=False)
    if result.returncode != 0:
        raise ReleaseError(f"nuitka failed for {module} with exit code {result.returncode}")

    binary = output_dir / module
    if not binary.is_file():
        present = sorted(entry.name for entry in output_dir.iterdir())
        raise ReleaseError(
            f"nuitka reported success but {binary} is missing, output contains: {present}"
        )
    print(f"[{module}] compiled in {time.monotonic() - started:.0f}s", flush=True)
    _verify_embedded_licensing(module, binary)
    return binary


def _verify_embedded_licensing(module: str, binary: Path) -> None:
    environment = dict(os.environ)
    environment[NO_USER_SITE_VAR] = "1"
    environment.pop(PYTHONPATH_VAR, None)

    result = subprocess.run(
        [str(binary), HELP_FLAG],
        cwd=binary.parent,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or MISSING_LICENSING_MARKER in result.stderr:
        raise ReleaseError(
            f"{module} does not carry {LICENSING_PACKAGE} inside the binary: "
            f"{result.stderr.strip() or 'unexpected exit code ' + str(result.returncode)}"
        )
    print(f"[{module}] {LICENSING_PACKAGE} is embedded", flush=True)


def compile_bytecode(module: str, output_root: Path) -> Path:
    source_dir = ROOT / module
    if not source_dir.is_dir():
        raise ReleaseError(f"module directory not found: {source_dir}")

    output_dir = output_root / module
    if output_dir.exists():
        shutil.rmtree(output_dir)

    started = time.monotonic()
    print(f"[{module}] compiling to bytecode", flush=True)
    shutil.copytree(source_dir, output_dir, ignore=shutil.ignore_patterns(*EXCLUDED_PATTERNS))

    if not compileall.compile_dir(
        output_dir, legacy=True, optimize=BYTECODE_OPTIMIZE_LEVEL, force=True, quiet=1
    ):
        raise ReleaseError(f"bytecode compilation failed for {module}")

    for source in output_dir.rglob(f"*{BYTECODE_SOURCE_SUFFIX}"):
        source.unlink()
    print(f"[{module}] compiled in {time.monotonic() - started:.0f}s", flush=True)
    return output_dir


def build_modules(modules: tuple[str, ...], stage_dir: Path) -> None:
    for module in modules:
        if module in BYTECODE_MODULES:
            compile_bytecode(module, stage_dir)
        else:
            compile_binary(module, stage_dir)


def collect_deploy_files(stage_dir: Path) -> None:
    target = stage_dir / SCRIPTS_DIR_NAME
    target.mkdir(parents=True, exist_ok=True)
    for name in DEPLOY_FILES:
        source = ROOT / SCRIPTS_DIR_NAME / name
        if not source.is_file():
            raise ReleaseError(f"deployment file not found: {source}")
        shutil.copy2(source, target / name)
    print(f"[deploy] collected {len(DEPLOY_FILES)} files", flush=True)


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHECKSUM_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(stage_dir: Path, version: str, commit: str, built_at: datetime) -> None:
    entries = {}
    for path in sorted(stage_dir.rglob("*")):
        if path.is_file():
            entries[path.relative_to(stage_dir).as_posix()] = _checksum(path)

    manifest = {
        "product": COMPANY_NAME,
        "version": version,
        "commit": commit,
        "built_at": built_at.isoformat(),
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
            if path.is_file():
                bundle.write(path, path.relative_to(stage_dir).as_posix())
    size = archive.stat().st_size
    print(
        f"[archive] {archive.name}, {size / (1 << 20):.1f} MiB "
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
        build_modules(modules, stage_dir)
        collect_deploy_files(stage_dir)
        verify_no_private_content(stage_dir)
        write_manifest(stage_dir, args.version, commit, built_at)
        archive = make_archive(stage_dir, args.output, name)
    except ReleaseError as error:
        print(f"release error: {error}", file=sys.stderr)
        print(f"staging directory kept for inspection: {stage_dir}", file=sys.stderr)
        return 1

    if not args.keep_stage:
        shutil.rmtree(stage_dir)

    print(f"\nrelease {args.version} ({commit}) ready: {archive}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
