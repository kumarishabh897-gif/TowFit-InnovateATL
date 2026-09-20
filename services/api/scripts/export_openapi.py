"""Write the API's OpenAPI schema to docs/openapi.json. The typed TypeScript client is generated from this file.

Run from services/api:  .venv/bin/python scripts/export_openapi.py
"""

import json
import tempfile
from pathlib import Path

from app.config_loader import REPO_ROOT
from app.main import create_app

OUTPUT = REPO_ROOT / "docs" / "openapi.json"


def build_schema() -> dict:
    with tempfile.TemporaryDirectory() as tmp:  # a throwaway DB, so exporting never touches real data
        return create_app(database_url=f"sqlite:///{tmp}/schema.db").openapi()


def render(schema: dict) -> str:
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    OUTPUT.write_text(render(build_schema()))
    print(f"wrote {OUTPUT}")
