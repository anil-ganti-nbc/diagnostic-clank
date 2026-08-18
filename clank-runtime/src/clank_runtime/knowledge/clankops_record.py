"""Deterministic CLANKOPS_RECORD footer extraction -- no LLM.

Looks for a `CLANKOPS_RECORD` block in pasted agent output and extracts
`key: value` style fields it recognizes. Never guesses a missing field;
absent fields stay None. If no such block is found, returns an empty
CLANKOPSRecord (all fields None) -- the raw report is always preserved by
the caller regardless of what this extracts.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

FIELD_NAMES = (
    "schema_version", "agent", "project", "task", "timestamp", "repo", "branch", "start_sha", "end_sha",
    "pr", "hosts_read", "hosts_modified", "tests", "p0", "p1", "p2", "p3",
    "decisions", "unresolved", "next_action", "verdict",
)

_BLOCK_START = re.compile(r"CLANKOPS_RECORD\b", re.IGNORECASE)
_FIELD_LINE = re.compile(
    r"^\s*[-*]?\s*(" + "|".join(FIELD_NAMES) + r")\s*[:=]\s*(.*)$",
    re.IGNORECASE,
)


class CLANKOPSRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str | None = None
    agent: str | None = None
    project: str | None = None
    task: str | None = None
    timestamp: str | None = None
    repo: str | None = None
    branch: str | None = None
    start_sha: str | None = None
    end_sha: str | None = None
    pr: str | None = None
    hosts_read: str | None = None
    hosts_modified: str | None = None
    tests: str | None = None
    p0: str | None = None
    p1: str | None = None
    p2: str | None = None
    p3: str | None = None
    decisions: str | None = None
    unresolved: str | None = None
    next_action: str | None = None
    verdict: str | None = None

    def is_empty(self) -> bool:
        return all(getattr(self, f) is None for f in FIELD_NAMES)


def extract_clankops_record(raw_text: str) -> CLANKOPSRecord:
    match = _BLOCK_START.search(raw_text)
    if match is None:
        return CLANKOPSRecord()
    lines = raw_text[match.end():].splitlines()
    values: dict[str, str] = {}
    blank_run = 0
    for line in lines:
        if not line.strip():
            blank_run += 1
            if blank_run >= 3:  # end of the footer block, not just a spaced-out list
                break
            continue
        blank_run = 0
        field_match = _FIELD_LINE.match(line)
        if field_match:
            key = field_match.group(1).lower()
            value = field_match.group(2).strip()
            if value:
                values[key] = value
    return CLANKOPSRecord(**values)
