"""Role D's local evidence must not claim that classroom demonstration occurred."""

import importlib
import json
import sys
from pathlib import Path

import pytest


@pytest.fixture
def acceptance(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    return importlib.import_module("acceptance")


def command(tmp_path, name, code):
    return {"name": name, "command": [sys.executable, "-c", code], "cwd": str(tmp_path)}


def test_success_records_role_d_scope_and_keeps_classroom_demo_pending(acceptance, tmp_path):
    target = tmp_path / "evidence with spaces"
    checks = [command(tmp_path, "success", "print('中文 evidence')")]
    report = acceptance.run_suite(target, checks, {"commit": "test-sha", "dirty": True})
    assert report["automated_status"] == "passed"
    assert report["format_version"] == 2
    assert report["acceptance_owner"] == "role_d"
    assert report["acceptance_scope"] == "local_preclass"
    assert report["classroom_demo"] == "pending"
    assert "manual_acceptance" not in report
    assert report["environment"] == {"commit": "test-sha", "dirty": True}
    assert report["checks"][0]["exit_code"] == 0
    assert (target / "success.log").read_text(encoding="utf-8").strip() == "中文 evidence"
    assert json.loads((target / "summary.json").read_text(encoding="utf-8")) == report


def test_failure_retains_evidence_and_does_not_run_later_steps(acceptance, tmp_path):
    target = tmp_path / "failed"
    checks = [
        command(tmp_path, "fail", "import sys; print('failure'); sys.exit(7)"),
        command(tmp_path, "later", "raise AssertionError('must not run')"),
    ]
    report = acceptance.run_suite(target, checks, {})
    assert report["automated_status"] == "failed"
    assert [row["status"] for row in report["checks"]] == ["failed", "not_run"]
    assert report["checks"][0]["exit_code"] == 7
    assert not (target / "later.log").exists()


def test_existing_evidence_is_never_overwritten(acceptance, tmp_path):
    target = tmp_path / "existing"
    target.mkdir()
    marker = target / "summary.json"
    marker.write_text("original evidence", encoding="utf-8")
    with pytest.raises(FileExistsError):
        acceptance.run_suite(target, [], {})
    assert marker.read_text(encoding="utf-8") == "original evidence"


def test_migration_environment_ignores_development_database(acceptance, tmp_path, monkeypatch):
    monkeypatch.setenv("HEZHANG_DATABASE_URL", "sqlite:///do-not-touch.db")
    monkeypatch.setenv("HEZHANG_JWT_SECRET", "private-development-secret")
    target = tmp_path / "isolated"
    checks = [
        command(tmp_path, "environment", "import os; print(os.environ['HEZHANG_DATABASE_URL'])")
    ]
    report = acceptance.run_suite(target, checks, {})
    assert report["automated_status"] == "passed"
    assert (target / "environment.log").read_text(encoding="utf-8").strip() == (
        f"sqlite:///{(target / 'migration.db').as_posix()}"
    )
    assert "private-development-secret" not in (target / "summary.json").read_text(encoding="utf-8")


def test_missing_executable_is_a_recorded_failure(acceptance, tmp_path):
    check = {
        "name": "missing",
        "command": [str(tmp_path / "missing-command")],
        "cwd": str(tmp_path),
    }
    report = acceptance.run_suite(tmp_path / "missing", [check], {})
    assert report["automated_status"] == "failed"
    assert report["checks"][0]["error"]


def test_timeout_stops_process_and_records_failure(acceptance, tmp_path):
    check = command(tmp_path, "timeout", "import time; time.sleep(60)")
    report = acceptance.run_suite(tmp_path / "timeout", [check], {}, timeout=0.1)
    assert report["automated_status"] == "failed"
    assert "timed out" in report["checks"][0]["error"]


def test_empty_suite_cannot_claim_success(acceptance, tmp_path):
    assert acceptance.run_suite(tmp_path / "empty", [], {})["automated_status"] == "failed"


@pytest.mark.parametrize("node", ["v18.20.8", "v22.11.0", "v23.0.0"])
def test_unsupported_node_rejected_before_running_checks(acceptance, tmp_path, monkeypatch, node):
    monkeypatch.setattr(acceptance, "capture", lambda *_: node)
    with pytest.raises(ValueError, match="Unsupported Node.js"):
        acceptance.preflight(tmp_path)


def test_interrupt_is_not_reported_as_passed(acceptance, tmp_path, monkeypatch):
    def interrupt(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(acceptance.subprocess, "Popen", interrupt)
    check = command(tmp_path, "interrupt", "pass")
    report = acceptance.run_suite(tmp_path / "interrupted", [check], {})
    assert report["automated_status"] == "failed"
    assert report["checks"][0]["status"] == "interrupted"
