import json
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from sloctl.api import APIError, Client
from sloctl.cli import app
from sloctl.models import Service, desired, read
from sloctl.reconcile import Conflict, apply, fingerprint, plan
from sloctl.security import redact
from sloctl.simulator import Simulator


@pytest.fixture
def service():
    return read(Path("examples/public-api.yaml"))


def test_json_and_latency(service):
    assert read(Path("examples/auth-api.json")).target == 99.95
    data = service.model_dump()
    data.update(kind="latency", latency_threshold_ms=250.0)
    assert Service.model_validate(data).kind == "latency"
    for days in (7, 30, 90):
        assert (
            desired(Service.model_validate({**data, "days": days}))["thresholds"][0]["timeframe"]
            == f"{days}d"
        )


@pytest.mark.parametrize(
    "patch",
    [
        {"good_query": "sum:public_api.total{*}.as_count()"},
        {"alerts": [{"name": "x", "long_hours": 1, "short_minutes": 5, "burn_rate": 1.0}] * 2},
    ],
)
def test_extra_validation(service, patch):
    with pytest.raises(ValueError):
        Service.model_validate({**service.model_dump(), **patch})


@pytest.mark.parametrize("content", [b"\xff", b"[]", b"{[bad]: 1}", b'{"version": 1, "version": 2}'])
def test_bad_bytes(tmp_path, content):
    path = tmp_path / "bad"
    path.write_bytes(content)
    assert CliRunner().invoke(app, ["validate", str(path)]).exit_code == 2


def test_secret_redaction(monkeypatch):
    monkeypatch.setenv("DD_API_KEY", "fake-sensitive-value")
    assert redact({"api_key": "x", "nested": ["fake-sensitive-value"]}) == {
        "api_key": "[REDACTED]",
        "nested": ["[REDACTED]"],
    }
    assert redact(1) == 1


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"not-json"),
        httpx.Response(200, content=b"x" * 4_000_001),
        httpx.Response(302, headers={"location": "https://example.com"}),
    ],
)
def test_response_guards(response):
    c = Client(transport=httpx.MockTransport(lambda _: response))
    with pytest.raises(APIError):
        c.list("slo")
    c.close()


def test_bad_retry_header():
    sleeps = []
    c = Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(429, headers={"retry-after": "bad"})),
        sleep=sleeps.append,
    )
    with pytest.raises(APIError):
        c.list("slo")
    assert sleeps == [1, 1, 1]
    c.close()


@pytest.mark.parametrize("body", [{"data": []}, {"data": [{}, {}]}, {"data": [{"id": "../bad"}]}])
def test_save_schema(service, body):
    c = Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body)), writable=True)
    with pytest.raises(APIError):
        c.save("slo", desired(service))
    with pytest.raises(APIError):
        c.save("slo", desired(service), "../bad")
    c.close()


def test_pagination(service):
    payload = {**desired(service), "id": "abc"}
    paths = []

    def handle(req):
        paths.append(str(req.url))
        return httpx.Response(200, json={"data": [payload] * 1000 if len(paths) == 1 else []})

    c = Client(transport=httpx.MockTransport(handle))
    assert len(c.list("slo")) == 1000
    assert "offset=1000" in paths[-1]
    c.close()


def test_concurrent_remote_change(tmp_path, service):
    sim = Simulator(tmp_path / "db")
    c = Client(transport=sim.transport, writable=True)
    first = plan(c, [service])
    original = c.list
    calls = 0

    def racing(kind):
        nonlocal calls
        calls += 1
        if calls == 3:
            c.save("slo", desired(service))
        return original(kind)

    c.list = racing
    with pytest.raises(Conflict):
        apply(c, [service], fingerprint(first), tmp_path / "audit")
    c.close()
    sim.close()


