#!/bin/sh
# TEMPLATE entrypoint — no scheduler, no domain logic.
set -eu
cd /app

if [ -n "${{CLANK_ENV_PREFIX}}_DATA_DIR:-}" ]; then
  mkdir -p "${{CLANK_ENV_PREFIX}}_DATA_DIR" 2>/dev/null || true
fi

if [ "$#" -eq 0 ]; then
  exec {{CLI_NAME}} run
fi

case "$1" in
  {{CLI_NAME}})
    shift
    exec {{CLI_NAME}} "$@"
    ;;
  version|identity|health|run|status|validate)
    exec {{CLI_NAME}} "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
