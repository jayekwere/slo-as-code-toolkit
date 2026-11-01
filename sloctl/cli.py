"""Read-only by default CLI. All mutations require apply and confirmation."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .api import APIError, Client
from .math import alert_state, budget
from .models import Service, desired, monitor, read
from .reconcile import Conflict, fingerprint, lock
from .reconcile import apply as reconcile
from .reconcile import plan as make_plan
from .reports import write
from .security import redact
from .simulator import Simulator

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)
console = Console(record=True)
Files = Annotated[list[Path], typer.Argument(help="One or more YAML or JSON service definitions")]


def load(paths: list[Path]) -> list[Service]:
    try:
        services = [read(p) for p in paths]
        if len({s.name for s in services}) != len(services):
            raise ValueError("duplicate services")
        return services
    except (ValueError, OSError, TypeError, RecursionError):
        console.print(
            "[red]Invalid or unreadable definition. Run validate after correcting the configuration.[/red]"
        )
        raise typer.Exit(2) from None


@contextmanager
def backend(state: Path, live: bool, site: str, writable: bool = False) -> Iterator[Client]:
    simulator = None
    client = None
    try:
        if live:
            import os

            if not os.getenv("DD_API_KEY") or not os.getenv("DD_APP_KEY"):
                raise APIError("DD_API_KEY and DD_APP_KEY are required")
        else:
            simulator = Simulator(state)
        client = Client(site=site, transport=simulator.transport if simulator else None, writable=writable)
        yield client
    except Conflict as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(5) from None
    except APIError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(4) from None
    except (OSError, sqlite3.Error):
        console.print("[red]Local file operation failed[/red]")
        raise typer.Exit(2) from None
    finally:
        if client:
            client.close()
        if simulator:
            simulator.close()


@app.command()
def validate(paths: Files) -> None:
    """Validate all definitions. Exit 0 valid; 2 invalid."""
    services = load(paths)
    table = Table("Service", "SLI", "Target", "Window", "Alerts")
    for s in services:
        table.add_row(s.name, s.kind, f"{s.target}%", f"{s.days}d", str(len(s.alerts)))
    console.print(table)


@app.command()
def plan(
    paths: Files,
    state: Path = Path(".sloctl.db"),
    live: bool = False,
    site: str = "datadoghq.com",
    output: Path | None = None,
) -> None:
    """Read remote state and preview changes. Never mutates API resources."""
    services = load(paths)
    with backend(state, live, site) as client:
        changes = make_plan(client, services)
        data = {
            "backend": "live" if live else "simulator",
            "fingerprint": fingerprint(changes),
            "changes": changes,
        }
        console.print_json(data=redact(data))
        if output:
            write(output, data, "json")


@app.command()
def diff(
    paths: Files, state: Path = Path(".sloctl.db"), live: bool = False, site: str = "datadoghq.com"
) -> None:
    """Report configuration changes. Exit 3 if drift is present."""
    services = load(paths)
    with backend(state, live, site) as client:
        changes = make_plan(client, services)
        table = Table("Resource", "Identity", "Action")
        for c in changes:
            table.add_row(c["kind"], c["key"], c["action"])
        console.print(table)
        if any(c["action"] != "noop" for c in changes):
            raise typer.Exit(3)


@app.command()
def drift(
    paths: Files, state: Path = Path(".sloctl.db"), live: bool = False, site: str = "datadoghq.com"
) -> None:
    """Inspect owned-resource drift, with the same exit codes as diff."""
    diff(paths, state, live, site)


@app.command()
def apply(
    paths: Files,
    state: Path = Path(".sloctl.db"),
    yes: bool = typer.Option(False, "--yes", help="Explicitly confirm the displayed changes"),
    live: bool = False,
    allow_live_mutations: bool = False,
    site: str = "datadoghq.com",
    expected: str | None = None,
    audit: Path = Path("sloctl-audit.jsonl"),
) -> None:
    """Apply explicit changes. Live writes also require --allow-live-mutations."""
    services = load(paths)
    if live and not allow_live_mutations:
        console.print("Live mutation authorization flag is required.")
        raise typer.Exit(2)
    with backend(state, live, site, writable=True) as client, lock(Path(str(state) + ".lock")):
        changes = make_plan(client, services)
        table = Table("Resource", "Identity", "Action")
        for c in changes:
            table.add_row(c["kind"], c["key"], c["action"])
        console.print(table)
        digest = fingerprint(changes)
        if expected and digest != expected:
            raise Conflict("approved fingerprint differs; re-plan")
        if not yes and not typer.confirm("Apply these changes?", default=False):
            raise typer.Exit(2)
        events = reconcile(client, services, digest, audit)
        console.print_json(
            data={"applied": len(events), "verified": True, "backend": "live" if live else "simulator"}
        )


@app.command()
def simulate(
    paths: Files,
    good: int = 9900,
    total: int = 10000,
    short_good: int | None = None,
    short_total: int | None = None,
    incomplete: bool = False,
) -> None:
    """Evaluate fictional short and long observations, never real telemetry."""
    services = load(paths)
    if (short_good is None) != (short_total is None):
        raise typer.Exit(2)
    try:
        for s in services:
            result = budget(s.target, good, total)
            console.print(f"[cyan]{s.name}: SYNTHETIC[/cyan]")
            console.print_json(data=result)
            for a in s.alerts:
                status = alert_state(
                    s.target,
                    a,
                    (
                        short_good if short_good is not None else good,
                        short_total if short_total is not None else total,
                    ),
                    (good, total),
                    not incomplete,
                )
                burn = result["burn_rate"] or 0
                console.print(f"{a.name:8} {'█' * min(30, int(burn)):30} {status} threshold={a.burn_rate:g}")
    except ValueError:
        raise typer.Exit(2) from None


@app.command()
def export(
    paths: Files,
    output: Annotated[Path, typer.Option(help="New report destination")],
    format: str = typer.Option("html", help="html, markdown, or json"),
    good: int = 9900,
    total: int = 10000,
) -> None:
    """Export desired configuration and synthetic budgets; refuses overwrite."""
    services = load(paths)
    try:
        data = {
            "synthetic": True,
            "services": [
                {
                    "definition": s.model_dump(),
                    "slo": desired(s),
                    "monitors": [monitor(s, a, "REF:" + s.name) for a in s.alerts],
                    "budget": budget(s.target, good, total),
                }
                for s in services
            ],
        }
        write(output, data, format)
    except (OSError, ValueError):
        raise typer.Exit(2) from None
    console.print(f"Created {output}")


@app.command()
def demo(output_dir: Path = Path("demo-output")) -> None:
    """Run all three fictional services against a fresh local contract simulator."""
    try:
        output_dir.mkdir(parents=True, exist_ok=False)
    except OSError:
        console.print("A new writable demo output directory is required.")
        raise typer.Exit(2) from None
    paths = [
        Path(__file__).parent / "examples" / f"{name}.yaml"
        for name in ("public-api", "auth-api", "background-processing")
    ]
    services = load(paths)
    state = output_dir / "datadog.db"
    with backend(state, False, "datadoghq.com", writable=True) as client:
        before = make_plan(client, services)
        write(output_dir / "plan.json", {"changes": before}, "json")
        console.print("DEMO: explicit local mutation authorization; no live resources")
        reconcile(client, services, fingerprint(before), output_dir / "audit.jsonl")
        after = make_plan(client, services)
        assert all(c["action"] == "noop" for c in after)
        write(output_dir / "verified.json", {"changes": after}, "json")
    validate(paths)
    table = Table("Service", "Budget / 10k", "Healthy burn", "Degraded burn", "Alert state")
    for service in services:
        healthy = budget(service.target, 10000, 10000)
        degraded = budget(service.target, 9000, 10000)
        states = [alert_state(service.target, a, (9000, 10000), (9000, 10000)) for a in service.alerts]
        table.add_row(
            service.name,
            str(healthy["allowed_bad_events"]),
            str(healthy["burn_rate"]),
            str(degraded["burn_rate"]),
            " / ".join(states),
        )
    console.print("SYNTHETIC: healthy 100% success; degraded 90% success in both windows")
    console.print(table)
    console.print("Burn preview: each block is 10× burn, capped at 30 blocks")
    for service in services:
        burn = budget(service.target, 9000, 10000)["burn_rate"]
        console.print(f"{service.name:22} {'█' * min(30, int(burn / 10))} {burn:g}×")
    changes = Table("Resource", "Identity", "Before", "Verified")
    for initial, final in zip(before, after, strict=True):
        changes.add_row(initial["kind"], initial["key"], initial["action"], final["action"])
    console.print(changes)
    export(paths, output_dir / "report.html", "html", good=9000)
    export(paths, output_dir / "report.md", "markdown", good=9000)
    console.print("Verified: 3 SLOs, 6 monitors, zero drift")
    console.save_svg(str(output_dir / "terminal.svg"), title="sloctl offline demonstration")


@app.command()
def serve(state: Path = Path(".sloctl.db"), port: int = typer.Option(8765, min=1024, max=65535)) -> None:
    """Expose the simulator on loopback only. Ctrl-C stops it. No credentials needed."""
    from .server import server

    with backend(state, False, "datadoghq.com"):
        pass
    with server(state, port) as httpd:
        console.print(f"Local simulator: http://127.0.0.1:{port}/api/v1/slo")
        with suppress(KeyboardInterrupt):
            httpd.serve_forever()
