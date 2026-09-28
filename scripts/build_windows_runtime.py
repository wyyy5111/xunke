#!/usr/bin/env python3
"""Assemble a self-contained Windows x64 Python runtime on macOS.

The runtime uses the official CPython embeddable distribution and only binary
Windows wheels.  It includes the backend source and seeded course assets, so
the target machine does not need Python, Node.js, Java or Docker.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


PYTHON_VERSION = "3.12.10"
PYTHON_OFFICIAL_URL = (
    f"https://www.python.org/ftp/python/{PYTHON_VERSION}/"
    f"python-{PYTHON_VERSION}-embed-amd64.zip"
)
PYTHON_DOWNLOAD_URL = (
    f"https://repo.huaweicloud.com/python/{PYTHON_VERSION}/"
    f"python-{PYTHON_VERSION}-embed-amd64.zip"
)


def run(command: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def copy_tree_clean(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", "tests"),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--force-download", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    runtime = root / "desktop" / "runtime" / "windows"
    cache = root / "desktop" / ".cache"
    archive = cache / f"python-{PYTHON_VERSION}-embed-amd64.zip"
    requirements = root / "desktop" / "requirements-runtime.txt"

    cache.mkdir(parents=True, exist_ok=True)
    if args.force_download and archive.exists():
        archive.unlink()
    if not archive.exists():
        print(f"Downloading CPython mirror of the official runtime: {PYTHON_DOWNLOAD_URL}")
        run(["curl", "--fail", "--location", "--retry", "3", "--output", str(archive), PYTHON_DOWNLOAD_URL])
    if archive.stat().st_size < 8_000_000:
        raise SystemExit("Downloaded CPython archive is unexpectedly small")

    shutil.rmtree(runtime, ignore_errors=True)
    runtime.mkdir(parents=True)
    with zipfile.ZipFile(archive) as package:
        package.extractall(runtime)

    pth_files = list(runtime.glob("python*._pth"))
    if len(pth_files) != 1:
        raise SystemExit("Expected exactly one embedded-Python _pth file")
    pth_files[0].write_text(
        "python312.zip\n.\nLib/site-packages\nimport site\n",
        encoding="utf-8",
    )

    site_packages = runtime / "Lib" / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)
    run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--index-url",
            "https://repo.huaweicloud.com/repository/pypi/simple",
            "--no-compile",
            "--upgrade",
            "--target",
            str(site_packages),
            "--platform",
            "win_amd64",
            "--implementation",
            "cp",
            "--python-version",
            "3.12",
            "--abi",
            "cp312",
            "--only-binary=:all:",
            "-r",
            str(requirements),
        ]
    )

    copy_tree_clean(root / "backend" / "app", runtime / "app")
    copy_tree_clean(root / "demo_data", runtime / "demo_data")
    shutil.copy2(root / "desktop" / "backend_server.py", runtime / "backend_server.py")
    shutil.copy2(requirements, runtime / "requirements-runtime.txt")
    (runtime / "PYTHON_RUNTIME_LICENSE.txt").write_text(
        "CPython runtime from python.org. Python Software Foundation License.\n"
        f"Version: {PYTHON_VERSION}\nOfficial source: {PYTHON_OFFICIAL_URL}\n"
        f"Download mirror: {PYTHON_DOWNLOAD_URL}\n"
        f"Archive SHA256: {sha256(archive)}\n",
        encoding="utf-8",
    )

    required = [
        runtime / "python.exe",
        runtime / "pythonw.exe",
        runtime / "python312.dll",
        runtime / "backend_server.py",
        runtime / "app" / "main.py",
        runtime / "demo_data" / "finance_governance" / "lecture.md",
        site_packages / "fastapi",
        site_packages / "sklearn",
        site_packages / "numpy",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit("Windows runtime is incomplete:\n" + "\n".join(missing))

    total = sum(path.stat().st_size for path in runtime.rglob("*") if path.is_file())
    manifest = runtime / "RUNTIME_MANIFEST.txt"
    manifest.write_text(
        "\n".join(
            [
                "XunkeFlow Windows x64 embedded runtime",
                f"Python: {PYTHON_VERSION}",
                f"Files: {sum(1 for path in runtime.rglob('*') if path.is_file())}",
                f"Bytes: {total}",
                "Runtime requirements: none (Windows 10/11 x64)",
                "Includes: CPython, backend, SQLite, RAG/Agent dependencies, demo course assets",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Windows runtime ready: {runtime}")
    print(f"Files: {sum(1 for path in runtime.rglob('*') if path.is_file())}")
    print(f"Size: {total / 1024 / 1024:.1f} MiB")


if __name__ == "__main__":
    main()
