import json
from pathlib import Path

import pytest

from app.config_loader import REPO_ROOT, ConfigStore
from app.engine import evaluate_with_config
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
