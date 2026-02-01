from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


_DAYS_PER_YEAR = Decimal("365")


def _to_decimal(value: Any, *, field: str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    raise TypeError(f"{field} must be Decimal|int|str|float, got {type(value).__name__}")


def calculate_time_priority_factor(*, created_at: dt.datetime | dt.date, now: dt.datetime) -> Decimal:
    """
    Calculate the PRD time-priority factor (earlier nodes => higher factor).

    PRD reference:
      time_factor = 1 / (1 + (now - created_at).days / 365)
    """
    if isinstance(created_at, dt.date) and not isinstance(created_at, dt.datetime):
        created_at = dt.datetime.combine(created_at, dt.time(0, 0))
    if created_at.tzinfo is None and now.tzinfo is not None:
        created_at = created_at.replace(tzinfo=now.tzinfo)

    delta_days = (now - created_at).days
    if delta_days < 0:
        delta_days = 0

    return Decimal("1") / (Decimal("1") + (Decimal(delta_days) / _DAYS_PER_YEAR))


def calculate_reference_weight(
    *,
    created_at: dt.datetime | dt.date,
    now: dt.datetime,
    citation_count: int,
    creativity_factor: Decimal | int | float | str = Decimal("1"),
) -> Decimal:
    """
    Calculate node reference weight: time_priority_factor × citation_count × creativity_factor.
    """
    if citation_count < 0:
        raise ValueError("citation_count must be >= 0")

    time_factor = calculate_time_priority_factor(created_at=created_at, now=now)
    creativity = _to_decimal(creativity_factor, field="creativity_factor")
    if creativity < 0:
        raise ValueError("creativity_factor must be >= 0")

    return Decimal(citation_count) * time_factor * creativity


@dataclass(frozen=True)
class WeightCalculator:
    now: dt.datetime

    def calculate_node_weight(self, node: Any) -> Decimal:
        return calculate_reference_weight(
            created_at=getattr(node, "created_at"),
            now=self.now,
            citation_count=int(getattr(node, "citation_count")),
            creativity_factor=getattr(node, "creativity_factor", Decimal("1")),
        )

