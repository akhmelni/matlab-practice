"""The local web app: `uv run practice` (or start.bat / start.sh).

    uv run practice            start on http://127.0.0.1:8770 and open the browser
    uv run practice --no-open  start without opening the browser
"""

from __future__ import annotations

import json
import re
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import config, engine, grading, problems, review, store

HOST = "127.0.0.1"
STATIC_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8", ".json": "application/json", ".svg": "image/svg+xml",
                ".png": "image/png", ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf",
                ".md": "text/plain; charset=utf-8", ".map": "application/json"}


def problem_summary(p: problems.Problem) -> dict:
    return {"id": p.id, "set": p.set, "number": p.number, "title": p.title, "kind": p.kind,
            "status": store.status(p.id), "fails": store.fails(p.id), "example": p.example}


def problem_detail(p: problems.Problem) -> dict:
    context = []
    for cid in p.context:
        c = problems.find(cid)
        if c:
            context.append({"id": c.id, "title": c.title, "statement_md": c.statement})
    return {
        "id": p.id, "set": p.set, "number": p.number, "title": p.title, "kind": p.kind,
        "statement_md": p.statement, "submit_md": p.submit_text,
        "source_url": f"/api/problems/{p.id}/source" if p.source_path else None,
        "context": context, "file": p.file, "code": p.student_code(), "scratch": p.student_scratch(),
        "fails": store.fails(p.id), "hint_threshold": config.HINT_THRESHOLD,
        "submissions": [store.summary(s) for s in store.all_for(p.id)],
    }


def status() -> dict:
    o = engine.find_octave()
    return {"octave": {"found": o.found, "path": o.cli, "version": o.version, "graphics": bool(o.gui)},
            "claude": {"found": review.find_claude() is not None}, "work_dir": str(config.work_dir())}


class Handler(BaseHTTPRequestHandler):
    server_version = "MatlabPractice"

    def log_message(self, fmt, *args):
        pass

    # ---- helpers ----

    def send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def json(self, data, code: int = 200) -> None:
        self.send(code, json.dumps(data).encode("utf-8"), "application/json")

    def error(self, code: int, message: str) -> None:
        self.json({"error": message}, code)

    def body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > 2_000_000:
            raise ValueError("request too large")
        data = json.loads(self.rfile.read(n) or b"{}")
        if not isinstance(data, dict):
            raise ValueError("expected a JSON object")
        return data

    def parts(self) -> list[str]:
        return [unquote(p) for p in urlparse(self.path).path.strip("/").split("/") if p]

    def problem_or_404(self, pid: str) -> problems.Problem | None:
        p = problems.find(pid)
        if p is None:
            self.error(404, "no such problem")
        return p

    # ---- GET ----

    def do_GET(self) -> None:
        try:
            self._get()
        except Exception as e:  # keep the server alive
            self.error(500, f"{type(e).__name__}: {e}")

    def _get(self) -> None:
        parts = self.parts()
        if not parts or parts[0] != "api":
            return self.static(parts)
        if parts == ["api", "status"]:
            return self.json(status())
        if parts == ["api", "problems"]:
            return self.json([problem_summary(p) for p in problems.all_problems()])
        if len(parts) == 4 and parts[:2] == ["api", "figures"]:
            path = store.figure_path(parts[2], parts[3])
            return self.send(200, path.read_bytes(), "image/png") if path else self.error(404, "no such figure")
        if len(parts) >= 3 and parts[1] == "problems":
            p = self.problem_or_404(parts[2])
            if p is None:
                return None
            if len(parts) == 3:
                return self.json(problem_detail(p))
            if parts[3:] == ["source"]:
                src = p.source_path
                if not src:
                    return self.error(404, "no source image")
                return self.send(200, src.read_bytes(),
                                 problems.IMAGE_TYPES.get(src.suffix.lower(), "application/octet-stream"))
            if len(parts) == 5 and parts[3] == "submissions":
                sub = store.load(p.id, parts[4])
                return self.json(sub) if sub else self.error(404, "no such submission")
        self.error(404, "not found")

    def static(self, parts: list[str]) -> None:
        rel = Path(*parts) if parts else Path("index.html")
        root = config.WEB_DIR.resolve()
        path = (root / rel).resolve()
        if root not in path.parents and path != root or not path.is_file():
            return self.error(404, "not found")
        self.send(200, path.read_bytes(), STATIC_TYPES.get(path.suffix.lower(), "application/octet-stream"))

    # ---- POST ----

    def do_POST(self) -> None:
        try:
            self._post()
        except ValueError as e:
            self.error(400, str(e))
        except RuntimeError as e:
            self.error(503, str(e))
        except Exception as e:
            self.error(500, f"{type(e).__name__}: {e}")

    def _post(self) -> None:
        parts = self.parts()
        if len(parts) != 4 or parts[:2] != ["api", "problems"]:
            return self.error(404, "not found")
        p = self.problem_or_404(parts[2])
        if p is None:
            return None
        action = parts[3]
        data = self.body()
        code = data.get("code")
        if not isinstance(code, str):
            return self.error(400, "missing code")
        scratch = data.get("scratch") if isinstance(data.get("scratch"), str) else None
        if action == "check":
            filename = data.get("file") if data.get("file") in (p.file, "scratch.m") else None
            return self.json({"issues": grading.lint(p, code, filename)})
        if action == "save":
            p.save_student(code, scratch)
            return self.json({"ok": True})
        if action == "run":
            return self.json(grading.run(p, code, scratch))
        if action == "submit":
            return self.json(grading.submit(p, code, scratch))
        self.error(404, "not found")


def main() -> None:
    port = int(config.setting("PORT", "8770"))
    config.work_dir().mkdir(parents=True, exist_ok=True)
    try:
        server = ThreadingHTTPServer((HOST, port), Handler)
    except OSError:
        print(f"Port {port} is busy. The app may already be running: open http://{HOST}:{port}")
        sys.exit(1)
    url = f"http://{HOST}:{port}"
    print(f"MATLAB Practice is running at {url}  (press Ctrl+C to stop)")
    o = engine.find_octave()
    print(f"Octave: {o.cli or 'NOT FOUND - see INSTALL.md'}")
    if review.find_claude() is None:
        print("Claude Code: not found - submissions won't be reviewed and hints are off")
    if "--no-open" not in sys.argv:
        threading.Timer(0.6, webbrowser.open, [url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
