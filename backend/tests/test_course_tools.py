"""Verify demo preparation through its public CLI without sharing app globals."""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_demo_preparation_is_isolated_and_refuses_existing_data(tmp_path):
    root = Path(__file__).resolve().parents[2]
    target = tmp_path / "course"
    command = [
        sys.executable,
        str(root / "scripts/course.py"),
        "prepare",
        "--directory",
        str(target),
    ]
    result = subprocess.run(command, cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    metadata = json.loads((target / "demo.json").read_text(encoding="utf-8"))
    with sqlite3.connect(target / "ledger.db") as connection:
        assert connection.execute("SELECT count(*) FROM users").fetchone()[0] == 3
        assert connection.execute("SELECT count(*) FROM memberships").fetchone()[0] == 6
        assert (
            connection.execute(
                "SELECT count(*) FROM expenses WHERE activity_id = ?",
                (metadata["live_activity_id"],),
            ).fetchone()[0]
            == 0
        )
        assert connection.execute("SELECT sum(amount_cents) FROM expenses").fetchone()[0] == 70000
    before = (target / "ledger.db").read_bytes()
    (target / "keep.txt").write_text("do not touch", encoding="utf-8")
    repeated = subprocess.run(command, cwd=root, capture_output=True, text=True)
    assert repeated.returncode != 0
    assert (target / "ledger.db").read_bytes() == before
    assert (target / "keep.txt").read_text(encoding="utf-8") == "do not touch"


def test_real_workflow_and_restart_ignore_shell_proxies(tmp_path):
    root = Path(__file__).resolve().parents[2]
    target = tmp_path / "restart evidence"
    env = {**os.environ, "PYTHONUTF8": "1"}
    # Intentionally unusable proxy and no loopback exemption: both readiness
    # and the HTTP smoke client must connect directly to their own local server.
    for name in [
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ]:
        env[name] = "http://127.0.0.1:1"
    env.update(NO_PROXY="", no_proxy="")
    result = subprocess.run(
        [sys.executable, str(root / "scripts/course.py"), "verify", "--directory", str(target)],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    evidence = json.loads((target / "verification.json").read_text(encoding="utf-8"))
    assert evidence["workflow_passed"] is True
    assert evidence["restart_passed"] is True
    state = json.loads((target / "smoke-state.json").read_text(encoding="utf-8"))
    with sqlite3.connect(target / "ledger.db") as connection:
        assert connection.execute(
            "SELECT status FROM activities WHERE id = ?", (state["activity_id"],)
        ).fetchone() == ("ARCHIVED",)
        assert connection.execute(
            "SELECT count(*) FROM payments WHERE activity_id = ? AND status = 'CONFIRMED'",
            (state["activity_id"],),
        ).fetchone() == (3,)
