# ADR 0004 — No automatic execution of stale offline operational actions

## Decision

Only SAFE_OFFLINE idempotent items auto-sync. Restart/deploy/restore require live reconfirmation.

## Why

A six-hour-old restart after NAS recovery is operationally dangerous.
