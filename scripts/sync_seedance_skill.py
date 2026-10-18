#!/usr/bin/env python3
"""将 Seedance 2.0 Skill OS 同步到固定 vendor 目录。

此脚本只接受显式提交哈希，不跟踪远端默认分支。同步完成后会写入
VENDOR_VERSION.md，并保留上游 LICENSE。
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path


REPOSITORY = "https://github.com/Emily2040/seedance-2.0"
PINNED_COMMIT = "57d01dc66f93ecb03c2475be5f22dc416d9b701d"
ROOT = Path(__file__).resolve().parents[1]
VENDOR_DIR = ROOT / "vendor" / "seedance-20"
LICENSE_TARGET = ROOT / "third_party" / "seedance-20" / "LICENSE"


def run(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        args,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def verify_commit(source: Path, commit: str) -> None:
    actual = run("git", "rev-parse", "HEAD", cwd=source)
    if actual != commit:
        raise SystemExit(f"提交不匹配：期望 {commit}，实际 {actual}")


def copy_tree(source: Path, target: Path) -> None:
    preserved_version = target / "VENDOR_VERSION.md"
    version_text = preserved_version.read_text(encoding="utf-8") if preserved_version.exists() else ""
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(".git", ".DS_Store"))
    if version_text:
        preserved_version.write_text(version_text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="同步固定版本的 Seedance 2.0 Skill OS")
    parser.add_argument("--commit", required=True, help="必须显式提供完整提交哈希")
    parser.add_argument("--source", type=Path, help="可选：已检出的本地上游目录")
    args = parser.parse_args()

    if args.commit != PINNED_COMMIT:
        raise SystemExit(f"当前升级只允许固定提交 {PINNED_COMMIT}")

    if args.source:
        source = args.source.resolve()
        verify_commit(source, args.commit)
        copy_tree(source, VENDOR_DIR)
    else:
        with tempfile.TemporaryDirectory(prefix="seedance-skill-") as temp_dir:
            source = Path(temp_dir) / "source"
            run("git", "clone", "--filter=blob:none", "--no-checkout", REPOSITORY, str(source))
            run("git", "fetch", "origin", args.commit, "--depth", "1", cwd=source)
            run("git", "checkout", "--detach", args.commit, cwd=source)
            verify_commit(source, args.commit)
            copy_tree(source, VENDOR_DIR)

    LICENSE_TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(VENDOR_DIR / "LICENSE", LICENSE_TARGET)
    print(f"已同步 Seedance Skill OS：{args.commit}")
    print(f"目录：{VENDOR_DIR}")


if __name__ == "__main__":
    main()
