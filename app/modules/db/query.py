from collections.abc import Iterable, Mapping
from typing import Any, Literal

from sqlalchemy import ColumnElement


def sort_options(columns: Iterable[str]) -> Any:
    """The values of a ``sort`` parameter: a column name, with ``-`` for descending."""
    return Literal[tuple(f"{sign}{name}" for name in columns for sign in ("", "-"))]  # type: ignore[valid-type]


def ordered(columns: Mapping[str, Any], sort: str) -> ColumnElement[Any]:
    """The order for a ``sort`` value; empty values go last when descending."""
    column = columns[sort.lstrip("-")]
    return column.desc().nulls_last() if sort.startswith("-") else column.asc().nulls_first()


def contains(column: Any, search: str) -> ColumnElement[bool]:
    """``column`` holds ``search`` in any letter case; ``%`` and ``_`` are plain characters."""
    escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return column.ilike(f"%{escaped}%", escape="\\")


def listed(raw: str | None, allowed: Iterable[str] | None = None) -> list[str]:
    """Comma-separated filter values; with ``allowed``, unknown ones are ignored."""
    values = [value for value in (raw or "").split(",") if value]
    if allowed is None:
        return values
    known = set(allowed)
    return [value for value in values if value in known]