def test_cli_failure_exits(tmp_path, monkeypatch):
    runner = CliRunner()
    f = "examples/public-api.yaml"
    assert runner.invoke(app, ["validate", f, f]).exit_code == 2
    monkeypatch.delenv("DD_API_KEY", raising=False)
    monkeypatch.delenv("DD_APP_KEY", raising=False)
    assert runner.invoke(app, ["plan", f, "--live"]).exit_code == 4
    assert runner.invoke(app, ["plan", f, "--state", str(tmp_path / "no" / "db")]).exit_code == 2
    assert (
        runner.invoke(
            app, ["apply", f, "--state", str(tmp_path / "db"), "--expected", "invalid", "--yes"]
        ).exit_code
        == 5
    )
    output = tmp_path / "plan.json"
    assert (
        runner.invoke(app, ["plan", f, "--state", str(tmp_path / "db"), "--output", str(output)]).exit_code
        == 0
    )
    assert json.loads(output.read_text())["backend"] == "simulator"
    assert runner.invoke(app, ["validate", "examples/invalid/bad-threshold.yaml"]).exit_code == 2
    assert runner.invoke(app, ["--help"]).exit_code == 0


@pytest.mark.parametrize("patch", [{"version": True}, {"version": 1.0}, {"days": 30.0}])
def test_literal_types(service, patch):
    with pytest.raises(ValueError):
        Service.model_validate({**service.model_dump(), **patch})


def test_api_path_guard():
    c = Client()
    with pytest.raises(APIError):
        c.request("GET", "https://example.com/api/v1/slo")
    with pytest.raises(APIError):
        c.request("DELETE", "/api/v1/slo/123")
    c.close()


def test_unrelated_monitor_based_slo(tmp_path, service):
    payload = {"id": "abc", "name": "unrelated", "type": "monitor", "tags": [], "monitor_ids": [123]}

    def handler(req):
        return httpx.Response(200, json={"data": [payload]} if req.url.path.endswith("slo") else [])

    c = Client(transport=httpx.MockTransport(handler))
    assert len(plan(c, [service])) == 3
    c.close()


def test_owned_type_migration(service):
    payload = {**desired(service), "type": "monitor", "id": "abc"}

    def handler(req):
        return httpx.Response(200, json={"data": [payload]} if req.url.path.endswith("slo") else [])

    c = Client(transport=httpx.MockTransport(handler))
    with pytest.raises(Conflict):
        plan(c, [service])
    c.close()


def test_contract_fixture_files(service):
    def handler(req):
        name = "slo-list.json" if req.url.path.endswith("slo") else "monitor-list.json"
        return httpx.Response(200, json=json.loads((Path("tests/fixtures") / name).read_text()))

    c = Client(transport=httpx.MockTransport(handler))
    assert all(change["action"] in ("noop", "create") for change in plan(c, [service]))
    c.close()


def test_ambiguous_write_recovery(tmp_path, service):
    sim = Simulator(tmp_path / "db")
    c = Client(transport=sim.transport, writable=True)
    original = c.save

    def lost_response(kind, payload, resource_id=None):
        original(kind, payload, resource_id)
        raise APIError("transport failure; outcome unknown")

    c.save = lost_response
    with pytest.raises(APIError):
        apply(c, [service], fingerprint(plan(c, [service])), tmp_path / "audit")
    c.save = original
    apply(c, [service], fingerprint(plan(c, [service])), tmp_path / "audit")
    assert len(c.list("slo")) == 1
    c.close()
    sim.close()


def test_unmanaged_resources_are_preserved(tmp_path, service):
    sim = Simulator(tmp_path / "db")
    c = Client(transport=sim.transport, writable=True)
    payload = desired(service)
    payload["tags"] = []
    payload["name"] = "unrelated"
    unrelated = c.save("slo", payload)
    apply(c, [service], fingerprint(plan(c, [service])), tmp_path / "audit")
    assert unrelated in c.list("slo")
    assert len(c.list("slo")) == 2
    c.close()
    sim.close()
