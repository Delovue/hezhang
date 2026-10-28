"""Start a real API on port 18000 with a fresh, isolated database for browser tests.

Run through frontend's Playwright config using backend/.venv. Never reads or changes
the developer's database. Per-run databases remain under ignored .e2e/ for inspection.
"""

import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    backend = root / "backend"
    test_root = root / ".e2e"
    test_root.mkdir(exist_ok=True)
    run_directory = Path(tempfile.mkdtemp(prefix="frontend-", dir=test_root))
    os.environ["HEZHANG_DATABASE_URL"] = f"sqlite:///{(run_directory / 'test.db').as_posix()}"
    os.environ["HEZHANG_JWT_SECRET"] = secrets.token_urlsafe(48)
    os.chdir(backend)
    sys.path.insert(0, str(backend))
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    import uvicorn

    uvicorn.run("app.main:create_app", factory=True, host="127.0.0.1", port=18000)


if __name__ == "__main__":
    main()
