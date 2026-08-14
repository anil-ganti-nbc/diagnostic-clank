# Stage 1A Acceptance

1. Register both Clanks simultaneously — **YES**
2. Same Fleet identity contract — **YES**
3. Health without shared internals — **YES**
4. Source-specific zero semantics preserved — **YES** (`blocked_zero` mapped, not reinterpreted)
5. Valid telemetry export — **YES**
6. Unavailable fields null not zero — **YES** (`delivery_count` null for FP)
7. One adapter fail isolates — **YES**
8. Stale explicit — **YES** (`is_stale` / `is_stale_cache`)
9. API list/detail/health/telemetry — **YES**
10. CLI both — **YES**
11. No production writes — **YES** (RO URI + mtime test)
12. No delivery calls — **YES**
13. DB schemas untouched — **YES**
14. Capability differences explicit — **YES** (FULL vs LIMITED delivery)
15. Future desktop can use API — **YES**
16. Contract versions explicit — **YES**
17. Adapters evolve independently — **YES**
18. Stage 1B onboarding another Clank straightforward — **YES** (copy adapter pattern)
19. NAS migration not performed — **YES**
20. Durable export for Codex — **YES** (handoff bundle)
