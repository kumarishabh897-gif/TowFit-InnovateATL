"""Vercel entry point: serves the FastAPI app (everything under /v1, plus /health and /docs).

Vercel functions have no persistent disk, so the SQLite file lives in /tmp and is private to each function
instance: Decision Records are demo-only here and can disappear when an instance restarts. Config is
read-only, so live assumption edits are switched off.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/towfit.db")
os.environ.setdefault("TOWFIT_READ_ONLY_CONFIG", "1")

from app.db import init_db  # noqa: E402
from app.main import create_app  # noqa: E402

app = create_app()
init_db(app.state.engine)  # do not rely on ASGI lifespan events running on Vercel
