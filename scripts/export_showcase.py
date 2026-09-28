#!/usr/bin/env python3
"""Export the existing demo API into a read-only GitHub Pages snapshot.

Always seeds a disposable database. Never reads the user's .env or database.
Run with the backend dependencies installed: python scripts/export_showcase.py
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "frontend" / "public" / "showcase"
ACCOUNTS = ("admin", "teacher", "teacher2", "student01")


def key(path: str, params: dict | None = None) -> str:
    query = urlencode(sorted((params or {}).items()))
    return path + ("?" + query if query else "")


def export() -> None:
    with tempfile.TemporaryDirectory(prefix="xunkeflow-showcase-") as temporary:
        work = Path(temporary)
        os.environ.update({
            "XUNKEFLOW_ENV_FILE": str(work / "no-user-env"),
            "XUNKEFLOW_ASSET_DIR": str(ROOT),
            "XUNKEFLOW_DATA_DIR": str(work),
            "XUNKEFLOW_FRONTEND_DIR": "",
            "DATABASE_URL": f"sqlite:///{work / 'demo.db'}",
            "UPLOAD_DIR": str(work / "uploads"),
            "CHUNK_DIR": str(work / "chunks"),
            "APP_ENV": "demo", "APP_DEBUG": "false",
            "AUTO_SEED_DEMO": "true", "LLM_PROVIDER": "mock",
            "LLM_MODEL": "deepseek-v4-flash", "DEEPSEEK_API_KEY": "",
            "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
            "JWT_SECRET": secrets.token_urlsafe(48),
            "TRUSTED_HOSTS": "testserver,localhost,127.0.0.1",
        })
        sys.path.insert(0, str(ROOT / "backend"))
        from fastapi.testclient import TestClient
        from app.main import app

        assets: dict[str, bytes] = {}
        snapshot: dict = {
            "schema_version": 1,
            "source": "Original demo seed and FastAPI responses; no live model calls",
            "public": {}, "actors": {},
        }

        def capture(client, target, path, params=None, headers=None):
            response = client.get("/api" + path, params=params, headers=headers)
            if response.status_code >= 500:
                raise RuntimeError(f"Export failed: {path} HTTP {response.status_code}")
            content_type = response.headers.get("content-type", "application/json")
            entry = {"status": response.status_code, "content_type": content_type}
            if "json" in content_type:
                entry["data"] = response.json()
            else:
                suffix = ".pdf" if "pdf" in content_type else ".md" if path.endswith(".md") else ".bin"
                filename = hashlib.sha256(response.content).hexdigest()[:24] + suffix
                assets[filename] = response.content
                entry["asset"] = "files/" + filename
            target[key(path, params)] = entry
            return entry.get("data", {}).get("data", []) if isinstance(entry.get("data"), dict) else []

        with TestClient(app) as client:
            for path in ("/health", "/system/info"):
                capture(client, snapshot["public"], path)
            for username in ACCOUNTS:
                response = client.post("/api/auth/login", json={"username": username, "password": "123456"})
                response.raise_for_status()
                login = response.json()["data"]
                headers = {"Authorization": "Bearer " + login["access_token"]}
                # Do not persist JWTs or password hashes. These are public demo personas.
                actor = {"user": login["user"], "responses": {}}
                snapshot["actors"][username] = actor
                routes = actor["responses"]
                for path in ("/auth/me", "/auth/me/settings", "/courses/mine/enrolled",
                             "/admin/users", "/admin/configs", "/admin/llm_logs",
                             "/admin/dashboard", "/admin/data-snapshot"):
                    capture(client, routes, path, headers=headers)
                courses = capture(client, routes, "/courses", headers=headers)
                capture(client, routes, "/courses", {"include_archived": "true"}, headers)
                runs = list(capture(client, routes, "/agents/runs", headers=headers))
                capture(client, routes, "/agents/command_center", headers=headers)
                for course in courses:
                    cid = course["id"]
                    for path in (
                        f"/courses/{cid}/chapters", f"/knowledge/course/{cid}",
                        f"/knowledge/graph/{cid}", f"/profiles/{cid}",
                        f"/profiles/{cid}/mastery", f"/profiles/{cid}/path",
                        f"/profiles/{cid}/records", f"/wrong/{cid}",
                        f"/tests/compare/{cid}", f"/stats/teacher/{cid}",
                        f"/stats/experiment/{cid}",
                    ):
                        capture(client, routes, path, headers=headers)
                    files = capture(client, routes, f"/files/course/{cid}", headers=headers)
                    for file in files:
                        capture(client, routes, f"/files/{file['id']}/parse_status", headers=headers)
                    for path in ("/questions", "/review/pending", "/agents/command_center"):
                        capture(client, routes, path, {"course_id": cid}, headers)
                    runs += capture(client, routes, "/agents/runs", {"course_id": cid}, headers)
                    resources = capture(client, routes, "/resources", {"course_id": cid}, headers)
                    for resource in resources:
                        capture(client, routes, f"/resources/{resource['id']}", headers=headers)
                    if actor["user"]["role"] == "student":
                        for test_type in ("practice", "pre", "post"):
                            capture(client, routes, f"/tests/pre/{cid}", {"count": 10, "test_type": test_type}, headers)
                    report_type = "student" if actor["user"]["role"] == "student" else "class"
                    for extension in ("md", "pdf"):
                        capture(client, routes, f"/reports/{report_type}/{cid}.{extension}", headers=headers)
                for run in {run["id"]: run for run in runs}.values():
                    capture(client, routes, f"/agents/runs/{run['id']}", headers=headers)
                    capture(client, routes, f"/agents/trace/{run['trace_id']}", headers=headers)

        payload = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
        # Runtime metadata may contain an ephemeral path, never publish host paths.
        payload = payload.replace(str(work), "[demo-data]").replace(str(ROOT), "[project]")
        for forbidden in ('"access_token":', '"hashed_password":', os.environ["JWT_SECRET"]):
            if forbidden in payload:
                raise RuntimeError("Snapshot contains a credential field")
        OUTPUT.mkdir(parents=True, exist_ok=True)
        files_dir = OUTPUT / "files"
        files_dir.mkdir(exist_ok=True)
        for old in files_dir.iterdir():
            if old.is_file() and old.name not in assets:
                old.unlink()
        for filename, content in assets.items():
            (files_dir / filename).write_bytes(content)
        (OUTPUT / "snapshot.json").write_text(payload + "\n", encoding="utf-8")
        print(json.dumps({"actors": len(snapshot["actors"]), "responses": sum(
            len(actor["responses"]) for actor in snapshot["actors"].values()),
            "files": len(assets), "snapshot_bytes": len(payload.encode())}, ensure_ascii=False))


if __name__ == "__main__":
    export()
