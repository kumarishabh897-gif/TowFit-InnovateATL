import os
from pathlib import Path

from sqlalchemy import DDL, Engine, event
from sqlmodel import SQLModel, create_engine

from app.config_loader import REPO_ROOT
from app.models import DecisionEvent, DecisionRecord

DEFAULT_DB_URL = f"sqlite:///{REPO_ROOT / 'services/api/data/clearanceos.db'}"

# Decision Records are an audit trail (liability, post-incident review), so the database itself
# refuses to change or delete them; application code cannot bypass this by accident.
_APPEND_ONLY_TABLES = ("decision_record", "decision_event")


def _append_only_ddl(table: str, verb: str) -> DDL:
    return DDL(
        f"CREATE TRIGGER IF NOT EXISTS {table}_no_{verb.lower()} BEFORE {verb} ON {table} "
        f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END"
    )


for _model in (DecisionRecord, DecisionEvent):
    for _verb in ("UPDATE", "DELETE"):
        event.listen(_model.__table__, "after_create", _append_only_ddl(_model.__tablename__, _verb))


def make_engine(url: str | None = None) -> Engine:
    url = url or os.environ.get("DATABASE_URL") or DEFAULT_DB_URL
    if url.startswith("sqlite:///") and url != "sqlite://":
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})


def init_db(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)
