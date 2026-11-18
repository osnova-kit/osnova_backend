from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

from scripts.strip import TEST_MARK

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = "https://github.com/osnova-kit/osnova_backend.git"
VERSION_FILE = ".osnova-version"
OURS = ("CHANGELOG.md", "README.md")

MODULE_NAME = re.compile(r'ModuleSpec\(\s*name="(\w+)"')
VERSION_LINE = re.compile(r'^\s*"?version"?\s*[:=]', re.I)
CONFLICT = re.compile(r"<<<<<<< [^\n]*\n(.*?)=======\n(.*?)>>>>>>> [^\n]*\n", re.S)


class UpgradeError(Exception):
    pass


def git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if check and result.returncode:
        raise UpgradeError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout


def release_ref(version: str) -> str:
    return f"refs/osnova/{version}"


def files_at(root: Path, rev: str) -> set[str]:
    return set(git(root, "ls-tree", "-r", "--name-only", rev).split())


def modules_at(root: Path, rev: str) -> set[str]:
    text = git(root, "show", f"{rev}:app/core/modules.py", check=False)
    return set(MODULE_NAME.findall(text))


def removed_dirs(base: set[str], head: set[str]) -> set[str]:
    """Folders that held files in the base release and hold none in the project."""
    dirs = {str(parent) for path in base for parent in PurePosixPath(path).parents}
    dirs.discard(".")
    kept = {str(parent) for path in head for parent in PurePosixPath(path).parents}
    return dirs - kept


def keep_our_versions(text: str) -> str:
    """Resolves the conflicts where both sides only set a version, in favour of ours."""

    def resolve(match: re.Match) -> str:
        ours, theirs = match[1].splitlines(), match[2].splitlines()
        if ours and theirs and all(VERSION_LINE.match(line) for line in ours + theirs):
            return match[1]
        return match[0]

    return CONFLICT.sub(resolve, text)


def unmerged(root: Path) -> dict[str, str]:
    status = git(root, "status", "--porcelain", "--untracked-files=no")
    codes = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
    return {line[3:]: line[:2] for line in status.splitlines() if line[:2] in codes}


def upgrade(root: Path, version: str, upstream: str = UPSTREAM) -> tuple[str, list[str]]:
    """Merges `version` of the template into the project. Returns the commit to go back
    to and the files left in conflict (the merge is then not committed)."""
    if git(root, "status", "--porcelain"):
        raise UpgradeError("The git working tree has changes: commit them first.")
    version_file = root / VERSION_FILE
    if not version_file.exists():
        raise UpgradeError(
            f"No {VERSION_FILE}: write the release the project was made from into it, e.g. v1.0.0"
        )
    base = version_file.read_text().strip()
    start = git(root, "rev-parse", "HEAD").strip()
    if base == version:
        raise UpgradeError(f"The project is on {version} already.")
    git(
        root,
        "fetch",
        "--no-tags",
        upstream,
        *(f"+refs/tags/{v}:{release_ref(v)}" for v in (base, version)),
    )

    head_files = files_at(root, "HEAD")
    gone_dirs = removed_dirs(files_at(root, release_ref(base)), head_files)
    gone_modules = modules_at(root, release_ref(base)) - modules_at(root, "HEAD")

    if not git(root, "merge-base", "HEAD", release_ref(version), check=False).strip():
        git(
            root,
            "merge",
            "-s",
            "ours",
            "--allow-unrelated-histories",
            "-m",
            f"chore: Osnova {base} as the base for upgrades",
            release_ref(base),
        )
    git(root, "merge", "--no-ff", "--no-commit", release_ref(version), check=False)

    for path, code in unmerged(root).items():
        if code == "DU":
            git(root, "rm", "-q", "--", path)
        elif path in OURS:
            git(root, "checkout", "--ours", "--", path)
            git(root, "add", "--", path)
        elif code == "UU":
            file = root / path
            file.write_text(keep_our_versions(file.read_text()))
            if not CONFLICT.search(file.read_text()):
                git(root, "add", "--", path)

    for path in sorted(set(git(root, "ls-files").split()) - head_files):
        mark = TEST_MARK.search((root / path).read_text()) if path.startswith("tests/") else None
        marked = set(re.findall(r'"(\w+)"', mark["names"])) if mark else set()
        inside = any(path.startswith(f"{folder}/") for folder in gone_dirs)
        if inside or marked & gone_modules:
            git(root, "rm", "-q", "-f", "--", path)

    left = sorted(unmerged(root))
    if left:
        return start, left
    version_file.write_text(f"{version}\n")
    git(root, "add", VERSION_FILE)
    git(root, "commit", "-q", "--no-edit", "-m", f"chore: upgrade Osnova to {version}")
    return start, []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge a new release of the template.")
    parser.add_argument("version", help="The release to upgrade to, e.g. v1.1.0")
    parser.add_argument("--upstream", default=UPSTREAM, help="Git address of the template")
    args = parser.parse_args(argv)
    try:
        start, left = upgrade(ROOT, args.version, args.upstream)
    except UpgradeError as error:
        print(error)
        return 1
    if left:
        print("Both the project and the template changed these files:")
        for path in left:
            print(f"  {path}")
        print("\nResolve the conflicts, then: git add <files> && git commit")
        print(f"To give up: git merge --abort && git reset --hard {start}")
        return 1
    print(f"Upgraded to {args.version}. Check with make lint and make test.")
    print(f"To undo: git reset --hard {start}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
