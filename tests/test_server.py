import threading
from pathlib import Path

import httpx

from sloctl.models import desired, monitor, read
from sloctl.server import server


def test_real_loopback_api(tmp_path):
    httpd = server(tmp_path / "db", 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{httpd.server_port}",
            trust_env=False,
            timeout=2,
            headers={"Content-Type": "application/json"},
        ) as c:
            service = read(Path("examples/public-api.yaml"))
            response = c.post("/api/v1/slo", json=desired(service))
            assert response.status_code == 200
            rid = response.json()["data"][0]["id"]
            response = c.post("/api/v1/monitor", json=monitor(service, service.alerts[0], rid))
            assert response.status_code == 200
            assert len(c.get("/api/v1/monitor").json()) == 1
            assert c.get("/api/v1/slo").json()["data"][0]["id"] == rid
            assert c.put("/api/v1/slo/" + rid, json=desired(service)).status_code == 200
            assert c.put("/api/v1/slo/999", json=desired(service)).status_code == 404
            assert c.get("/api/v1/unknown").status_code == 404
            assert c.post("/api/v1/slo", content="x").status_code == 400
            assert c.post("/api/v1/slo", json=[]).status_code == 400
            assert c.post("/api/v1/slo", json={}).status_code == 400
            assert c.post("/api/v1/slo", content="x" * 65537).status_code == 413
            assert (
                c.post("/api/v1/monitor", json=monitor(service, service.alerts[0], "999")).status_code == 400
            )
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=3)
