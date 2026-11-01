"""Ownership-scoped planning and fail-closed sequential reconciliation."""

import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .api import APIError, Client
from .models import Service, desired, monitor


class Conflict(APIError):
    pass


def owned(resources: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    matches = [r for r in resources if f"sloctl-id:{key}" in r["tags"]]
    if len(matches) > 1 or (matches and "managed-by:sloctl" not in matches[0]["tags"]):
        raise Conflict("duplicate identity or ownership collision")
    return matches[0] if matches else None


def comparable(remote: dict[str, Any], wanted: dict[str, Any]) -> dict[str, Any]:
    result = {k: remote.get(k) for k in wanted}
    if "tags" in result:
        result["tags"] = sorted(remote["tags"])
    if "options" in wanted and isinstance(result["options"], dict):
        result["options"] = {k: result["options"].get(k) for k in wanted["options"]}
    return result


def change(kind: str, key: str, wanted: dict[str, Any], remote: dict[str, Any] | None) -> dict[str, Any]:
    if remote is not None and remote["type"] != wanted["type"]:
        raise Conflict("owned resource type differs; manual migration required")
    canonical = {**wanted, "tags": sorted(wanted["tags"])}
    return {
        "kind": kind,
        "key": key,
        "action": "create"
        if remote is None
        else ("noop" if comparable(remote, wanted) == canonical else "update"),
        "id": remote["id"] if remote else None,
        "desired": wanted,
        "before": remote,
    }


def plan(client: Client, services: list[Service]) -> list[dict[str, Any]]:
    slos = client.list("slo")
    monitors = client.list("monitor")
    changes = []
    if len({s.name for s in services}) != len(services):
        raise Conflict("duplicate service definition")
    for s in services:
        remote = owned(slos, s.name)
        changes.append(change("slo", s.name, desired(s), remote))
        for a in s.alerts:
            key = f"{s.name}:{a.name}"
            changes.append(
                change(
                    "monitor",
                    key,
                    monitor(s, a, str(remote["id"]) if remote else f"REF:{s.name}"),
                    owned(monitors, key),
                )
            )
    return changes


def fingerprint(changes: list[dict[str, Any]]) -> str:
    return hashlib.sha256(json.dumps(changes, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@contextmanager
def lock(path: Path) -> Iterator[None]:
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise Conflict("another apply holds the local lock; inspect recovery guide") from None
    try:
        os.close(fd)
        yield
    finally:
        path.unlink()


def apply(client: Client, services: list[Service], expected: str, audit: Path) -> list[dict[str, Any]]:
    changes = plan(client, services)
    if fingerprint(changes) != expected:
        raise Conflict("remote state changed since approval; re-plan")
    events = []
    ids: dict[str, str | int] = {}
    for c in changes:
        # Recheck the exact resource before each write; Datadog lacks atomic CAS.
        current = owned(client.list(c["kind"]), c["key"])
        if current != c["before"]:
            raise Conflict("concurrent remote change detected")
        payload = json.loads(json.dumps(c["desired"]))
        if c["kind"] == "monitor":
            for name, rid in ids.items():
                payload["query"] = payload["query"].replace(f"REF:{name}", str(rid))
        if c["action"] == "noop":
            assert current is not None
            saved = current
        else:
            saved = client.save(c["kind"], payload, c["id"])
            event = {"kind": c["kind"], "key": c["key"], "action": c["action"], "id": saved["id"]}
            with audit.open("a") as stream:
                stream.write(json.dumps(event) + "\n")
            events.append(event)
        if c["kind"] == "slo":
            ids[c["key"]] = saved["id"]
    if any(c["action"] != "noop" for c in plan(client, services)):
        raise Conflict("post-apply verification found drift; inspect and re-plan")
    return events
