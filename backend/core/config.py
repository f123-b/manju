from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_env_file() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()
DATA_DIR = ROOT / "data"
DB_PATH = Path(os.environ.get("SHORT_DRAMA_DB", DATA_DIR / "short-drama.sqlite3"))
DIST_DIR = ROOT / "dist" / "client"
PROJECT_ID = os.environ.get("SHORT_DRAMA_PROJECT_ID", "P001")
