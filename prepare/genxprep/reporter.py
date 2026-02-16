"""Reporter – Rich console output for validation results.

Provides coloured, structured feedback: errors, warnings, suggestions, and
progress indicators so that non-technical users can understand what is wrong
and how to fix it.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Self

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# ---------------------------------------------------------------------------
# Severity levels
# ---------------------------------------------------------------------------

class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    SUCCESS = "success"


# ---------------------------------------------------------------------------
# Single validation message
# ---------------------------------------------------------------------------

@dataclass
class Message:
    severity: Severity
    text: str
    suggestion: str = ""
    context: str = ""  # e.g. file path or species code


# ---------------------------------------------------------------------------
# Validation result for one logical unit (file / step)
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    source: str  # human-readable label, e.g. "AC raw matrix"
    messages: list[Message] = field(default_factory=list)

    # convenience helpers --------------------------------------------------
    def error(self, text: str, *, suggestion: str = "", context: str = "") -> Self:
        self.messages.append(Message(Severity.ERROR, text, suggestion, context))
        return self

    def warn(self, text: str, *, suggestion: str = "", context: str = "") -> Self:
        self.messages.append(Message(Severity.WARNING, text, suggestion, context))
        return self

    def info(self, text: str, *, context: str = "") -> Self:
        self.messages.append(Message(Severity.INFO, text, context=context))
        return self

    def success(self, text: str, *, context: str = "") -> Self:
        self.messages.append(Message(Severity.SUCCESS, text, context=context))
        return self

    @property
    def has_errors(self) -> bool:
        return any(m.severity == Severity.ERROR for m in self.messages)

    @property
    def has_warnings(self) -> bool:
        return any(m.severity == Severity.WARNING for m in self.messages)

    @property
    def ok(self) -> bool:
        return not self.has_errors


# ---------------------------------------------------------------------------
# Reporter – collects results and renders them to console
# ---------------------------------------------------------------------------

_ICONS = {
    Severity.ERROR: "[bold red]✗[/bold red]",
    Severity.WARNING: "[bold yellow]⚠[/bold yellow]",
    Severity.INFO: "[bold blue]ℹ[/bold blue]",
    Severity.SUCCESS: "[bold green]✓[/bold green]",
}


class Reporter:
    """Accumulates :class:`ValidationResult` objects and renders them."""

    def __init__(self, *, verbose: bool = False) -> None:
        self.console = Console(stderr=True)
        self.verbose = verbose
        self._results: list[ValidationResult] = []

    # -- collecting --------------------------------------------------------

    def add(self, result: ValidationResult) -> None:
        self._results.append(result)

    def new(self, source: str) -> ValidationResult:
        """Create a new :class:`ValidationResult`, add it, and return it."""
        vr = ValidationResult(source=source)
        self._results.append(vr)
        return vr

    # -- querying ----------------------------------------------------------

    @property
    def has_errors(self) -> bool:
        return any(r.has_errors for r in self._results)

    @property
    def has_warnings(self) -> bool:
        return any(r.has_warnings for r in self._results)

    @property
    def results(self) -> list[ValidationResult]:
        return list(self._results)

    # -- printing ----------------------------------------------------------

    def print_msg(self, msg: Message) -> None:
        icon = _ICONS[msg.severity]
        line = f"  {icon} {msg.text}"
        self.console.print(line)
        if msg.suggestion:
            self.console.print(f"      [dim]→ {msg.suggestion}[/dim]")

    def print_result(self, result: ValidationResult) -> None:
        if not result.messages:
            return
        # Show only errors/warnings unless verbose
        msgs = result.messages
        if not self.verbose:
            msgs = [m for m in msgs if m.severity in (Severity.ERROR, Severity.WARNING, Severity.SUCCESS)]
        if not msgs:
            return

        self.console.print(f"\n[bold]{result.source}[/bold]")
        for m in msgs:
            self.print_msg(m)

    def print_all(self) -> None:
        for r in self._results:
            self.print_result(r)

    def print_summary(self) -> None:
        n_err = sum(1 for r in self._results for m in r.messages if m.severity == Severity.ERROR)
        n_warn = sum(1 for r in self._results for m in r.messages if m.severity == Severity.WARNING)
        n_ok = sum(1 for r in self._results for m in r.messages if m.severity == Severity.SUCCESS)

        self.console.print()
        if n_err:
            self.console.print(
                Panel(
                    f"[bold red]{n_err} error(s)[/bold red], "
                    f"[yellow]{n_warn} warning(s)[/yellow], "
                    f"[green]{n_ok} passed[/green]\n\n"
                    "Please fix all errors before building.",
                    title="[bold red]Validation failed[/bold red]",
                    border_style="red",
                )
            )
        elif n_warn:
            self.console.print(
                Panel(
                    f"[green]{n_ok} passed[/green], "
                    f"[yellow]{n_warn} warning(s)[/yellow]  — no errors.\n\n"
                    "Warnings indicate optional data that is missing or incomplete.\n"
                    "You can proceed with building.",
                    title="[bold green]Validation passed with warnings[/bold green]",
                    border_style="yellow",
                )
            )
        else:
            self.console.print(
                Panel(
                    f"[green]{n_ok} check(s) passed[/green] — everything looks good!",
                    title="[bold green]Validation passed[/bold green]",
                    border_style="green",
                )
            )

    def print_species_table(self, species_stats: dict[str, dict]) -> None:
        """Print a summary table with per-species statistics."""
        table = Table(title="Species Summary", show_lines=True)
        table.add_column("Code", style="bold")
        table.add_column("Species")
        table.add_column("Genes", justify="right")
        table.add_column("Samples", justify="right")
        table.add_column("Layers")
        table.add_column("Status")

        for code, stats in species_stats.items():
            status = "[green]✓[/green]" if stats.get("ok") else "[red]✗[/red]"
            table.add_row(
                code,
                stats.get("name", "?"),
                str(stats.get("n_genes", "?")),
                str(stats.get("n_samples", "?")),
                ", ".join(stats.get("layers", [])),
                status,
            )
        self.console.print()
        self.console.print(table)

    # -- lifecycle ---------------------------------------------------------

    def abort_if_errors(self) -> None:
        if self.has_errors:
            self.print_all()
            self.print_summary()
            sys.exit(1)

    def section(self, title: str) -> None:
        self.console.print(f"\n[bold underline]{title}[/bold underline]")
