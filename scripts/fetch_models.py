import argparse
import sys
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download, snapshot_download
from huggingface_hub.errors import GatedRepoError

REPO_SEPARATOR = "/"
FILE_SEPARATOR = ":"
OK = "ok"
FAILED = "FAILED"


class ScriptError(Exception):
    pass


def read_token(path: Path | None) -> str | None:
    if path is None:
        return None
    if not path.is_file():
        raise ScriptError(f"token file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        token = handle.readline().strip()
    if not token:
        raise ScriptError(f"token file is empty: {path}")
    return token


def split_target(target: str) -> tuple[str, str | None]:
    repo_id, separator, file_name = target.partition(FILE_SEPARATOR)
    return repo_id, file_name if separator else None


def target_dir(models_dir: Path, repo_id: str) -> Path:
    return models_dir / repo_id.rsplit(REPO_SEPARATOR, 1)[-1]


def check_access(targets: list[str], token: str | None) -> int:
    api = HfApi()
    unreachable = []

    for repo_id in dict.fromkeys(split_target(target)[0] for target in targets):
        try:
            api.auth_check(repo_id, token=token)
            print(f"{repo_id}: {OK}")
        except Exception as error:
            reason = "gated" if isinstance(error, GatedRepoError) else error
            print(f"{repo_id}: {FAILED}: {reason}")
            unreachable.append(repo_id)

    if unreachable:
        print("\naccept the conditions while signed in with the account owning", file=sys.stderr)
        print("the token, then run this check again:", file=sys.stderr)
        for repo_id in unreachable:
            print(f"  https://huggingface.co/{repo_id}", file=sys.stderr)
        return 1

    print(f"\nall {len(targets)} repositories are reachable")
    return 0


def download(target: str, models_dir: Path, token: str | None) -> None:
    repo_id, file_name = split_target(target)
    try:
        if file_name:
            print(f"{repo_id} [{file_name}] -> {models_dir}", flush=True)
            models_dir.mkdir(parents=True, exist_ok=True)
            hf_hub_download(
                repo_id=repo_id,
                filename=file_name,
                local_dir=str(models_dir),
                token=token,
            )
            return
        local_dir = target_dir(models_dir, repo_id)
        print(f"{repo_id} -> {local_dir}", flush=True)
        local_dir.mkdir(parents=True, exist_ok=True)
        snapshot_download(repo_id=repo_id, local_dir=str(local_dir), token=token)
    except GatedRepoError as error:
        raise ScriptError(f"{repo_id} is gated, run with --check for details") from error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Hugging Face models into a local directory"
    )
    parser.add_argument(
        "repos",
        nargs="+",
        metavar="REPO",
        help=(
            "repository ids, like Qwen/Qwen3-4B-Instruct-2507; "
            "append ':filename' to fetch a single file instead of the whole repository"
        ),
    )
    parser.add_argument(
        "-d",
        "--models-dir",
        required=True,
        type=Path,
        help="directory to download into, one subdirectory per repository",
    )
    parser.add_argument(
        "-t",
        "--token-file",
        type=Path,
        help="path to a file whose first line is a Hugging Face token",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify access to every repository without downloading anything",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    targets = list(dict.fromkeys(args.repos))

    try:
        token = read_token(args.token_file)
    except ScriptError as error:
        print(error, file=sys.stderr)
        return 1

    if args.check:
        return check_access(targets, token)

    failures = {}
    for target in targets:
        try:
            download(target, args.models_dir, token)
        except Exception as error:
            failures[target] = error

    print()
    for target in targets:
        error = failures.get(target)
        print(f"{target}: {f'{FAILED}: {error}' if error else OK}")

    if failures:
        print(f"\n{len(failures)} of {len(targets)} models failed", file=sys.stderr)
        print("run with --check to see which repositories the token cannot reach", file=sys.stderr)
        return 1

    print(f"\ndownloaded {len(targets)} models into {args.models_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
