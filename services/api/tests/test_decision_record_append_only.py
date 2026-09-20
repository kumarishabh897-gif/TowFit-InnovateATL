import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError
from sqlmodel import Session, select

from app.db import init_db, make_engine
from app.models import DecisionEvent, DecisionRecord


@pytest.fixture()
def engine(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_db(engine)
    return engine


def _record() -> DecisionRecord:
    return DecisionRecord(
        unit_id="PATROL-42",
        vehicle_summary="2022 Honda Accord",
        verdict="GREEN",
        inputs_json="{}",
        reasons_json="[]",
        rules_fired_json="[]",
        assumptions_json="{}",
        disclaimer="d",
    )


def test_insert_and_read_back(engine):
    with Session(engine) as s:
        s.add(_record())
        s.commit()
        row = s.exec(select(DecisionRecord)).one()
        assert row.id is not None and row.created_at is not None
        s.add(DecisionEvent(decision_id=row.id, kind="operator_action", action="deploy"))
        s.commit()
        assert s.exec(select(DecisionEvent)).one().action == "deploy"


@pytest.mark.parametrize("sql", ["UPDATE decision_record SET verdict='RED'", "DELETE FROM decision_record"])
def test_record_rejects_update_and_delete_even_from_raw_sql(engine, sql):
    with Session(engine) as s:
        s.add(_record())
        s.commit()
        with pytest.raises(DatabaseError, match="append-only"):
            s.exec(text(sql))


def test_record_rejects_orm_update(engine):
    with Session(engine) as s:
        s.add(_record())
        s.commit()
        row = s.exec(select(DecisionRecord)).one()
        row.verdict = "RED"
        s.add(row)
        with pytest.raises(DatabaseError, match="append-only"):
            s.commit()


@pytest.mark.parametrize("sql", ["UPDATE decision_event SET action='x'", "DELETE FROM decision_event"])
def test_event_rejects_update_and_delete(engine, sql):
    with Session(engine) as s:
        s.add(_record())
        s.commit()
        s.add(DecisionEvent(decision_id=1, kind="outcome", note="cleared"))
        s.commit()
        with pytest.raises(DatabaseError, match="append-only"):
            s.exec(text(sql))
