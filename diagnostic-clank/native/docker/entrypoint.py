"""Container entrypoint for a persistent Diagnostic Clank web service.

Distinct from native/macos/launcher.py: no browser auto-open, no runtime
lifecycle tied to a Finder-launched GUI process, binds host/port from
environment (deployment configuration, never hard-coded) instead of an
ephemeral OS-assigned loopback port. Never assumes a specific NAS/host
identity -- host and port are supplied by whoever runs the container.

DIAGNOSTIC_CLANK_BIND_HOST defaults to 127.0.0.1 -- deliberately loopback
(fails safe/unreachable, not fails open) unless the deployment explicitly
opts into a wider bind via environment, matching the portability law that
NAS-specific network exposure is deployment configuration, not something
this module decides on its own.
"""
from __future__ import annotations

import os
import signal
import sys
import threading


def main() -> None:
    for name in tuple(os.environ):
        if any(token in name.upper() for token in ("DISCORD", "WEBHOOK", "SECRET", "TOKEN", "API_KEY")):
            os.environ.pop(name, None)

    from diagnostic_clank.dashboard import serve
    from diagnostic_clank.paths import resolve_state_paths

    host = os.environ.get("DIAGNOSTIC_CLANK_BIND_HOST", "127.0.0.1")
    port = int(os.environ.get("DIAGNOSTIC_CLANK_PORT", "8420"))

    paths = resolve_state_paths()
    server, store = serve(paths=paths, host=host, port=port)

    def stop(_signum: int, _frame: object) -> None:
        # server.shutdown() blocks until serve_forever()'s loop notices the
        # stop flag -- must be called from a different thread than the one
        # running serve_forever(), or this deadlocks (shutdown() waiting on
        # a loop that can never run because it's the same blocked thread).
        server.shutdown()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    print(f"diagnostic-clank listening on {host}:{port}", file=sys.stderr, flush=True)
    thread = threading.Thread(target=server.serve_forever, name="diagnostic-clank-web", daemon=False)
    try:
        thread.start()
        thread.join()
    finally:
        server.server_close()
        store.close()


if __name__ == "__main__":
    main()
