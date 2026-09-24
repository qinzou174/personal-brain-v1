"""One request outcome, one database transaction.

Canonical records, idempotency outcomes, queued jobs and audit rows must be
written through the same Session and committed exactly once. A missing commit,
an exception, or a commit failure leaves no partial result.
"""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session


class UnitOfWork:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory
        self.session: Session
        self._committed = False
        self._entered = False

    def __enter__(self) -> Self:
        if self._entered or self._committed:
            raise RuntimeError("unit of work cannot be entered twice")
        self.session = self._session_factory()
        # Establish the outer transaction before idempotency uses a nested
        # savepoint.  This is essential with SQLite's legacy transaction mode
        # and explicit documentation of the production PostgreSQL boundary.
        self.session.begin()
        self._entered = True
        return self

    def commit(self) -> None:
        if not self._entered:
            raise RuntimeError("unit of work is not active")
        if self._committed:
            raise RuntimeError("unit of work is already committed")
        try:
            self.session.commit()
        except BaseException:
            self.session.rollback()
            raise
        self._committed = True

    def rollback(self) -> None:
        if not self._entered:
            raise RuntimeError("unit of work is not active")
        if self._committed:
            raise RuntimeError("committed unit of work cannot be rolled back")
        self.session.rollback()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            if exc_type is not None or not self._committed:
                if not self._committed:
                    self.session.rollback()
        finally:
            self.session.close()
            self._entered = False
