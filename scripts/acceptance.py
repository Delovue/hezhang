"""Run the course's automated acceptance checks and retain versioned evidence.

Install locked backend/frontend dependencies and Chromium first. Run with the
backend virtualenv's Python; --directory must be new. Role D owns local acceptance;
classroom demonstration is recorded separately and is not run by this command.
"""

import argparse
import hashlib
import json
import os
import platform
import secrets
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from course import stop

ROOT = Path(__file__).resolve().parents[1]


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


def capture(command: list[str], cwd: Path) -> str:
    return subprocess.check_output(command, cwd=cwd, text=True, encoding="utf-8").strip()


def npm_command(*args: str) -> list[str]:
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        raise ValueError("Install Node.js 22.12+ (22.x) or Node.js 24+ and npm first")
    if os.name == "nt":
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", npm, *args]
    return [npm, *args]


def preflight(root: Path) -> dict:
    if sys.version_info[:2] != (3, 12):
        raise ValueError("Run with backend/.venv's Python 3.12 after uv sync --locked")
    node = capture(["node", "--version"], root)
    version = tuple(int(part) for part in node.removeprefix("v").split("."))
    if not (version >= (24, 0, 0) or (22, 12, 0) <= version < (23, 0, 0)):
        raise ValueError(f"Unsupported Node.js {node}; use 22.12+ (22.x) or 24+")
    for dependency in ["vite", "vitest", "@playwright/test"]:
        if not (root / "frontend/node_modules" / dependency / "package.json").is_file():
            raise ValueError("Run npm ci and npm run test:install-browser in frontend/ first")
    return {
        "python": platform.python_version(),
        "node": node,
        "npm": capture(npm_command("--version"), root),
        "platform": platform.platform(),
        "commit": capture(["git", "rev-parse", "HEAD"], root),
        "dirty": bool(capture(["git", "status", "--porcelain"], root)),
        "lockfiles_sha256": {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in ["backend/uv.lock", "frontend/package-lock.json"]
        },
    }


def steps(root: Path, directory: Path) -> list[dict]:
    python = sys.executable
    backend = root / "backend"
    frontend = root / "frontend"
    return [
        {"name": name, "command": command, "cwd": str(cwd)}
        for name, command, cwd in [
            (
                "backend-lint",
                [python, "-m", "ruff", "check", "app", "tests", "migrations"],
                backend,
            ),
            (
                "backend-format",
                [python, "-m", "ruff", "format", "--check", "app", "tests", "migrations"],
                backend,
            ),
            (
                "tooling-lint",
                [python, "-m", "ruff", "check", "../scripts/acceptance.py", "../scripts/course.py"],
                backend,
            ),
            (
                "tooling-format",
                [
                    python,
                    "-m",
                    "ruff",
                    "format",
                    "--check",
                    "../scripts/acceptance.py",
                    "../scripts/course.py",
                ],
                backend,
            ),
            ("migrate", [python, "-m", "alembic", "upgrade", "head"], backend),
            ("migration-check", [python, "-m", "alembic", "check"], backend),
            (
                "backend-tests",
                [
                    python,
                    "-m",
                    "pytest",
                    "-q",
                    "--cov=app",
                    "--cov-report=term-missing",
                    f"--cov-report=json:{directory / 'coverage.json'}",
                    f"--junitxml={directory / 'backend.xml'}",
                ],
                backend,
            ),
            ("frontend-build", npm_command("run", "build"), frontend),
            (
                "frontend-tests",
                npm_command(
                    "test",
                    "--",
                    "--reporter=default",
                    "--reporter=json",
                    f"--outputFile={directory / 'frontend.json'}",
                ),
                frontend,
            ),
            (
                "browser-tests",
                npm_command(
                    "run",
                    "test:e2e",
                    "--",
                    "--reporter=list,json",
                    f"--output={directory / 'browser-artifacts'}",
                ),
                frontend,
            ),
            (
                "http-restart",
                [
                    python,
                    str(root / "scripts/course.py"),
                    "verify",
                    "--directory",
                    str(directory / "restart"),
                ],
                root,
            ),
        ]
    ]


def run_step(step: dict, directory: Path, env: dict[str, str], timeout: float) -> dict:
    result = {**step, "status": "running", "started_at": timestamp(), "log": f"{step['name']}.log"}
    started = time.monotonic()
    process = None
    with (directory / result["log"]).open("w", encoding="utf-8") as log:
        try:
            options = (
                {"creationflags": subprocess.CREATE_NO_WINDOW}
                if os.name == "nt"
                else {"start_new_session": True}
            )
            process = subprocess.Popen(
                step["command"],
                cwd=step["cwd"],
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                **options,
            )
            result["exit_code"] = process.wait(timeout=timeout)
            result["status"] = "passed" if result["exit_code"] == 0 else "failed"
        except subprocess.TimeoutExpired:
            result.update(status="failed", error=f"Step timed out after {timeout} seconds")
        except OSError as error:
            result.update(status="failed", error=str(error))
        except KeyboardInterrupt:
            result.update(status="interrupted", error="Interrupted by operator")
        finally:
            if process is not None:
                stop(process)
    result.update(duration_seconds=round(time.monotonic() - started, 3), finished_at=timestamp())
    return result


def run_suite(directory: Path, checks: list[dict], metadata: dict, timeout: float = 900) -> dict:
    # Never overwrite a previous result or migrate an existing development database.
    directory.mkdir(parents=True, exist_ok=False)
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "HEZHANG_DATABASE_URL": f"sqlite:///{(directory / 'migration.db').as_posix()}",
        "HEZHANG_JWT_SECRET": secrets.token_urlsafe(48),
        "PLAYWRIGHT_JSON_OUTPUT_FILE": str(directory / "browser.json"),
        "COVERAGE_FILE": str(directory / ".coverage"),
        "NO_COLOR": "1",
    }
    report = {
        "format_version": 2,
        "started_at": timestamp(),
        "environment": metadata,
        "automated_status": "running",
        "acceptance_owner": "role_d",
        "acceptance_scope": "local_preclass",
        "classroom_demo": "pending",
        "checks": [{**step, "status": "not_run"} for step in checks],
    }

    def save():
        temporary = directory / "summary.tmp"
        temporary.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(directory / "summary.json")

    save()
    for index, step in enumerate(checks):
        print(f"[{index + 1}/{len(checks)}] {step['name']}", flush=True)
        report["checks"][index]["status"] = "running"
        save()
        result = run_step(step, directory, env, timeout)
        report["checks"][index] = result
        save()
        print(f"  {result['status']}: {result['log']}", flush=True)
        if result["status"] != "passed":
            break
    report["automated_status"] = (
        "passed"
        if checks and all(row["status"] == "passed" for row in report["checks"])
        else "failed"
    )
    report["finished_at"] = timestamp()
    save()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--directory", type=Path, required=True, help="New evidence directory")
    args = parser.parse_args()
    directory = args.directory.resolve()
    try:
        metadata = preflight(ROOT)
        report = run_suite(directory, steps(ROOT, directory), metadata)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")
    print(f"Role D automated acceptance: {report['automated_status']}; classroom demo: pending")
    print(f"Evidence: {directory / 'summary.json'}")
    return 0 if report["automated_status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
