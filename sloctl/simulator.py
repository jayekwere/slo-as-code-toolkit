"""Persistent local Datadog contract simulator using the same HTTP client path."""

import json
import re
import sqlite3
from pathlib import Path

import httpx

from .api import Resource


class Simulator:
    def __init__(self, path: Path) -> None:
        self.db = sqlite3.connect(path, timeout=5)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS resources (id INTEGER PRIMARY KEY,kind TEXT NOT NULL,payload TEXT NOT NULL)"
        )
        self.db.commit()
        self.transport = httpx.MockTransport(self.handle)

    def close(self) -> None:
        self.db.close()

    def handle(self, request: httpx.Request) -> httpx.Response:
        parts = request.url.path.split("/")
        if len(parts) < 4 or parts[3] not in ("slo", "monitor"):
            return httpx.Response(404, json={"errors": ["not found"]})
        kind = parts[3]
        rid = parts[4] if len(parts) > 4 else None
        if request.method == "GET":
            records = [
                json.loads(row[0])
                for row in self.db.execute("SELECT payload FROM resources WHERE kind=? ORDER BY id", (kind,))
            ]
            page = (
                int(request.url.params.get("offset", "0"))
                if kind == "slo"
                else int(request.url.params.get("page", "0")) * 1000
            )
            records = records[page : page + 1000]
            return httpx.Response(200, json={"data": records} if kind == "slo" else records)
        if request.method not in ("POST", "PUT"):
            return httpx.Response(405)
        if len(request.content) > 65536:
            return httpx.Response(413)
        try:
            payload = json.loads(request.content)
        except ValueError:
            return httpx.Response(400)
        if not isinstance(payload, dict):
            return httpx.Response(400)
        try:
            resource = Resource.model_validate({**payload, "id": rid or "pending"})
            if kind == "slo" and resource.type != "metric":
                raise ValueError("unsupported SLO type")
            if kind == "monitor":
                match = re.fullmatch(
                    r'burn_rate\("([a-zA-Z0-9]+)"\)\.over\("(7d|30d|90d)"\)\.long_window\("([0-9]+)h"\)\.short_window\("([0-9]+)m"\) > ([0-9.eE+-]+)',
                    str(resource.query),
                )
                if resource.type != "slo alert" or match is None:
                    raise ValueError("unsupported monitor query")
                slo_id, days, long_hours, short_minutes, threshold = match.groups()
                row = self.db.execute(
                    "SELECT payload FROM resources WHERE id=? AND kind='slo'", (slo_id,)
                ).fetchone()
                if row is None:
                    raise ValueError("SLO reference not found")
                slo = json.loads(row[0])
                if (
                    days != slo["thresholds"][0]["timeframe"]
                    or not 1 <= int(long_hours) <= 48
                    or not 1 <= int(short_minutes) < int(long_hours) * 60
                ):
                    raise ValueError("invalid monitor windows")
                maximum = 1 / (1 - slo["thresholds"][0]["target"] / 100)
                critical = (resource.options or {}).get("thresholds", {}).get("critical")
                if not 0 < float(threshold) <= maximum or critical != float(threshold):
                    raise ValueError("invalid monitor thresholds")
        except ValueError:
            return httpx.Response(400, json={"errors": ["invalid resource"]})
        with self.db:
            if rid:
                row = self.db.execute(
                    "SELECT id FROM resources WHERE id=? AND kind=?", (rid, kind)
                ).fetchone()
                if row is None:
                    return httpx.Response(404)
                number = int(rid)
            else:
                cur = self.db.execute("INSERT INTO resources(kind,payload) VALUES (?,?)", (kind, "{}"))
                assert cur.lastrowid is not None
                number = cur.lastrowid
            payload["id"] = str(number) if kind == "slo" else number
            self.db.execute("UPDATE resources SET payload=? WHERE id=?", (json.dumps(payload), number))
        return httpx.Response(200, json={"data": [payload], "errors": []} if kind == "slo" else payload)
