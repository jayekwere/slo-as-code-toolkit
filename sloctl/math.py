"""Event-based reliability math. Observations are half-open [start, end)."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from .models import Alert


def budget(target: float, good: int, total: int) -> dict[str, Any]:
    if (
        isinstance(good, bool)
        or isinstance(total, bool)
        or not isinstance(good, int)
        or not isinstance(total, int)
        or not 0 < target < 100
        or total < 0
        or not 0 <= good <= total
    ):
        raise ValueError("invalid target or event counts")
    allowance = Decimal(total) * (1 - Decimal(str(target)) / 100)
    bad = total - good
    return {
        "availability": 100 * good / total if total else None,
        "allowed_bad_events": float(allowance),
        "bad_events": bad,
        "remaining_bad_events": float(allowance - bad),
        "consumption": float(Decimal(bad) / allowance) if allowance else None,
        "burn_rate": float(Decimal(bad) / allowance) if allowance else None,
        "status": "observed" if total else "no_data",
    }


def alert_state(
    target: float, alert: Alert, short: tuple[int, int], long: tuple[int, int], complete: bool = True
) -> str:
    sb = budget(target, *short)["burn_rate"]
    lb = budget(target, *long)["burn_rate"]
    if not complete or sb is None or lb is None:
        return "NO_DATA"
    return "ALERT" if sb > alert.burn_rate and lb > alert.burn_rate else "OK"


def window_counts(
    samples: list[tuple[datetime, int, int]], end: datetime, minutes: int, cadence_minutes: int = 1
) -> tuple[int, int, bool]:
    if end.tzinfo is None or minutes <= 0 or cadence_minutes <= 0 or minutes % cadence_minutes:
        raise ValueError("timezone-aware aligned window required")
    start = end - timedelta(minutes=minutes)
    seen = set()
    good = total = 0
    for timestamp, g, t in samples:
        budget(99.9, g, t)
        if timestamp.tzinfo is None or timestamp > end:
            raise ValueError("invalid observation timestamp")
        if start <= timestamp < end:
            if timestamp in seen or (end - timestamp).total_seconds() % (60 * cadence_minutes):
                raise ValueError("duplicate or unaligned sample")
            seen.add(timestamp)
            good += g
            total += t
    return good, total, len(seen) == minutes // cadence_minutes
