"""Finder-launchable macOS field-test entrypoint for Diagnostic Clank v0.1.

Isolated Application Support state, loopback-only binding, readiness wait,
default-browser open, clean shutdown with runtime-marker cleanup. No
production authority: this is a pure local archivist, nothing here can
reach another Clank's database, secrets, or delivery channel.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

APP_NAME = "Diagnostic Clank"


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parents[1] / "Resources"
    return Path(__file__).resolve().parents[2]


def wait_for_ready(port: int, timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=0.5) as response:
                if response.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(0.1)
    return False


def main() -> None:
    # Never inherit any production-shaped secret by accident, even though
    # this app has no code path that would use one -- belt and suspenders,
    # matching every other Clank field-test launcher in this fleet.
    for name in tuple(os.environ):
        if any(token in name.upper() for token in ("DISCORD", "WEBHOOK", "SECRET", "TOKEN", "API_KEY")):
            os.environ.pop(name, None)

    if getattr(sys, "frozen", False):
        sys.path.insert(0, str(resource_root()))

    from diagnostic_clank.paths import resolve_nas_endpoint

    nas_url = resolve_nas_endpoint()
    if nas_url:
        # A canonical NAS-hosted instance is configured for this machine --
        # this app becomes a thin browser launcher only, never starting a
        # second, independently-writable local server/DB. Configured via
        # DIAGNOSTIC_CLANK_NAS_URL or a local nas-endpoint.txt file, never a
        # hard-coded host in source (see paths.resolve_nas_endpoint).
        if os.environ.get("DIAGNOSTIC_CLANK_NO_BROWSER") != "1":
            subprocess.Popen(["open", nas_url])
        return

    from diagnostic_clank.dashboard import serve
    from diagnostic_clank.paths import resolve_state_paths

    paths = resolve_state_paths()
    server, store = serve(paths=paths, port=0)
    port = server.socket.getsockname()[1]

    def stop(_signum: int, _frame: object) -> None:
        server.shutdown()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    marker = paths.runtime_marker
    thread = threading.Thread(target=server.serve_forever, name="diagnostic-clank-loopback", daemon=False)
    try:
        thread.start()
        if wait_for_ready(port):
            marker.write_text(json.dumps({"pid": os.getpid(), "port": port}), encoding="utf-8")
            if os.environ.get("DIAGNOSTIC_CLANK_NO_BROWSER") != "1":
                subprocess.Popen(["open", f"http://127.0.0.1:{port}/"])
        thread.join()
    finally:
        server.server_close()
        store.close()
        marker.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
