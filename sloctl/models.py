"""Strict versioned definitions and bounded, non-executable parsing."""

import re
from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Alert(Strict):
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{0,40}$")
    long_hours: int = Field(ge=1, le=48)
    short_minutes: int = Field(ge=1)
    burn_rate: float = Field(gt=0)

    @model_validator(mode="after")
    def windows(self) -> Self:
        if self.short_minutes >= self.long_hours * 60:
            raise ValueError("short window must be less than long window")
        return self


class Service(Strict):
    version: Literal[1]
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{0,62}$")
    kind: Literal["availability", "success", "latency"]
    target: float = Field(gt=0, lt=100)
    days: Literal[7, 30, 90]
    good_query: str = Field(min_length=1, max_length=2048)
    total_query: str = Field(min_length=1, max_length=2048)
    latency_threshold_ms: float | None = Field(default=None, gt=0)
    alerts: list[Alert] = Field(
        default_factory=lambda: [
            Alert(name="fast", long_hours=1, short_minutes=5, burn_rate=14.4),
            Alert(name="slow", long_hours=6, short_minutes=30, burn_rate=6.0),
        ],
        max_length=10,
    )

    @field_validator("version", "days", mode="before")
    @classmethod
    def integer_literal(cls, value: Any) -> int:
        if type(value) is not int:
            raise ValueError("version and days require integers")
        return value

    @model_validator(mode="after")
    def consistency(self) -> Self:
        pattern = r"sum:[a-zA-Z][a-zA-Z0-9_.]*\{[a-zA-Z0-9_:*.,/=-]+\}\.as_count\(\)"
        if any(not re.fullmatch(pattern, q) for q in [self.good_query, self.total_query]):
            raise ValueError("only summed count metrics with explicit scopes are supported")
        if self.good_query == self.total_query:
            raise ValueError("good and total queries must differ")
        if self.kind == "latency" and self.latency_threshold_ms is None:
            raise ValueError("latency requires a threshold and a precomputed good-event counter")
        if len({a.name for a in self.alerts}) != len(self.alerts):
            raise ValueError("duplicate alert name")
        if any(a.burn_rate > 1 / (1 - self.target / 100) for a in self.alerts):
            raise ValueError("unreachable burn threshold")
        return self


class SafeLoader(yaml.SafeLoader):
    def compose_node(self, parent: Any, index: Any) -> Any:
        if self.check_event(yaml.AliasEvent):
            raise ValueError("YAML aliases are not supported")
        return super().compose_node(parent, index)


def mapping(loader: SafeLoader, node: yaml.MappingNode, deep: bool = False) -> dict[str, Any]:
    result = {}
    for key, value in node.value:
        name = loader.construct_object(key, deep=deep)
        if not isinstance(name, str) or name in result:
            raise ValueError("duplicate or non-string key")
        result[name] = loader.construct_object(value, deep=deep)
    return result


SafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)


def read(path: Path) -> Service:
    with path.open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("definition exceeds 64 KiB")
    try:
        data = yaml.load(raw.decode("utf-8"), Loader=SafeLoader)
    except (RecursionError, UnicodeError, yaml.YAMLError) as exc:
        raise ValueError("invalid definition") from exc
    return Service.model_validate(data)


def desired(s: Service) -> dict[str, Any]:
    return {
        "name": s.name,
        "type": "metric",
        "tags": ["managed-by:sloctl", f"sloctl-id:{s.name}"],
        "query": {"numerator": s.good_query, "denominator": s.total_query},
        "thresholds": [{"timeframe": f"{s.days}d", "target": s.target}],
    }


def monitor(s: Service, a: Alert, slo_id: str) -> dict[str, Any]:
    return {
        "name": f"{s.name}: {a.name}",
        "type": "slo alert",
        "query": f'burn_rate("{slo_id}").over("{s.days}d").long_window("{a.long_hours}h").short_window("{a.short_minutes}m") > {a.burn_rate}',
        "message": "Investigate the service error budget. See the service runbook.",
        "tags": ["managed-by:sloctl", f"sloctl-id:{s.name}:{a.name}"],
        "options": {"thresholds": {"critical": a.burn_rate}, "notify_no_data": False},
    }
