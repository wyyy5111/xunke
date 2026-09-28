#!/usr/bin/env python3
"""Validate tracked upload files and the committed public demo snapshot."""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".git", "node_modules", "__pycache__", ".venv", ".pytest_cache", "dist", "tmp", "data", ".playwright-cli", "output"}


def main() -> None:
    tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True)
    paths = [ROOT / name for name in tracked.stdout.decode().split("\0") if name] if tracked.returncode == 0 else [
        path for path in ROOT.rglob("*") if path.is_file() and not (set(path.relative_to(ROOT).parts) & EXCLUDED)
    ]
    errors: list[str] = []
    for path in paths:
        relative = path.relative_to(ROOT)
        if (set(relative.parts) & EXCLUDED or
            (path.name.startswith(".env") and path.name != ".env.example") or
            path.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".key", ".pem", ".p12", ".pfx", ".exe", ".dmg"}):
            errors.append(f"Do not track runtime files or installers: {relative}")
        if path.stat().st_size > 95 * 1024 * 1024:
            errors.append(f"File exceeds repository size policy: {relative}")
    snapshot_path = ROOT / "frontend/public/showcase/snapshot.json"
    text = snapshot_path.read_text(encoding="utf-8")
    snapshot = json.loads(text)
    if snapshot["schema_version"] != 1 or set(snapshot["actors"]) != {"admin", "teacher", "teacher2", "student01"}:
        errors.append("Unexpected showcase snapshot schema or personas")
    for expression in [r'"(?:access_token|hashed_password)"\s*:', r'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.', r'/Users/[^/]+/', r'-----BEGIN .*PRIVATE KEY-----']:
        if re.search(expression, text):
            errors.append("Showcase snapshot contains credential fields or a host path")
    for actor in snapshot["actors"].values():
        for entry in actor["responses"].values():
            if entry["status"] >= 500:
                errors.append("Showcase includes an unhandled server failure")
            if "asset" in entry:
                asset = (snapshot_path.parent / entry["asset"]).resolve()
                if not asset.is_relative_to(snapshot_path.parent) or not asset.is_file():
                    errors.append(f"Missing or unsafe showcase asset: {entry['asset']}")
    for required in ("README.md", "LICENSE-NOTICE.md", ".github/workflows/ci-and-pages.yml", "backend/requirements.txt", "frontend/package-lock.json", "desktop/package-lock.json"):
        if not (ROOT / required).is_file():
            errors.append(f"Missing required project file: {required}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Repository checks passed: {len(paths)} files; 4 public demo personas; all report assets present.")


if __name__ == "__main__":
    main()
