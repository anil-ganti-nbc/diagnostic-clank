"""Architecture guardrail tests for Stage 0 / 0.5.

Designed to fail if later agents introduce forbidden dependencies,
production logic in placeholders, or architecture-violating imports.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]  # unified-clank-stage0
FLEET = ROOT / "clank-fleet"
RUNTIME = ROOT / "clank-runtime"
DESKTOP = ROOT / "clank-desktop"

FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        "sqlite3",
        "sqlalchemy",
        "playwright",
        "selenium",
        "scrapy",
        "docker",  # Docker SDK — socket control is forbidden
        "paramiko",  # SSH — no direct SSH from Stage 0.5
    }
)

FORBIDDEN_DEP_SUBSTRINGS = frozenset(
    {
        "sqlite",
        "sqlalchemy",
        "playwright",
        "selenium",
        "scrapy",
        "psycopg",
        "asyncpg",
        "docker",
    }
)

EXISTING_CLANK_TOKENS = frozenset(
    {
        "oem_radar",
        "oem-radar",
        "free_game_tracker",
        "free-game-tracker",
        "watch_clank",
        "watch-clank",
        "smartphone_clank",
        "smartphone-clank",
        "chinese_tech_wire",
        "chinese-tech-wire",
        "semi_intel",
        "semi-intel",
    }
)

PLACEHOLDER_MARKERS = (
    "STAGE 0.5 BOUNDARY",
    "Stage 0.5",
    "Stage 0",
    "not implemented",
    "Not implemented",
    "interface only",
    "placeholder",
)


def _iter_py_files(base: Path) -> list[Path]:
    if not base.exists():
        return []
    return [
        p
        for p in base.rglob("*.py")
        if ".venv" not in p.parts
        and "egg-info" not in str(p)
        and "__pycache__" not in p.parts
    ]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_required_directories_exist() -> None:
    for name in ("clank-fleet", "clank-runtime", "clank-desktop"):
        assert (ROOT / name).is_dir(), name
    for sub in ("compose", "config", "docs", "inventories", "tests"):
        assert (FLEET / sub).exists(), sub
    assert (FLEET / "src" / "clank_fleet" / "fleet_api").is_dir()
    assert (FLEET / "src" / "clank_fleet" / "operations").is_dir()


def test_required_docs_exist() -> None:
    for proj in (FLEET, RUNTIME, DESKTOP):
        assert (proj / "README.md").is_file(), proj
        assert (proj / "CHANGELOG.md").is_file(), proj
    assert (ROOT / "ARCHITECTURE_PRINCIPLES.md").is_file()
    assert (ROOT / "DEPENDENCIES.md").is_file()
    assert (ROOT / "Makefile").is_file()
    assert (ROOT / "LICENSE").is_file()


def test_no_windows_drive_paths_in_source() -> None:
    pattern = re.compile(r"[A-Za-z]:\\")
    for base in (FLEET / "src", RUNTIME / "src", DESKTOP / "src"):
        for path in _iter_py_files(base):
            text = _read(path)
            assert not pattern.search(text), f"Windows drive path in {path}"


def test_no_forbidden_production_imports() -> None:
    """Stage 1A: adapters may use stdlib sqlite3 read-only; nothing else may."""
    for base in (FLEET / "src", RUNTIME / "src", DESKTOP / "src"):
        for path in _iter_py_files(base):
            tree = ast.parse(_read(path), filename=str(path))
            allow_sqlite = "adapters" in path.parts
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root = alias.name.split(".")[0]
                        if root == "sqlite3" and allow_sqlite:
                            continue
                        assert root not in FORBIDDEN_IMPORT_ROOTS, f"{path}: import {alias.name}"
                elif isinstance(node, ast.ImportFrom) and node.module:
                    root = node.module.split(".")[0]
                    if root == "sqlite3" and allow_sqlite:
                        continue
                    assert root not in FORBIDDEN_IMPORT_ROOTS, f"{path}: from {node.module}"


def test_pyproject_has_no_forbidden_deps() -> None:
    for proj in (FLEET, RUNTIME, DESKTOP):
        text = _read(proj / "pyproject.toml").lower()
        for token in FORBIDDEN_DEP_SUBSTRINGS:
            # allow comments mentioning rejection
            for line in text.splitlines():
                stripped = line.strip()
                if (
                    token in line
                    and not stripped.startswith("#")
                    and (stripped.startswith('"') or "dependencies" in text)
                ):
                    assert token not in line or "reject" in line or "forbidden" in line, (
                        f"{proj}: possible forbidden dep mentioning {token}: {line}"
                    )


def test_no_secret_patterns() -> None:
    patterns = [
        re.compile(r"sk-[A-Za-z0-9]{20,}"),
        re.compile(r"password\s*=\s*['\"][^'\"]{8,}['\"]", re.I),
        re.compile(r"api[_-]?key\s*=\s*['\"][A-Za-z0-9]{16,}['\"]", re.I),
        re.compile(r"-----BEGIN (RSA |OPENSSH )?PRIVATE KEY-----"),
    ]
    for base in (FLEET, RUNTIME, DESKTOP, ROOT):
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if (
                path.suffix not in {".py", ".yml", ".yaml", ".toml", ".md", ".example", ".env"}
                and path.name not in {".env.example"}
            ):
                continue
            if any(x in path.parts for x in (".git", "__pycache__", ".pytest_cache")):
                continue
            try:
                text = _read(path)
            except Exception:
                continue
            for pat in patterns:
                assert not pat.search(text), f"Possible secret pattern in {path}"


def test_fleet_api_ping_200_and_behavior_501() -> None:
    from clank_fleet.fleet_api.app import create_app

    client = TestClient(create_app())
    r = client.get("/api/v1/system/ping")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    # Stage 1A message — must not over-claim production health
    lowered = body["message"].lower()
    assert "healthy" not in lowered or "shell" in lowered or "read-only" in lowered

    # Mutation / domain routes remain 501
    paths = (
        "/api/v1/fleet",
        "/api/v1/fleet/status",
        "/api/v1/clanks/example-clank/runs",
        "/api/v1/clanks/example-clank/collectors",
        "/api/v1/records",
        "/api/v1/events",
        "/api/v1/entities",
        "/api/v1/evidence",
        "/api/v1/review",
        "/api/v1/backups",
        "/api/v1/deployments",
        "/api/v1/ingestion",
        "/api/v1/search",
    )
    for path in paths:
        resp = client.get(path)
        assert resp.status_code == 501, f"{path} returned {resp.status_code}"
        data = resp.json()
        assert data["error_code"] == "STAGE0_NOT_IMPLEMENTED"
        assert "api_contract_version" in data

    # Stage 1A read routes are live (may be empty/stale without DBs)
    list_resp = client.get("/api/v1/clanks")
    assert list_resp.status_code == 200
    assert "clanks" in list_resp.json()


def test_cli_version_and_not_implemented() -> None:
    from typer.testing import CliRunner

    from clank_fleet.cli import EXIT_NOT_IMPLEMENTED, app

    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "0.0.1.dev0" in result.stdout

    for cmd in ("status", "doctor", "health", "backup", "deploy", "run"):
        args = [cmd]
        if cmd in {"deploy", "run"}:
            args.append("example-clank")
        result = runner.invoke(app, args)
        assert result.exit_code == EXIT_NOT_IMPLEMENTED, cmd
        combined = (result.stdout or "") + (result.stderr or "")
        assert "STAGE0_NOT_IMPLEMENTED" in combined


def test_compose_templates_parse_and_labeled() -> None:
    compose_dir = FLEET / "compose"
    for path in compose_dir.glob("*.yml"):
        text = _read(path)
        assert "NON-PRODUCTION TEMPLATE" in text, path.name
        data = yaml.safe_load(text)
        assert "services" in data
        # no docker socket
        assert "/var/run/docker.sock" not in text
        # no hardcoded NAS volume paths
        assert "/volume1/" not in text


def test_inventory_yaml_syntax() -> None:
    inv = FLEET / "inventories" / "clanks.example.yaml"
    data = yaml.safe_load(_read(inv))
    assert "clanks" in data


def test_no_existing_clank_imports_or_deps() -> None:
    """Stage 1A allows adapter modules to name Clanks; runtime/desktop still may not import them."""
    for base in (RUNTIME / "src", DESKTOP / "src"):
        for path in _iter_py_files(base):
            text = _read(path).lower()
            for token in EXISTING_CLANK_TOKENS:
                if token in text:
                    lines = [ln for ln in text.splitlines() if token in ln]
                    for ln in lines:
                        assert (
                            "example" in ln
                            or "do not" in ln
                            or "forbidden" in ln
                            or "must not" in ln
                            or "never" in ln
                        ), f"{path}: references existing clank token '{token}'"
    # Fleet may reference clank ids in adapters/; still forbid importing their packages
    for path in _iter_py_files(FLEET / "src"):
        text = _read(path)
        assert "import oem_radar" not in text
        assert "from oem_radar" not in text
        assert "import feature_phone_clank" not in text
        assert "from feature_phone_clank" not in text


def test_runtime_does_not_import_fleet_or_desktop() -> None:
    for path in _iter_py_files(RUNTIME / "src"):
        text = _read(path)
        assert "clank_fleet" not in text, path
        assert "clank_desktop" not in text, path


def test_desktop_does_not_import_fleet_impl() -> None:
    for path in _iter_py_files(DESKTOP / "src"):
        text = _read(path)
        assert "clank_fleet" not in text, path
        assert "fastapi" not in text.lower(), path
        assert "httpx" not in text.lower(), path
        assert "requests" not in text.lower(), path


def test_placeholder_modules_remain_thin() -> None:
    """Placeholder / protocol modules must not grow production logic."""
    thin_dirs = [
        RUNTIME / "src" / "clank_runtime" / "logging",
        RUNTIME / "src" / "clank_runtime" / "config",
        DESKTOP / "src" / "clank_desktop" / "services",
        DESKTOP / "src" / "clank_desktop" / "models",
    ]
    for d in thin_dirs:
        for path in _iter_py_files(d):
            text = _read(path)
            # no network, no subprocess, no sqlite
            assert "subprocess" not in text
            assert "sqlite" not in text.lower()
            assert "requests." not in text
            tree = ast.parse(text, filename=str(path))
            # disallow function defs that look like real exporters writing files
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in {"open", "write_text", "write_bytes"}
                ):
                    pytest.fail(f"{path}: placeholder must not open/write files")


def test_no_todo_with_production_logic_markers() -> None:
    """Reject TODOs that smuggle implementation intent into Stage 0.5."""
    bad = re.compile(
        r"TODO.*(implement|write jsonl|connect docker|sqlite|scrape|playwright)",
        re.I,
    )
    for base in (FLEET / "src", RUNTIME / "src", DESKTOP / "src"):
        for path in _iter_py_files(base):
            text = _read(path)
            match = bad.search(text)
            assert match is None, f"{path}: suspicious TODO: {match.group(0) if match else ''}"


def test_no_public_wildcard_port_publish_without_warning() -> None:
    for path in (FLEET / "compose").glob("*.yml"):
        text = _read(path)
        # published ports should be commented or absent
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("ports:"):
                # following lines should be comments in our templates
                continue
            if re.search(r'["\']?\d+:\d+["\']?', stripped) and not stripped.startswith("#"):
                pytest.fail(f"{path.name}: active port publish line: {stripped}")


def test_architecture_principles_reference_v21() -> None:
    text = _read(ROOT / "ARCHITECTURE_PRINCIPLES.md")
    assert "v2.1" in text or "reviewed" in text.lower()
