"""Escaped portable reports with synthetic-data labels."""

import html
import json
from pathlib import Path
from typing import Any

from .security import redact


def render(data: dict[str, Any], format: str) -> str:
    data = redact(data)
    text = json.dumps(data, indent=2, sort_keys=True)
    if format == "json":
        return text + "\n"
    if format == "markdown":
        return (
            "# Reliability report\n\nGenerated configuration and synthetic observations. Not live service reliability.\n\n```json\n"
            + text
            + "\n```\n"
        )
    if format == "html":
        rows = []
        for service in data.get("services", []):
            definition = service.get("definition", {})
            budget = service.get("budget", {})
            values = [
                definition.get("name"),
                definition.get("kind"),
                str(definition.get("target")) + "%",
                str(definition.get("days")) + "d",
                budget.get("allowed_bad_events"),
                budget.get("remaining_bad_events"),
                budget.get("burn_rate"),
            ]
            cells = "".join("<td>" + html.escape(str(value)) + "</td>" for value in values)
            rows.append("<tr>" + cells + "</tr>")
        table = (
            "<div class='scroll'><table><thead><tr><th>Service</th><th>SLI</th><th>Target</th><th>Window</th><th>Budget events</th><th>Remaining</th><th>Burn rate</th></tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table></div>"
            if rows
            else ""
        )
        return (
            "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>Reliability report</title><style>body{background:#0d1423;color:#dce8f6;font:16px system-ui;max-width:1100px;margin:3rem auto;padding:1rem}h1{font-size:2.7rem;margin:.4rem 0;color:#72e4bc}p{line-height:1.7;color:#b9c9dc}.label{font-size:.8rem;letter-spacing:.16em;color:#72e4bc}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;margin:2rem 0;background:#172338}th,td{text-align:left;padding:1rem;border-bottom:1px solid #304058}th{color:#72e4bc;font-size:.85rem}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#172338;padding:2rem;border-radius:12px;font-size:.85rem}summary{cursor:pointer;padding:1rem 0}footer{margin-top:2rem;color:#9eafc4}</style></head><body><div class='label'>SLO-AS-CODE TOOLKIT / SYNTHETIC SCENARIO</div><h1>Reliability report</h1><p>Generated configuration and fictional event observations. These values do not represent live service reliability. A negative remaining budget means the observed allowance was exceeded.</p>"
            + table
            + "<details><summary>Inspect definitions, SLOs, monitors, and calculations</summary><pre>"
            + html.escape(text)
            + "</pre></details><footer>Metric SLOs · Explicit approval · Ownership-scoped reconciliation</footer></body></html>"
        )
    raise ValueError("unsupported report format")


def write(path: Path, data: dict[str, Any], format: str) -> None:
    with path.open("x") as stream:
        stream.write(render(data, format))
