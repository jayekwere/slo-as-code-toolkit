from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from sloctl.math import alert_state, budget, window_counts
from sloctl.models import read


@pytest.mark.parametrize("target", [99.9, 99.95, 99.5])
@pytest.mark.parametrize("total", [0, 1, 10000])
def test_budget(target, total):
    result = budget(target, total, total)
    assert result["bad_events"] == 0
    assert result["burn_rate"] == (0 if total else None)


@pytest.mark.parametrize("good,total", [(-1, 1), (2, 1), (0, -1), (True, 1), (1.0, 2)])
def test_invalid(good, total):
    with pytest.raises(ValueError):
        budget(99.9, good, total)


@pytest.mark.parametrize("target", [0, 100, -1, float("nan"), float("inf")])
def test_bad_target(target):
    with pytest.raises(ValueError):
        budget(target, 1, 1)


def test_exact_allowance():
    b = budget(99.9, 9990, 10000)
    assert b["allowed_bad_events"] == 10
    assert b["burn_rate"] == 1
    assert b["remaining_bad_events"] == 0


@pytest.mark.parametrize("path", list(Path("examples").glob("*.yaml")))
def test_examples(path):
    assert read(path).days == 30


def test_alerts():
    a = read(Path("examples/public-api.yaml")).alerts[0]
    assert alert_state(99.9, a, (9800, 10000), (9800, 10000)) == "ALERT"
    assert alert_state(99.9, a, (10000, 10000), (9800, 10000)) == "OK"
    assert alert_state(99.9, a, (0, 0), (9800, 10000)) == "NO_DATA"
    assert alert_state(99.9, a, (9800, 10000), (9800, 10000), False) == "NO_DATA"
    assert alert_state(99.9, a, (9856, 10000), (9856, 10000)) == "OK"


def test_window_boundaries():
    end = datetime(2026, 1, 1, tzinfo=UTC)
    samples = [(end - timedelta(minutes=i), 99, 100) for i in range(6)]
    assert window_counts(samples, end, 5) == (495, 500, True)
    assert window_counts(samples[2:], end, 5) == (396, 400, False)
    with pytest.raises(ValueError):
        window_counts(samples + samples, end, 5)
    with pytest.raises(ValueError):
        window_counts([], end.replace(tzinfo=None), 5)
    with pytest.raises(ValueError):
        window_counts([(end + timedelta(minutes=1), 1, 1)], end, 5)
    with pytest.raises(ValueError):
        window_counts([(end - timedelta(seconds=1), 1, 1)], end, 5)
