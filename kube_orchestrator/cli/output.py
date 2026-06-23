from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.syntax import Syntax
from rich.table import Table

_console = Console()
_err_console = Console(stderr=True)


def print_table(
    headers: list[str], rows: list[list[Any]], title: str | None = None
) -> None:
    table = Table(title=title, show_header=True, header_style="bold cyan")
    for h in headers:
        table.add_column(h)
    for row in rows:
        table.add_row(*[str(c) for c in row])
    _console.print(table)


def print_success(message: str) -> None:
    _console.print(f"[bold green]✔[/bold green] {message}")


def print_error(message: str) -> None:
    _err_console.print(f"[bold red]✘[/bold red] {message}")


def print_warning(message: str) -> None:
    _console.print(f"[bold yellow]⚠[/bold yellow] {message}")


def print_info(message: str) -> None:
    _console.print(f"[bold blue]ℹ[/bold blue] {message}")


def print_diff(diff: dict[str, Any]) -> None:
    import json

    content = json.dumps(diff, indent=2, default=str)
    syntax = Syntax(content, "json", theme="monokai", line_numbers=True)
    _console.print(Panel(syntax, title="Diff", border_style="yellow"))


def print_health_report(report: dict[str, Any]) -> None:
    score = report.get("score", 0)
    color = "green" if score >= 80 else ("yellow" if score >= 50 else "red")
    lines = [f"[bold]Health Score:[/bold] [{color}]{score}/100[/{color}]"]

    for section in ("nodes", "control_plane", "workloads", "storage", "networking"):
        if section in report:
            data = report[section]
            status = (
                data.get("status", "unknown") if isinstance(data, dict) else str(data)
            )
            lines.append(
                f"  [cyan]{section.replace('_', ' ').title()}:[/cyan] {status}"
            )

    _console.print(
        Panel("\n".join(lines), title="Cluster Health Report", border_style=color)
    )


def progress_bar(total: int, description: str) -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn(f"[bold blue]{description}"),
        TimeElapsedColumn(),
        transient=True,
    )


def print_yaml(data: dict[str, Any]) -> None:
    import yaml

    content = yaml.dump(data, default_flow_style=False, allow_unicode=True)
    syntax = Syntax(content, "yaml", theme="monokai")
    _console.print(syntax)


def print_json(data: dict[str, Any]) -> None:
    import json

    content = json.dumps(data, indent=2, default=str)
    syntax = Syntax(content, "json", theme="monokai")
    _console.print(syntax)
