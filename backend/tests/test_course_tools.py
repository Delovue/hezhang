"""Verify demo preparation through its public CLI without sharing app globals."""

import json
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
