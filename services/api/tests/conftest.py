import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config_loader import REPO_ROOT, ConfigStore
from app.engine import evaluate_with_config
from app.main import create_app
from app.models import EvaluationInput, Verdict

SCENARIO_DIR = REPO_ROOT / "fixtures" / "scenarios"


@pytest.fixture(scope="session")
def config() -> ConfigStore:
    return ConfigStore(REPO_ROOT / "config")


def load_scenario(name: str) -> EvaluationInput:
    return EvaluationInput.model_validate(json.loads((SCENARIO_DIR / f"{name}.json").read_text())["input"])


def edit(inp: EvaluationInput, **sections: dict) -> EvaluationInput:
    """Copy an input, overriding fields inside its sections: edit(inp, crash={"axle_damage": True})."""
    data = inp.model_dump()
    for section, changes in sections.items():
        if isinstance(data[section], dict):
            data[section].update(changes)
        else:
            data[section] = changes
    return EvaluationInput.model_validate(data)


@pytest.fixture()
def run(config):
    def _run(inp: EvaluationInput) -> Verdict:
        return evaluate_with_config(inp, config)

    return _run


@pytest.fixture()
def green_input() -> EvaluationInput:
    return load_scenario("01_green_accord")


@dataclass
class Api:
    client: TestClient
    app: FastAPI
    config_dir: Path

    def session(self) -> Session:
        return Session(self.app.state.engine)

    def evaluate(self, inp: EvaluationInput):
        return self.client.post("/v1/towfit/evaluate", content=inp.model_dump_json(), headers={"content-type": "application/json"})


@pytest.fixture()
def api(tmp_path):
    """A fresh app per test: its own copy of config/ (so PUT /v1/assumptions never touches the real files) and its own DB."""
    config_dir = tmp_path / "config"
    shutil.copytree(REPO_ROOT / "config", config_dir)
    app = create_app(config_dir=config_dir, database_url=f"sqlite:///{tmp_path / 'test.db'}")
    with TestClient(app) as client:
        yield Api(client=client, app=app, config_dir=config_dir)
