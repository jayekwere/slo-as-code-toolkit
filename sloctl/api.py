"""Bounded Datadog HTTP operations. Writes are never retried."""

import json
import os
import re
import time
from collections.abc import Callable
from typing import Any, Self

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

SITES = {
    s: "https://api." + s
    for s in (
        "datadoghq.com",
        "us3.datadoghq.com",
        "us5.datadoghq.com",
        "datadoghq.eu",
        "ap1.datadoghq.com",
        "ap2.datadoghq.com",
        "ddog-gov.com",
        "us2.ddog-gov.com",
        "uk1.datadoghq.com",
    )
}


class APIError(Exception):
    pass


class Resource(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    id: str | int
    name: str
    type: str
    tags: list[str]
    query: dict[str, Any] | str | None = None
    thresholds: list[dict[str, Any]] | None = None
    options: dict[str, Any] | None = None

    @model_validator(mode="after")
    def identity(self) -> Self:
        if not re.fullmatch(r"[a-zA-Z0-9]{1,128}", str(self.id)):
            raise ValueError("invalid resource ID")
        if self.type == "metric":
            if (
                not isinstance(self.query, dict)
                or not all(isinstance(self.query.get(k), str) for k in ("numerator", "denominator"))
                or not self.thresholds
            ):
                raise ValueError("invalid metric SLO contract")
            for threshold in self.thresholds:
                if (
                    threshold.get("timeframe") not in ("7d", "30d", "90d")
                    or type(threshold.get("target")) not in (int, float)
                    or not 0 < threshold["target"] < 100
                ):
                    raise ValueError("invalid SLO threshold")
        elif self.type not in ("monitor", "time_slice") and not isinstance(self.query, str):
            raise ValueError("invalid monitor query")
        return self


class Client:
    def __init__(
        self,
        site: str = "datadoghq.com",
        transport: httpx.BaseTransport | None = None,
        api_key: str | None = None,
        app_key: str | None = None,
        sleep: Callable[[float], None] = time.sleep,
        writable: bool = False,
    ) -> None:
        if site not in SITES:
            raise APIError("unsupported Datadog site")
        self.writable = writable
        self.sleep = sleep
        self.http = httpx.Client(
            base_url=SITES[site],
            transport=transport,
            timeout=httpx.Timeout(10, connect=3),
            follow_redirects=False,
            trust_env=False,
            headers={
                "DD-API-KEY": api_key or os.getenv("DD_API_KEY", "") or "",
                "DD-APPLICATION-KEY": app_key or os.getenv("DD_APP_KEY", "") or "",
            },
        )

    def close(self) -> None:
        self.http.close()

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        if method not in ("GET", "POST", "PUT") or not re.fullmatch(
            r"/api/v1/(slo|monitor)(/[a-zA-Z0-9]+)?(\?[a-z0-9_=&]+)?", path
        ):
            raise APIError("unsupported API operation")
        if method != "GET" and not self.writable:
            raise APIError("client is read-only")
        for attempt in range(4):
            try:
                with self.http.stream(method, path, json=payload) as response:
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > 4_000_000:
                            raise APIError("API response too large")
            except (httpx.TimeoutException, httpx.TransportError):
                if method == "GET" and attempt < 3:
                    self.sleep(min(2**attempt, 4))
                    continue
                raise APIError(
                    "transport failure; mutation outcome may be unknown; re-plan before retry"
                ) from None
            if (
                method == "GET"
                and (response.status_code == 429 or response.status_code >= 500)
                and attempt < 3
            ):
                try:
                    delay = float(response.headers.get("retry-after", 2**attempt))
                except ValueError:
                    delay = 1
                self.sleep(max(0, min(delay, 5)))
                continue
            if response.status_code >= 300:
                raise APIError(f"Datadog HTTP {response.status_code}; re-plan before retry")
            try:
                return json.loads(content)
            except ValueError:
                raise APIError("invalid API JSON") from None
        raise APIError("retry limit reached")

    def parse(self, item: Any) -> dict[str, Any]:
        try:
            return Resource.model_validate(item).model_dump(exclude_none=True)
        except ValidationError:
            raise APIError("invalid resource response schema") from None

    def list(self, kind: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for page in range(100):
            path = (
                f"/api/v1/{kind}?limit=1000&offset={page * 1000}"
                if kind == "slo"
                else f"/api/v1/monitor?page_size=1000&page={page}"
            )
            raw = self.request("GET", path)
            values = raw.get("data") if kind == "slo" and isinstance(raw, dict) else raw
            if not isinstance(values, list):
                raise APIError("invalid list response")
            items.extend(self.parse(v) for v in values)
            if len(values) < 1000:
                return items
        raise APIError("pagination limit exceeded")

    def save(
        self, kind: str, payload: dict[str, Any], resource_id: str | int | None = None
    ) -> dict[str, Any]:
        if kind not in ("slo", "monitor") or (
            resource_id is not None and not re.fullmatch(r"[a-zA-Z0-9]{1,128}", str(resource_id))
        ):
            raise APIError("invalid resource path")
        path = f"/api/v1/{kind}" + (f"/{resource_id}" if resource_id is not None else "")
        raw = self.request("PUT" if resource_id is not None else "POST", path, payload)
        if kind == "slo":
            if not isinstance(raw, dict) or not isinstance(raw.get("data"), list) or len(raw["data"]) != 1:
                raise APIError("invalid SLO response")
            raw = raw["data"][0]
        return self.parse(raw)
