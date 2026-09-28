#!/usr/bin/env python3
"""Static integrity checks shared by the macOS and Windows desktop packages."""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()

    frontend = root / "frontend" / "dist"
    windows = root / "desktop" / "runtime" / "windows"
    mac_backend = root / "desktop" / "build" / "backend-macos" / "XunkeFlowBackend"
    required = [
        frontend / "index.html",
        windows / "python.exe",
        windows / "pythonw.exe",
        windows / "app" / "main.py",
        windows / "Lib" / "site-packages" / "fastapi",
        windows / "Lib" / "site-packages" / "sklearn",
        mac_backend / "XunkeFlowBackend",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit("Missing standalone runtime content:\n" + "\n".join(missing))

    forbidden_names = {".env", "docker-compose.yml", "Dockerfile", "node_modules"}
    forbidden = [path for path in windows.rglob("*") if path.name in forbidden_names]
    if forbidden:
        raise SystemExit("Forbidden deployment content found:\n" + "\n".join(map(str, forbidden)))

    print("Frontend production bundle: OK")
    print("Windows embedded CPython: OK")
    print("Windows backend/RAG dependencies: OK")
    print("macOS bundled backend: OK")
    for artifact in sorted((root / "desktop" / "dist").glob("*")):
        if artifact.is_file() and artifact.suffix.lower() in {".dmg", ".exe"}:
            print(f"{artifact.name}\t{artifact.stat().st_size}\t{sha256(artifact)}")


if __name__ == "__main__":
    main()
