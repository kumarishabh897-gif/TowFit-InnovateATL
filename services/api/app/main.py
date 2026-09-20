"""ClearanceOS / TowFit API.

Run:  uvicorn app.main:create_app --factory --reload
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config_loader import REPO_ROOT, ConfigError, ConfigStore
from app.db import init_db, make_engine
from app.services.scenarios import ScenarioStore

DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"


def create_app(
    config_dir: Path | None = None,
    database_url: str | None = None,
    fixtures_dir: Path | None = None,
) -> FastAPI:
    config = ConfigStore(config_dir)  # fails fast on a malformed config file
    engine = make_engine(database_url)
    scenarios = ScenarioStore(fixtures_dir or REPO_ROOT / "fixtures" / "scenarios")

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        init_db(engine)
        yield

    app = FastAPI(
        title="ClearanceOS / TowFit API",
        version="0.1.0",
        description=(
            "TowFit does not replace operator judgment or authorize a move. "
            "It provides a documented safety recommendation based on vehicle, rig, and scene constraints."
        ),
        lifespan=lifespan,
    )
    app.state.config = config
    app.state.engine = engine
    app.state.scenarios = scenarios

    origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(ConfigError)
    async def config_error(_: Request, exc: ConfigError) -> JSONResponse:
        # A config file was edited by hand into an invalid state. Say so plainly rather than serving stale numbers.
        return JSONResponse(status_code=500, content={"detail": f"Configuration is invalid: {exc}"})

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        snap = config.snapshot()
        return {
            "status": "ok",
            "units": len(snap.fleet),
            "vehicle_models": len(snap.specs.models),
            "assumptions": len(snap.assumptions),
            "unvalidated_assumptions": sum(1 for a in snap.assumptions.values() if a.is_unvalidated),
        }

    app.include_router(router)
    return app
