"""The transaction boundary is explicit and cannot silently commit."""

from __future__ import annotations

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from personal_brain_infra.persistence.unit_of_work import UnitOfWork


@pytest.fixture
def database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    tables = {
        name: Table(name, metadata, Column("id", String(36), primary_key=True), Column("version", Integer))
        for name in ("canonical", "idempotency", "jobs", "audit")
    }
    metadata.create_all(engine)
    yield sessionmaker(engine, class_=Session, expire_on_commit=False), tables
    engine.dispose()


def counts(factory, tables):
    with factory() as session:
        return {name: session.scalar(select(func.count()).select_from(table)) for name, table in tables.items()}


def test_all_effects_commit_together(database):
    factory, tables = database
    with UnitOfWork(factory) as uow:
        for table in tables.values():
            uow.session.execute(table.insert().values(id="same-request", version=1))
        uow.commit()
    assert counts(factory, tables) == {name: 1 for name in tables}


def test_exit_without_commit_rolls_back_every_effect(database):
    factory, tables = database
    with UnitOfWork(factory) as uow:
        for table in tables.values():
            uow.session.execute(table.insert().values(id="same-request", version=1))
    assert counts(factory, tables) == {name: 0 for name in tables}


def test_commit_is_explicit_and_only_once(database):
    factory, tables = database
    uow = UnitOfWork(factory)
    with pytest.raises(RuntimeError, match="not active"):
        uow.commit()
    with uow:
        uow.session.execute(tables["audit"].insert().values(id="one", version=1))
        uow.commit()
        with pytest.raises(RuntimeError, match="already committed"):
            uow.commit()
    with pytest.raises(RuntimeError, match="entered twice"):
        with uow:
            pass
    assert counts(factory, tables)["audit"] == 1


def test_failed_commit_rolls_back_uncommitted_effects(database):
    factory, tables = database
    with pytest.raises(Exception):
        with UnitOfWork(factory) as uow:
            uow.session.execute(tables["canonical"].insert().values(id="duplicate", version=1))
            uow.session.execute(tables["canonical"].insert().values(id="duplicate", version=1))
            uow.commit()
    assert counts(factory, tables) == {name: 0 for name in tables}
