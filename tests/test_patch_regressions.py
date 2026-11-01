"""Behavioral regressions found during the 0.1.1 review."""

import copy
import json
import threading
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from sloctl.api import APIError, Client
from sloctl.cli import app
from sloctl.models import Service, desired, monitor, read
from sloctl.reconcile import Conflict, apply, fingerprint, plan
from sloctl.reports import render
from sloctl.server import server
from sloctl.simulator import Simulator


@pytest.fixture
def sandbox(tmp_path):
    sim = Simulator(tmp_path / "db")
    client = Client(transport=sim.transport, writable=True)
    yield client
    client.close()
    sim.close()


def services(*names):
    base = read(Path("examples/public-api.yaml")).model_dump()
    return [Service.model_validate({**base, "name": name}) for name in names]


def test_service_prefixes_do_not_corrupt_slo_references(sandbox, tmp_path):
    definitions = services("api", "api-worker", "api-worker-jobs")
    apply(sandbox, definitions, fingerprint(plan(sandbox, definitions)), tmp_path / "audit")
    slos = {s["name"]: s["id"] for s in sandbox.list("slo")}
    for alert in sandbox.list("monitor"):
        name = alert["name"].split(":")[0]
        assert f'burn_rate("{slos[name]}")' in alert["query"]
    assert all(c["action"] == "noop" for c in plan(sandbox, definitions))


def test_monitor_status_changes_do_not_revoke_approval(sandbox, tmp_path):
    definitions = services("api")
    apply(sandbox, definitions, fingerprint(plan(sandbox, definitions)), tmp_path / "audit")
    original = sandbox.list
    counter = 0

    def changing_status(kind):
        nonlocal counter
        counter += 1
        result = copy.deepcopy(original(kind))
        for item in result:
            item["overall_state_modified"] = counter
            item["overall_state"] = "Alert" if counter % 2 else "OK"
        return result

    sandbox.list = changing_status
    digest = fingerprint(plan(sandbox, definitions))
    assert fingerprint(plan(sandbox, definitions)) == digest
    assert apply(sandbox, definitions, digest, tmp_path / "audit") == []


@pytest.mark.parametrize("field", ["query", "tags", "id"])
def test_managed_drift_still_invalidates_approval(sandbox, tmp_path, field):
    definitions = services("api")
    apply(sandbox, definitions, fingerprint(plan(sandbox, definitions)), tmp_path / "audit")
    digest = fingerprint(plan(sandbox, definitions))
    original = sandbox.list

    def change(kind):
        result = copy.deepcopy(original(kind))
        if kind == "slo":
            if field == "query":
                result[0]["query"]["numerator"] = "sum:other.good{*}.as_count()"
            elif field == "tags":
                result[0]["tags"].append("changed:true")
            else:
                result[0]["id"] = "different"
        return result

    sandbox.list = change
    with pytest.raises(Conflict):
        apply(sandbox, definitions, digest, tmp_path / "audit")


def test_multiple_identity_tags_fail_closed(sandbox):
    service = services("api")[0]
    payload = desired(service)
    payload["tags"].append("sloctl-id:other-service")
    sandbox.save("slo", payload)
    with pytest.raises(Conflict, match="ambiguous"):
        plan(sandbox, [service])


@pytest.mark.parametrize("format", ["html", "markdown", "json"])
def test_entire_report_redacts_active_credentials(monkeypatch, format):
    secret = "fictional-sensitive-key"
    monkeypatch.setenv("DD_API_KEY", secret)
    report = render({"services": [{"definition": {"name": secret}}]}, format)
    assert secret not in report
    assert "[REDACTED]" in report


def test_api_handles_deep_json_without_traceback():
    client = Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content="[" * 2000 + "]" * 2000))
    )
    try:
        with pytest.raises(APIError, match="invalid"):
            client.list("slo")
        with pytest.raises(APIError, match="invalid resource kind"):
            client.list("unknown")
    finally:
        client.close()


def test_update_response_cannot_change_identity():
    payload = {**desired(services("api")[0]), "id": "other"}
    client = Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"data": [payload]})), writable=True
    )
    try:
        with pytest.raises(APIError, match="identity mismatch"):
            client.save("slo", payload, "original")
    finally:
        client.close()


