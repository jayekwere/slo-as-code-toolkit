import json
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from sloctl.api import APIError, Client
from sloctl.cli import app
from sloctl.models import Service, desired, read
from sloctl.reconcile import Conflict, apply, fingerprint, lock, plan
from sloctl.reports import render
from sloctl.simulator import Simulator


@pytest.fixture
def service():
    return read(Path("examples/public-api.yaml"))


@pytest.fixture
def client(tmp_path):
    sim = Simulator(tmp_path / "state.db")
    c = Client(transport=sim.transport, writable=True, sleep=lambda _: None)
    yield c
    c.close()
    sim.close()


def test_reconciliation(client, service, tmp_path):
    first = plan(client, [service])
    assert len(first) == 3
    assert len(apply(client, [service], fingerprint(first), tmp_path / "audit")) == 3
    assert all(c["action"] == "noop" for c in plan(client, [service]))
    assert apply(client, [service], fingerprint(plan(client, [service])), tmp_path / "audit") == []
    service.target = 99.99
    changed = plan(client, [service])
    assert changed[0]["action"] == "update"
    apply(client, [service], fingerprint(changed), tmp_path / "audit")
    assert all(c["action"] == "noop" for c in plan(client, [service]))


def test_stale(client, service, tmp_path):
    digest = fingerprint(plan(client, [service]))
    client.save("slo", desired(service))
    with pytest.raises(Conflict):
        apply(client, [service], digest, tmp_path / "audit")


def test_ownership(client, service):
    payload = desired(service)
    payload["tags"].remove("managed-by:sloctl")
    client.save("slo", payload)
    with pytest.raises(Conflict):
        plan(client, [service])


def test_duplicate(client, service):
    client.save("slo", desired(service))
    client.save("slo", desired(service))
    with pytest.raises(Conflict):
        plan(client, [service])
    with pytest.raises(Conflict):
        plan(client, [service, service])


def test_lock(tmp_path):
    with lock(tmp_path / "lock"), pytest.raises(Conflict), lock(tmp_path / "lock"):
        pass
    assert not (tmp_path / "lock").exists()


@pytest.mark.parametrize("code", [401, 403, 400, 404, 429, 500, 503])
def test_errors(code):
    calls = []
    sleeps = []

    def handler(req):
        calls.append(req)
        return httpx.Response(code, json={"errors": ["SECRET"]})

    c = Client(transport=httpx.MockTransport(handler), sleep=sleeps.append)
    with pytest.raises(APIError) as error:
        c.list("slo")
    assert "SECRET" not in str(error.value)
    assert len(calls) == (4 if code in (429, 500, 503) else 1)
    c.close()


def test_retry_after():
    delays = []
    calls = []

    def handler(req):
        calls.append(req)
        return (
            httpx.Response(429, headers={"retry-after": "999999"})
            if len(calls) < 3
            else httpx.Response(200, json={"data": []})
        )

    c = Client(transport=httpx.MockTransport(handler), sleep=delays.append)
    assert c.list("slo") == []
    assert delays == [5, 5]
    c.close()


@pytest.mark.parametrize("write", [False, True])
def test_timeout(write, service):
    calls = []

    def handler(req):
        calls.append(req)
        raise httpx.ReadTimeout("SECRET", request=req)

    c = Client(transport=httpx.MockTransport(handler), sleep=lambda _: None, writable=True)
    with pytest.raises(APIError):
        c.save("slo", desired(service)) if write else c.list("slo")
    assert len(calls) == (1 if write else 4)
    c.close()


def test_readonly(service):
    c = Client()
    with pytest.raises(APIError):
        c.save("slo", desired(service))
    c.close()
    with pytest.raises(APIError):
        Client(site="localhost:9000")


@pytest.mark.parametrize("body", [{}, {"data": [{}]}, {"data": "bad"}])
def test_schema(body):
    c = Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body)))
    with pytest.raises(APIError):
        c.list("slo")
    c.close()


def test_partial_failure(client, service, tmp_path):
    original = client.save

    def fail(kind, payload, resource_id=None):
        if kind == "monitor":
            raise APIError("injected")
        return original(kind, payload, resource_id)

    client.save = fail
    with pytest.raises(APIError):
        apply(client, [service], fingerprint(plan(client, [service])), tmp_path / "audit")
    client.save = original
    assert len(client.list("slo")) == 1
    apply(client, [service], fingerprint(plan(client, [service])), tmp_path / "audit")
    assert len(client.list("slo")) == 1
    assert len(client.list("monitor")) == 2


@pytest.mark.parametrize(
    "patch",
    [
        {"unknown": 1},
        {"days": 14},
        {"target": 100.0},
        {"target": "99.9"},
        {"good_query": "eval(1)"},
        {"kind": "latency"},
        {"alerts": [{"name": "fast", "long_hours": 1, "short_minutes": 60, "burn_rate": 1.0}]},
        {"target": 10.0},
    ],
)
def test_schema_invalid(service, patch):
    with pytest.raises(ValueError):
        Service.model_validate({**service.model_dump(), **patch})


@pytest.mark.parametrize(
    "text",
    [
        "!!python/object/apply:os.system [echo bad]",
        "name: x\nname: y",
        "x: &a [*a]",
        "a: " + ("[" * 2000) + ("]" * 2000),
        "x" * 65537,
    ],
)
def test_adversarial(tmp_path, text):
    f = tmp_path / "bad.yaml"
    f.write_text(text)
    assert CliRunner().invoke(app, ["apply", str(f), "--yes", "--state", str(tmp_path / "db")]).exit_code == 2
    assert not (tmp_path / "db").exists()


def test_reports():
    assert "&lt;script&gt;" in render({"x": "<script>"}, "html")
    assert "```json" in render({}, "markdown")
    assert json.loads(render({"x": 1}, "json")) == {"x": 1}
    with pytest.raises(ValueError):
        render({}, "bad")


def test_cli(tmp_path):
    runner = CliRunner()
    f = "examples/public-api.yaml"
    state = str(tmp_path / "db")
    assert runner.invoke(app, ["validate", f]).exit_code == 0
    assert runner.invoke(app, ["plan", f, "--state", state]).exit_code == 0
    assert runner.invoke(app, ["diff", f, "--state", state]).exit_code == 3
    assert runner.invoke(app, ["apply", f, "--state", state], input="n\n").exit_code == 2
    assert (
        runner.invoke(
            app, ["apply", f, "--state", state, "--yes", "--audit", str(tmp_path / "audit")]
        ).exit_code
        == 0
    )
    assert runner.invoke(app, ["drift", f, "--state", state]).exit_code == 0
    assert runner.invoke(app, ["simulate", f]).exit_code == 0
    assert runner.invoke(app, ["simulate", f, "--good", "-1"]).exit_code == 2
    assert runner.invoke(app, ["simulate", f, "--short-good", "1"]).exit_code == 2
    for format in ["html", "markdown", "json"]:
        assert (
            runner.invoke(
                app, ["export", f, "--output", str(tmp_path / format), "--format", format]
            ).exit_code
            == 0
        )
    assert runner.invoke(app, ["export", f, "--output", str(tmp_path / "html")]).exit_code == 2
    assert runner.invoke(app, ["apply", f, "--live", "--yes"]).exit_code == 2
    assert runner.invoke(app, ["demo", "--output-dir", str(tmp_path / "demo")]).exit_code == 0
