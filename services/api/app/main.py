from contextlib import asynccontextmanager
from functools import cache

from fastapi import FastAPI

from app.config_loader import ConfigStore
from app.db import init_db, make_engine


@cache
def get_config() -> ConfigStore:
    return ConfigStore()


@cache
def get_engine():
    return make_engine()


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_config()  # fail fast on a malformed config file
    init_db(get_engine())
    yield


app = FastAPI(title="ClearanceOS / TowFit API", version="0.0.1", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    config = get_config()
    return {
        "status": "ok",
        "units": len(config.fleet),
        "vehicle_models": len(config.vehicle_specs.models),
        "assumptions": len(config.assumptions),
        "unvalidated_assumptions": config.unvalidated_assumption_count(),
    }
