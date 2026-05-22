"""Flask web UI for afow.  Localhost only."""

from __future__ import annotations

import time
from datetime import datetime
from flask import Flask, jsonify, render_template, request

from afow.organizer import organize
from afow.undo import undo


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/api/preview")
    def api_preview():
        data = request.get_json(silent=True) or {}
        policy = data.get("dedup_policy") or "rename"
        return _run(lambda p: organize(p, dry_run=True, dedup_policy=policy), action_name="preview")

    @app.post("/api/organize")
    def api_organize():
        data = request.get_json(silent=True) or {}
        policy = data.get("dedup_policy") or "rename"
        return _run(lambda p: organize(p, dry_run=False, dedup_policy=policy), action_name="organize")

    @app.post("/api/undo")
    def api_undo():
        return _run(undo, action_name="undo")

    return app


def _run(action, action_name="action"):
    data = request.get_json(silent=True) or {}
    path = (data.get("path") or "").strip()
    if path.startswith('"') and path.endswith('"'):
        path = path[1:-1].strip()
    if path.startswith("'") and path.endswith("'"):
        path = path[1:-1].strip()

    if not path:
        return jsonify(error="path is required"), 400

    import sys
    from afow.history import get_db_path
    
    log_file = get_db_path().parent / "server.log"
    
    def log_msg(msg: str) -> None:
        print(msg, file=sys.stderr, flush=True)
        try:
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(msg + "\n")
        except OSError:
            pass

    log_msg(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] API Request: {action_name.upper()} on path: {path}")
    start_time = time.perf_counter()
    try:
        summary = action(path)
        elapsed = (time.perf_counter() - start_time) * 1000
        log_msg(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] API Success: {action_name.upper()} completed in {elapsed:.1f}ms (moved: {summary.moved}, skipped: {summary.skipped})")
    except NotADirectoryError as e:
        log_msg(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] API Error: Not a directory: {path}")
        return jsonify(error=str(e)), 400
    except FileNotFoundError as e:
        log_msg(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] API Error: File not found: {path}")
        return jsonify(error=str(e)), 404
    except Exception as e:
        log_msg(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] API Error: Unexpected exception: {e}")
        return jsonify(error=str(e)), 500
    return jsonify(summary.to_dict())


def run_server(port: int = 5000) -> None:
    app = create_app()
    print(f"afow web UI on http://127.0.0.1:{port}  (Ctrl+C to stop)")
    app.run(host="127.0.0.1", port=port, debug=False)
