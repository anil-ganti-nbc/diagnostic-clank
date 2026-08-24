"""OEM Radar execution-result extractor + invocation-block-locator (P-4.2).

locate_invocation_block was moved here from a host-only probe script during
live validation (2026-08-24): the same live-validation pass proved it
against a real natural zero-work cron cycle before this move, and again
after, to confirm the canonicalized version behaves identically.
"""

from __future__ import annotations

from clank_fleet.execution_results.oem_radar import (
    EXTRACTOR,
    locate_invocation_block,
)

# Fixture text mirrors the real deployed cron-log format observed live
# 2026-08-24 (two invocations in one day's accumulated log).
_LOG_TEXT = """\
2026-08-24 15:20:02,552 INFO oem_radar.run_lock: acquired run lock data/oem-radar.lock (pid=1)
2026-08-24 15:20:02,558 INFO oem_radar.runner: skip acemagic-shopify: crawled within min_interval
2026-08-24 15:20:18,574 INFO oem_radar.runner: chuwi-shopify: 25 discovered, 0 new snapshots, 15 unchanged, 10 skipped, 0 events, 0 errors
2026-08-24 15:20:18,596 INFO oem_radar.run_lock: released run lock data/oem-radar.lock
done: 1 source(s) crawled, 0 snapshot(s), 0 event(s)
2026-08-24 18:20:02,495 INFO oem_radar.run_lock: acquired run lock data/oem-radar.lock (pid=1)
2026-08-24 18:20:02,508 INFO oem_radar.runner: skip acemagic-shopify: crawled within min_interval
2026-08-24 18:20:02,530 INFO oem_radar.run_lock: released run lock data/oem-radar.lock
done: 0 source(s) crawled, 0 snapshot(s), 0 event(s)
"""


def test_locate_invocation_block_finds_the_matching_block_by_timestamp():
    block = locate_invocation_block(_LOG_TEXT, "2026-08-24T18:20:01+00:00")
    assert block is not None
    assert "done: 0 source(s) crawled" in block
    assert "15:20" not in block  # does not bleed into the earlier invocation


def test_locate_invocation_block_picks_the_earlier_invocation_too():
    block = locate_invocation_block(_LOG_TEXT, "2026-08-24T15:20:01+00:00")
    assert block is not None
    assert "done: 1 source(s) crawled" in block
    assert "18:20" not in block


def test_locate_invocation_block_none_outside_tolerance():
    # No invocation near this time in the fixture -> None, never a guess.
    assert locate_invocation_block(_LOG_TEXT, "2026-08-24T09:00:00+00:00") is None


def test_locate_invocation_block_none_on_empty_log():
    assert locate_invocation_block("", "2026-08-24T18:20:01+00:00") is None


def test_extractor_consumes_the_located_block_end_to_end():
    block = locate_invocation_block(_LOG_TEXT, "2026-08-24T18:20:01+00:00")
    result = EXTRACTOR.extract(block, exit_code=0)
    assert result["execution_result"] == "no_work_due"
    assert result["extractor_id"] == "oem-radar/done-line"
