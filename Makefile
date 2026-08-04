# Unified Clank Stage 0.5 — developer targets only.
# No deployment, no Docker build, no NAS, no production actions.

.PHONY: help bootstrap install test lint typecheck architecture check clean tree

PYTHON ?= python3
PACKAGES := clank-runtime clank-fleet clank-desktop

help:
	@echo "Unified Clank Stage 0.5 targets:"
	@echo "  make bootstrap   - install all packages editable with dev deps"
	@echo "  make install     - alias for bootstrap"
	@echo "  make test        - run unit + architecture tests"
	@echo "  make lint        - ruff check all packages"
	@echo "  make typecheck   - pyright (if installed)"
	@echo "  make architecture - architecture guardrail tests only"
	@echo "  make check       - lint + test"
	@echo "  make tree        - show repository tree"
	@echo "  make clean       - remove caches and build artifacts"
	@echo ""
	@echo "Stage 0.5 does not deploy, build images, or run clanks."

bootstrap install:
	$(PYTHON) -m pip install -e "./clank-runtime[dev]"
	$(PYTHON) -m pip install -e "./clank-fleet[dev]"
	$(PYTHON) -m pip install -e "./clank-desktop[dev]"

test:
	cd clank-runtime && $(PYTHON) -m pytest -q
	cd clank-fleet && $(PYTHON) -m pytest -q
	cd clank-desktop && QT_QPA_PLATFORM=offscreen CLANK_DESKTOP_TEST_SAFE=1 $(PYTHON) -m pytest -q

architecture:
	cd clank-fleet && $(PYTHON) -m pytest -q tests/test_architecture.py

lint:
	ruff check --no-cache clank-runtime/src clank-runtime/tests
	ruff check --no-cache clank-fleet/src clank-fleet/tests
	ruff check --no-cache clank-desktop/src clank-desktop/tests

typecheck:
	@command -v pyright >/dev/null && pyright clank-runtime/src clank-fleet/src clank-desktop/src || echo "pyright not installed; skip"

check: lint test

tree:
	@find . -type f ! -path '*/__pycache__/*' ! -path '*/.pytest_cache/*' ! -path '*/.ruff_cache/*' ! -path '*/.git/*' ! -name '*.pyc' | sort

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name dist -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name build -exec rm -rf {} + 2>/dev/null || true
