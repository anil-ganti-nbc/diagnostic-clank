# CLANKOPS_RECORD v1

Deterministic structured footer. Human-readable report is primary evidence.

```
CLANKOPS_RECORD
schema_version: 1
agent: grok
project: oem-radar
task: example-task
timestamp: 2026-08-18T12:00:00Z
repo:
branch:
start_sha:
end_sha:
pr:
hosts_read:
hosts_modified:
tests:
p0:
p1:
p2:
p3:
decisions:
unresolved:
next_action:
verdict:
```

Unknown/empty fields allowed. Never fabricates values.
Object identity is content hash, never host path.
