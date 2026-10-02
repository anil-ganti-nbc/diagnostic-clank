"""CTW host integration requires the real optional trace producer."""
import pytest

from clank_fleet.execution_results import ctw_scheduler_probe as probe


def test_missing_optional_dependency_fails_explicitly(monkeypatch, tmp_path):
    def unavailable(name):
        assert name == "motherclank.scheduler_traces"
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(probe, "import_module", unavailable)
    with pytest.raises(ModuleNotFoundError, match="motherclank.scheduler_traces"):
        probe.extract_cron_fires(clank_id="ctw", instance_id="i", lane_id="l",
                                 log_dir=tmp_path, expected_target="collect")


def test_invalid_trace_producer_rejected(monkeypatch):
    monkeypatch.setattr(probe, "import_module", lambda name: object())
    with pytest.raises(TypeError, match="must be callable"):
        probe._trace_module()


def test_delegates_fields_and_preserves_producer_result(monkeypatch, tmp_path):
    calls = []
    canonical = {"content_hash": "producer-owned", "schema_version": 1}

    class TraceProducer:
        def make_trace(self, **fields):
            calls.append(fields)
            return canonical

    monkeypatch.setattr(probe, "import_module", lambda name: TraceProducer())
    (tmp_path / "cron-20261002.log").write_text("2026-10-02T06:15:00Z collect\n")
    result = probe.extract_cron_fires(clank_id="ctw", instance_id="i", lane_id="l",
                                      log_dir=tmp_path, expected_target="collect")
    assert result == [canonical]
    assert result[0] is canonical
    assert calls == [{"trace_id": "cron-ctw-0", "clank_id": "ctw",
                      "instance_id": "i", "lane_id": "l", "scheduler_type": "cron",
                      "unit_or_job": "collect", "invoked_at": "2026-10-02T06:15Z",
                      "process_started": None, "evidence_source": "journal",
                      "notes": "matched 'collect' in cron-20261002.log"}]


def test_absent_logs_need_no_optional_dependency(monkeypatch, tmp_path):
    def unexpected(name):
        raise AssertionError("must not import")

    monkeypatch.setattr(probe, "import_module", unexpected)
    assert probe.extract_cron_fires(clank_id="ctw", instance_id="i", lane_id="l",
                                    log_dir=tmp_path / "absent", expected_target="collect") == []
