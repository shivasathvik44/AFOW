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

    @app.get("/api/system-info")
    def api_system_info():
        import subprocess
        import sys
        from pathlib import Path

        platform_name = "windows" if sys.platform == "win32" else ("darwin" if sys.platform == "darwin" else "linux")
        home = Path.home()

        downloads = home / "Downloads"
        documents = home / "Documents"
        desktop = home / "Desktop"
        pictures = home / "Pictures"

        if platform_name == "linux":
            import shutil
            if shutil.which("xdg-user-dir"):
                dirs = [("DOWNLOAD", "downloads"), ("DOCUMENTS", "documents"), ("DESKTOP", "desktop"), ("PICTURES", "pictures")]
                for dir_type, attr in dirs:
                    try:
                        out = subprocess.check_output(["xdg-user-dir", dir_type], text=True, stderr=subprocess.DEVNULL).strip()
                        if out and Path(out).is_dir():
                            if attr == "downloads": downloads = Path(out)
                            elif attr == "documents": documents = Path(out)
                            elif attr == "desktop": desktop = Path(out)
                            elif attr == "pictures": pictures = Path(out)
                    except (subprocess.SubprocessError, OSError):
                        pass

        from afow.config import get_default_directory
        default_dir = get_default_directory()
        default_str = str(default_dir)

        return jsonify(
            os=platform_name,
            placeholder=default_str,
            default_path=default_str,
            common_folders=common,
        )

    @app.post("/api/preview")
    def api_preview():
        data = request.get_json(silent=True) or {}
        policy = data.get("dedup_policy") or "rename"
        use_xdg = bool(data.get("use_xdg_folders"))
        return _run(lambda p: organize(p, dry_run=True, dedup_policy=policy, use_xdg_folders=use_xdg), action_name="preview")

    @app.post("/api/organize")
    def api_organize():
        data = request.get_json(silent=True) or {}
        policy = data.get("dedup_policy") or "rename"
        use_xdg = bool(data.get("use_xdg_folders"))
        return _run(lambda p: organize(p, dry_run=False, dedup_policy=policy, use_xdg_folders=use_xdg), action_name="organize")

    @app.post("/api/undo")
    def api_undo():
        return _run(undo, action_name="undo")

    return app


def _run(action, action_name="action"):
    import sys
    data = request.get_json(silent=True) or {}
    path = (data.get("path") or "").strip()
    if (path.startswith('"') and path.endswith('"')) or (path.startswith("'") and path.endswith("'")):
        path = path[1:-1].strip()

    # Unescape shell/terminal-escaped spaces on Linux/macOS
    if sys.platform != "win32" and "\\ " in path:
        path = path.replace("\\ ", " ")

    if not path:
        return jsonify(error="path is required"), 400

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
