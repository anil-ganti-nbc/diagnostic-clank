"""Shared Diagnostic Clank launcher preflight — platform-agnostic contract."""
from __future__ import annotations
import os, sys
from dataclasses import dataclass, field
from pathlib import Path

CONTRACT_VERSION = "1.0.0"

@dataclass
class LauncherConfig:
    home: Path
    db_path: Path
    log_dir: Path
    mode: str = "inbox"
    python: str = sys.executable

@dataclass
class PreflightResult:
    ok: bool
    checks: list[tuple[str, bool, str]] = field(default_factory=list)
    config: LauncherConfig | None = None
    def add(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append((name, passed, detail))
        if not passed:
            self.ok = False

def resolve_home(explicit: str | None = None) -> Path:
    if explicit: return Path(explicit).resolve()
    env = os.environ.get("DIAGNOSTIC_CLANK_HOME")
    if env: return Path(env).resolve()
    return Path(__file__).resolve().parents[2]

def load_config(home: Path | None = None) -> LauncherConfig:
    home = home or resolve_home()
    db = os.environ.get("DIAGNOSTIC_DB_PATH", "data/motherclank_knowledge.db")
    log_dir = os.environ.get("DIAGNOSTIC_LOG_DIR", "logs")
    mode = os.environ.get("DIAGNOSTIC_MODE", "inbox")
    py = os.environ.get("DIAGNOSTIC_PYTHON") or sys.executable
    db_path = Path(db) if Path(db).is_absolute() else home / db
    log_path = Path(log_dir) if Path(log_dir).is_absolute() else home / log_dir
    return LauncherConfig(home=home, db_path=db_path, log_dir=log_path, mode=mode, python=py)

def run_preflight(cfg: LauncherConfig | None = None) -> PreflightResult:
    cfg = cfg or load_config()
    result = PreflightResult(ok=True, config=cfg)
    result.add("contract_version", True, CONTRACT_VERSION)
    result.add("home_exists", cfg.home.is_dir(), str(cfg.home))
    result.add("python_executable", Path(cfg.python).exists() or cfg.python == sys.executable, cfg.python)
    try:
        import clank_runtime  # noqa: F401
        result.add("clank_runtime_importable", True, "ok")
    except ImportError as e:
        result.add("clank_runtime_importable", False, str(e))
    try:
        from clank_runtime.knowledge.inbox import AgentOutputInbox  # noqa: F401
        from clank_runtime.registry.core import ClankRegistry  # noqa: F401
        from clank_runtime.diagnostic.engine import diagnose  # noqa: F401
        result.add("diagnostic_modules", True, "ok")
    except ImportError as e:
        result.add("diagnostic_modules", False, str(e))
    try:
        cfg.db_path.parent.mkdir(parents=True, exist_ok=True)
        cfg.log_dir.mkdir(parents=True, exist_ok=True)
        result.add("data_dirs_writable", True, f"db={cfg.db_path.parent} logs={cfg.log_dir}")
    except OSError as e:
        result.add("data_dirs_writable", False, str(e))
    if result.ok:
        try:
            from clank_runtime.knowledge.inbox import AgentOutputInbox
            from clank_runtime.registry.core import ClankRegistry
            box = AgentOutputInbox(cfg.db_path, ClankRegistry())
            ver = box.schema_version(); box.close()
            result.add("db_schema", True, f"schema_version={ver}")
        except Exception as e:
            result.add("db_schema", False, str(e))
    result.add("mode_supported", cfg.mode in {"inbox", "status", "preflight"}, cfg.mode)
    return result

def print_status(result: PreflightResult) -> None:
    print(f"Diagnostic Clank launcher contract {CONTRACT_VERSION}")
    print(f"overall: {'OK' if result.ok else 'FAIL'}")
    for name, passed, detail in result.checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}: {detail}")

def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    mode = os.environ.get("DIAGNOSTIC_MODE", "preflight")
    if argv: mode = argv[0]
    cfg = load_config(); cfg.mode = mode
    result = run_preflight(cfg); print_status(result)
    if mode in {"preflight", "status"}: return 0 if result.ok else 1
    if mode == "inbox":
        if not result.ok: return 1
        from clank_desktop.inbox.agent_inbox_gui import run_inbox_gui
        run_inbox_gui(cfg.db_path); return 0
    print(f"unknown mode: {mode}", file=sys.stderr); return 2

if __name__ == "__main__":
    raise SystemExit(main())
