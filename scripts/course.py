"""Prepare an isolated course demo, serve it locally, or verify persistence after restart.

Run with backend/.venv's Python. A new directory is required for prepare/verify;
existing directories and all existing databases are left untouched.
"""

import argparse
import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
PASSWORD = "Demo-pass-2026"
ACCOUNTS = [("demo_a", "小王"), ("demo_b", "小李"), ("demo_c", "小陈")]


def environment(directory: Path) -> dict[str, str]:
    secret = (
        (directory / ".env").read_text(encoding="utf-8").strip().removeprefix("HEZHANG_JWT_SECRET=")
    )
    if len(secret) < 32:
        raise ValueError("Demo configuration is invalid")
    return {
        **os.environ,
        "HEZHANG_DATABASE_URL": f"sqlite:///{(directory / 'ledger.db').as_posix()}",
        "HEZHANG_JWT_SECRET": secret,
        "PYTHONUTF8": "1",
    }


def migrate(env: dict[str, str]) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env, check=True
    )


def prepare(directory: Path) -> dict:
    print(f"New isolated demo directory: {directory}", flush=True)
    # Exclusive creation is intentional: no reset/delete option and no partially overwriting data.
    directory.mkdir(parents=True, exist_ok=False)
    (directory / ".env").write_text(
        f"HEZHANG_JWT_SECRET={secrets.token_urlsafe(48)}\n", encoding="utf-8"
    )
    env = environment(directory)
    migrate(env)
    sys.path.insert(0, str(BACKEND))
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    settings = Settings(
        database_url=env["HEZHANG_DATABASE_URL"],
        jwt_secret=env["HEZHANG_JWT_SECRET"],
        _env_file=None,
    )
    with TestClient(create_app(settings)) as client:

        def post(path: str, data=None, headers=None):
            response = client.post(f"/api/v1{path}", json=data, headers=headers)
            response.raise_for_status()
            return response.json()

        auth = []
        for username, name in ACCOUNTS:
            post(
                "/auth/register", {"username": username, "display_name": name, "password": PASSWORD}
            )
            token = post("/auth/login", {"username": username, "password": PASSWORD})
            auth.append({"Authorization": f"Bearer {token['access_token']}"})
        activities = []
        for name, budget in [("三人出游 · 现场演示", 20000), ("分摊方式样例", 100000)]:
            activity = post("/activities", {"name": name, "budget_cents": budget}, auth[0])
            for headers in auth[1:]:
                post("/activities/join", {"invite_code": activity["invite_code"]}, headers)
            activities.append(activity)
        sample = activities[1]["id"]
        members = client.get(f"/api/v1/activities/{sample}/members", headers=auth[0]).json()
        for method, title, amount, values in [
            ("EXACT", "指定金额餐费", 10000, [2000, 3000, 5000]),
            ("SHARES", "按份数住宿费", 60000, [2, 1, 1]),
        ]:
            key = "amount_cents" if method == "EXACT" else "shares"
            post(
                f"/activities/{sample}/expenses",
                {
                    "title": title,
                    "category": "餐饮" if method == "EXACT" else "住宿",
                    "amount_cents": amount,
                    "expense_date": "2026-10-30",
                    "payer_member_id": members[0]["id"],
                    "split_method": method,
                    "participants": [
                        {"member_id": member["id"], key: value}
                        for member, value in zip(members, values, strict=True)
                    ],
                    "request_id": str(uuid4()),
                },
                auth[0],
            )
    metadata = {
        "format_version": 1,
        "accounts": [{"username": username, "display_name": name} for username, name in ACCOUNTS],
        "live_activity_id": activities[0]["id"],
        "sample_activity_id": sample,
    }
    (directory / "demo.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("Demo accounts: demo_a / demo_b / demo_c; password: Demo-pass-2026", flush=True)
    print("Live activity has three members and no expenses; sample activity has EXACT/SHARES.")
    return metadata


def check_port(port: int) -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", port))


def launch(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.Popen:
    options = (
        {"creationflags": subprocess.CREATE_NO_WINDOW}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    return subprocess.Popen(command, cwd=cwd, env=env, **options)


def stop(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait(timeout=5)


def wait_ready(url: str, process: subprocess.Popen) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Server exited with code {process.returncode}")
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError):
            time.sleep(0.15)
    raise TimeoutError(f"Server did not become ready: {url}")


def api_command(port: int) -> list[str]:
    return [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:create_app",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--no-access-log",
    ]


def serve(directory: Path, api_port: int, web_port: int, backend_only: bool) -> None:
    if not (directory / "demo.json").is_file() or not (directory / "ledger.db").is_file():
        raise ValueError("Run prepare with a new demo directory first")
    check_port(api_port)
    npm = None
    if not backend_only:
        if api_port == web_port:
            raise ValueError("API and frontend ports must differ")
        check_port(web_port)
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
        if not npm or not (ROOT / "frontend/node_modules/vite/bin/vite.js").is_file():
            raise ValueError("Install Node.js, then run npm ci in frontend/ first")
    env = environment(directory)
    migrate(env)
    processes: list[subprocess.Popen] = []
    try:
        api = launch(api_command(api_port), BACKEND, env)
        processes.append(api)
        wait_ready(f"http://127.0.0.1:{api_port}/health", api)
        if npm:
            command = [npm, "run", "dev", "--", "--port", str(web_port)]
            if os.name == "nt":
                command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", *command]
            web = launch(
                command,
                ROOT / "frontend",
                {**env, "HEZHANG_API_TARGET": f"http://127.0.0.1:{api_port}"},
            )
            processes.append(web)
            wait_ready(f"http://127.0.0.1:{web_port}", web)
            print(f"Local: http://127.0.0.1:{web_port}/", flush=True)
        print(f"API: http://127.0.0.1:{api_port}/docs", flush=True)
        print(f"Data: {directory}\nPress Ctrl+C to stop both servers.", flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(0.4)
        raise RuntimeError("A server stopped unexpectedly")
    except KeyboardInterrupt:
        print("Stopping the demo servers.")
    finally:
        for process in reversed(processes):
            stop(process)


def verify(directory: Path) -> None:
    prepare(directory)
    env = environment(directory)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    command = [
        sys.executable,
        str(ROOT / "scripts/settlement_smoke.py"),
        "--base-url",
        f"http://127.0.0.1:{port}",
        "--state",
        str(directory / "smoke-state.json"),
    ]
    for restarting in [False, True]:
        process = launch(api_command(port), BACKEND, env)
        try:
            wait_ready(f"http://127.0.0.1:{port}/health", process)
            subprocess.run(
                command + (["--verify-only"] if restarting else []),
                cwd=BACKEND,
                env=env,
                check=True,
            )
        finally:
            stop(process)
    (directory / "verification.json").write_text(
        json.dumps(
            {"workflow_passed": True, "restart_passed": True, "python": sys.version.split()[0]},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("PASS: real HTTP workflow and persistence after a full process restart.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["prepare", "serve", "verify"])
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--api-port", type=int, default=18001)
    parser.add_argument("--web-port", type=int, default=15174)
    parser.add_argument("--backend-only", action="store_true")
    args = parser.parse_args()
    if not all(1 <= port <= 65535 for port in [args.api_port, args.web_port]):
        parser.error("Ports must be between 1 and 65535")
    directory = args.directory.resolve()
    try:
        if args.command == "prepare":
            prepare(directory)
        elif args.command == "verify":
            verify(directory)
        else:
            serve(directory, args.api_port, args.web_port, args.backend_only)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
