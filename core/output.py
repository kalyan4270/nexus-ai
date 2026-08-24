"""
Output manager for Nexus AI.
Handles both CLI (Rich) and MCP (plain) modes.
"""

from __future__ import annotations

from typing import Any


def is_mcp_mode() -> bool:
    """Check if running in MCP mode."""
    from core.config import get_settings
    try:
        return get_settings().nexus_mode == "mcp"
    except Exception:
        return False


def print_info(message: str) -> None:
    """Print info message."""
    if is_mcp_mode():
        _log_only("INFO", message)
        return
    from rich.console import Console
    Console().print(f"[cyan]{message}[/cyan]")


def print_success(message: str) -> None:
    """Print success message."""
    if is_mcp_mode():
        _log_only("INFO", message)
        return
    from rich.console import Console
    Console().print(f"[green]{message}[/green]")


def print_warning(message: str) -> None:
    """Print warning message."""
    if is_mcp_mode():
        _log_only("WARNING", message)
        return
    from rich.console import Console
    Console().print(f"[yellow]{message}[/yellow]")


def print_error(message: str) -> None:
    """Print error message."""
    if is_mcp_mode():
        _log_only("ERROR", message)
        return
    from rich.console import Console
    Console().print(f"[red]{message}[/red]")


def print_panel(
    content: str,
    title:   str = "",
    color:   str = "cyan"
) -> None:
    """Print a bordered panel."""
    if is_mcp_mode():
        _log_only("INFO", f"[{title}] {content}")
        return
    from rich.console import Console
    from rich.panel   import Panel
    Console().print(Panel(
        content,
        title=        title,
        border_style= color
    ))


def print_table(
    title:   str,
    columns: list[dict],
    rows:    list[list[str]]
) -> None:
    """Print a table."""
    if is_mcp_mode():
        # In MCP mode just log column headers and rows
        _log_only("INFO", f"Table: {title}")
        for row in rows:
            _log_only("INFO", " | ".join(str(c) for c in row))
        return

    from rich.console import Console
    from rich.table   import Table
    from rich         import box

    table = Table(
        box=         box.ROUNDED,
        show_header= True,
        header_style="bold cyan",
        title=       title
    )
    for col in columns:
        table.add_column(
            col.get("name", ""),
            width= col.get("width", 20)
        )
    for row in rows:
        table.add_row(*[str(c) for c in row])

    Console().print(table)


def _log_only(level: str, message: str) -> None:
    """Log without any Rich formatting."""
    import logging
    logger = logging.getLogger("nexus.output")
    clean  = _strip_rich_markup(message)
    getattr(logger, level.lower(), logger.info)(clean)


def _strip_rich_markup(text: str) -> str:
    """Remove Rich markup tags from text."""
    import re
    return re.sub(r'\[/?[^\]]+\]', '', text)