def test_simulator_routes_and_malformed_payloads(tmp_path):
    sim = Simulator(tmp_path / "db")
    try:
        for method, path, expected in [
            ("GET", "/other/v1/slo", 404),
            ("POST", "/api/v1/slo/1", 405),
            ("PUT", "/api/v1/slo", 405),
            ("GET", "/api/v1/slo/1/extra", 404),
            ("GET", "/api/v1/slo?offset=-1", 400),
            ("GET", "/api/v1/monitor?page=bad", 400),
        ]:
            assert sim.handle(httpx.Request(method, "http://localhost" + path)).status_code == expected
        service = services("api")[0]
        c = Client(transport=sim.transport, writable=True)
        created = c.save("slo", desired(service))
        malformed = monitor(service, service.alerts[0], created["id"])
        malformed["options"]["thresholds"] = []
        assert (
            sim.handle(httpx.Request("POST", "http://localhost/api/v1/monitor", json=malformed)).status_code
            == 400
        )
        assert (
            sim.handle(
                httpx.Request("POST", "http://localhost/api/v1/slo", content="[" * 2000 + "]" * 2000)
            ).status_code
            == 400
        )
        assert (
            sim.handle(httpx.Request("GET", "http://localhost/api/v1/slo/" + created["id"])).json()["data"][
                0
            ]["id"]
            == created["id"]
        )
        c.close()
    finally:
        sim.close()


def test_browser_origin_host_and_content_type_are_rejected(tmp_path):
    httpd = server(tmp_path / "db", 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{httpd.server_port}", trust_env=False, timeout=2) as c:
            payload = desired(services("api")[0])
            assert (
                c.post(
                    "/api/v1/slo", json=payload, headers={"Origin": "https://untrusted.invalid"}
                ).status_code
                == 403
            )
            assert (
                c.post("/api/v1/slo", json=payload, headers={"Host": "untrusted.invalid"}).status_code == 403
            )
            assert (
                c.post(
                    "/api/v1/slo", content=json.dumps(payload), headers={"Content-Type": "text/plain"}
                ).status_code
                == 415
            )
            assert c.get("/api/v1/slo").json()["data"] == []
            assert c.post("/api/v1/slo", json=payload).status_code == 200
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=3)


def test_demo_existing_directory_is_input_error(tmp_path):
    assert CliRunner().invoke(app, ["demo", "--output-dir", str(tmp_path)]).exit_code == 2


def test_unavailable_audit_fails_before_any_mutation(sandbox, tmp_path):
    definitions = services("api")
    with pytest.raises(OSError):
        apply(sandbox, definitions, fingerprint(plan(sandbox, definitions)), tmp_path / "missing" / "audit")
    assert sandbox.list("slo") == []
    assert sandbox.list("monitor") == []


def test_bad_response_encoding_is_sanitized():
    def broken(_):
        raise httpx.DecodingError("fictional-sensitive-detail")

    client = Client(transport=httpx.MockTransport(broken))
    try:
        with pytest.raises(APIError, match="invalid API response encoding") as error:
            client.list("slo")
        assert "fictional-sensitive-detail" not in str(error.value)
    finally:
        client.close()


def assert_svg_is_self_contained(data):
    import re
    import xml.etree.ElementTree as ET

    root = ET.fromstring(data)
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    for element in root.iter():
        assert element.tag.split("}")[-1] not in {"script", "foreignObject", "image", "use", "a"}
        assert not any(key.lower().startswith("on") or key.endswith("href") for key in element.attrib)
        if element.tag.endswith("}style"):
            css = element.text or ""
            assert "@font-face" not in css and "@import" not in css
            for target in re.findall(r'url\(\s*[\'"]?([^\s\)\'"]+)', css):
                assert target.startswith("#")
    return root


def test_demo_svg_has_no_network_dependencies(tmp_path):
    output = tmp_path / "demo"
    result = CliRunner().invoke(app, ["demo", "--output-dir", str(output)])
    assert result.exit_code == 0, result.output
    root = assert_svg_is_self_contained((output / "terminal.svg").read_text())
    text = "".join(root.itertext()).replace("\u00a0", " ")
    assert "Verified:" in text and "zero drift" in text and "public-api" in text


def test_checked_in_svg_evidence_has_no_network_dependencies():
    paths = list(Path("evidence").rglob("*.svg"))
    assert paths
    for path in paths:
        assert_svg_is_self_contained(path.read_text())
