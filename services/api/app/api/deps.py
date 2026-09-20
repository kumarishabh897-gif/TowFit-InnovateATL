from collections.abc import Iterator

from fastapi import Request
from sqlmodel import Session

from app.config_loader import ConfigStore
from app.services.scenarios import ScenarioStore


def get_config(request: Request) -> ConfigStore:
    return request.app.state.config


def get_scenarios(request: Request) -> ScenarioStore:
    return request.app.state.scenarios


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session
