"""
Nexus AI Command Line Interface.
The main entry point for interacting
with Nexus AI from the terminal.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from agents.orchestrator import NexusOrchestrator
from core.config import get_settings
from core.logging import setup_logging
from safety.rollback import rollback_manager
from a2a.registry import agent_registry

console = Console()

def _init_agents() -> None:
    """Initialize all agents so they register with A2A."""
    from agents.planner   import PlannerAgent
    from agents.coder     import CoderAgent
    from agents.reviewer  import ReviewerAgent
    from agents.security  import SecurityAgent
    from agents.tester    import TesterAgent
    from agents.validator import ValidatorAgent

    PlannerAgent()
    CoderAgent()
    ReviewerAgent()
    SecurityAgent()
    TesterAgent()
    ValidatorAgent()


def print_banner() -> None:
    """Print Nexus AI banner."""
    console.print()
    console.print(Panel(
        "[bold cyan]"
        "  ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗\n"
        "  ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝\n"
        "  ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗\n"
        "  ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║\n"
        "  ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║\n"
        "  ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝\n"
        "[/bold cyan]"
        "[cyan]  Autonomous Developer Intelligence Network[/cyan]\n"
        "[dim]  Powered by MCP + A2A + Neo4j + Groq[/dim]",
        border_style="cyan",
        padding=(1, 2)
    ))


@click.group()
def cli() -> None:
    """
    Nexus AI — Autonomous Developer Assistant.
    Give it one instruction. It does the rest.
    """
    setup_logging()


@cli.command()
@click.argument("instruction")
@click.option(
    "--repo",
    default=None,
    help="Target repository path (overrides .env)"
)
@click.option(
    "--safety",
    default=None,
    type=click.Choice(["strict", "balanced", "auto"]),
    help="Safety level for this run"
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show plan only, do not execute"
)
def run(
    instruction: str,
    repo:        str | None,
    safety:      str | None,
    dry_run:     bool
) -> None:
    """
    Run an autonomous task.

    Example:
        nexus run "fix the failing tests"
        nexus run "add rate limiting to /review endpoint"
        nexus run "refactor the auth module"
    """
    print_banner()

    settings = get_settings()

    # Override settings if provided
    repo_path = repo or settings.target_repo_path
    if not repo_path:
        console.print(
            "[red]❌ No repository path set.\n"
            "Set TARGET_REPO_PATH in .env or "
            "use --repo flag[/red]"
        )
        sys.exit(1)

    context = {
        "repo_path":    repo_path,
        "safety_level": safety or settings.safety_level,
        "dry_run":      dry_run
    }

    if dry_run:
        console.print(
            "[yellow]🔍 DRY RUN MODE — "
            "Plan only, no execution[/yellow]"
        )
        # Show plan only
        from agents.planner import PlannerAgent
        planner = PlannerAgent()
        result  = planner.execute(instruction, context)
        if result.get("success"):
            planner.display_plan(
                result.get("plan", {})
            )
        return

    # Run full orchestration
    orchestrator = NexusOrchestrator()

    try:
        result = asyncio.run(
            orchestrator.run(instruction, context)
        )

        if result.get("success"):
            console.print(
                f"\n[bold green]✅ Task completed "
                f"successfully![/bold green]"
            )
            if result.get("pr_url"):
                console.print(
                    f"[cyan]🔗 PR: "
                    f"{result.get('pr_url')}[/cyan]"
                )
        else:
            console.print(
                f"\n[bold red]❌ Task failed: "
                f"{result.get('reason')}[/bold red]"
            )
            sys.exit(1)

    except KeyboardInterrupt:
        console.print(
            "\n[yellow]⚠ Task interrupted by user[/yellow]"
        )
        sys.exit(0)


@cli.command()
@click.argument("instruction")
def plan(instruction: str) -> None:
    """
    Show execution plan without running.

    Example:
        nexus plan "add authentication to API"
    """
    print_banner()

    from agents.planner import PlannerAgent

    settings = get_settings()
    planner  = PlannerAgent()

    console.print(
        f"\n[cyan]Planning: {instruction}[/cyan]\n"
    )

    result = planner.execute(
        instruction,
        {"repo_path": settings.target_repo_path}
    )

    if result.get("success"):
        planner.display_plan(result.get("plan", {}))
    else:
        console.print(
            f"[red]Planning failed: "
            f"{result.get('error')}[/red]"
        )


@cli.command()
def status() -> None:
    """
    Show status of all Nexus AI agents.

    Example:
        nexus status
    """
    print_banner()

    # Initialize all agents so they register
    from agents.planner   import PlannerAgent
    from agents.coder     import CoderAgent
    from agents.reviewer  import ReviewerAgent
    from agents.security  import SecurityAgent
    from agents.tester    import TesterAgent
    from agents.validator import ValidatorAgent

    PlannerAgent()
    CoderAgent()
    ReviewerAgent()
    SecurityAgent()
    TesterAgent()
    ValidatorAgent()

    status_data = agent_registry.get_status()
    settings    = get_settings()

    # Agent table
    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        title="Agent Status"
    )
    table.add_column("Agent",        width=20)
    table.add_column("Status",       width=12)
    table.add_column("Capabilities", width=45)
    table.add_column("Tasks",        width=8)

    for agent in status_data.get("agents", []):
        available  = agent.get("available", False)
        status_str = (
            "[green]🟢 Ready[/green]"
            if available
            else "[yellow]🟡 Busy[/yellow]"
        )
        caps = ", ".join(
            agent.get("capabilities", [])[:3]
        )
        if len(agent.get("capabilities", [])) > 3:
            caps += "..."

        table.add_row(
            agent.get("name", ""),
            status_str,
            caps,
            str(agent.get("active_tasks", 0))
        )

    console.print(table)

    # Config info
    console.print()
    console.print(Panel(
        f"[cyan]Repo:[/cyan]      "
        f"{settings.target_repo_path or 'Not set'}\n"
        f"[cyan]Safety:[/cyan]    {settings.safety_level}\n"
        f"[cyan]Model:[/cyan]     {settings.groq_model}\n"
        f"[cyan]Auto PR:[/cyan]   {settings.auto_create_pr}\n"
        f"[cyan]Auto Test:[/cyan] {settings.auto_run_tests}",
        title="[cyan]⚙ Configuration[/cyan]",
        border_style="cyan"
    ))


@cli.command()
def history() -> None:
    """
    Show recent operation history.

    Example:
        nexus history
    """
    print_banner()

    records = rollback_manager.get_history(limit=20)

    if not records:
        console.print(
            "[yellow]No operations in history yet[/yellow]"
        )
        return

    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        title="Operation History"
    )
    table.add_column("#",           width=6)
    table.add_column("Time",        width=20)
    table.add_column("Operation",   width=20)
    table.add_column("File",        width=35)
    table.add_column("Status",      width=12)

    for record in records:
        status_str = record.get("status", "")
        color = {
            "completed":   "green",
            "rolled_back": "yellow",
            "failed":      "red",
            "pending":     "cyan"
        }.get(status_str, "white")

        table.add_row(
            str(record.get("id", "")),
            record.get("timestamp", "")[:19],
            record.get("operation", ""),
            record.get("file_path", "") or "",
            f"[{color}]{status_str}[/{color}]"
        )

    console.print(table)


@cli.command()
@click.option(
    "--operation-id",
    default=None,
    type=int,
    help="Rollback specific operation ID"
)
def rollback(operation_id: int | None) -> None:
    """
    Rollback last operation or specific one.

    Example:
        nexus rollback
        nexus rollback --operation-id 5
    """
    print_banner()

    if operation_id:
        console.print(
            f"[yellow]Rolling back operation "
            f"#{operation_id}...[/yellow]"
        )
        success = rollback_manager.rollback_operation(
            operation_id
        )
    else:
        console.print(
            "[yellow]Rolling back last operation...[/yellow]"
        )
        success = rollback_manager.rollback_latest()

    if success:
        console.print(
            "[green]✅ Rollback successful[/green]"
        )
    else:
        console.print(
            "[red]❌ Rollback failed — "
            "check history for details[/red]"
        )


@cli.command()
def agents() -> None:
    """
    List all agents and their capabilities.

    Example:
        nexus agents
    """
    print_banner()

    # Initialize all agents so they register
    from agents.planner   import PlannerAgent
    from agents.coder     import CoderAgent
    from agents.reviewer  import ReviewerAgent
    from agents.security  import SecurityAgent
    from agents.tester    import TesterAgent
    from agents.validator import ValidatorAgent

    PlannerAgent()
    CoderAgent()
    ReviewerAgent()
    SecurityAgent()
    TesterAgent()
    ValidatorAgent()

    cap_map = agent_registry.list_agents_by_capability()

    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        title="Agent Capabilities"
    )
    table.add_column("Capability", width=30)
    table.add_column("Handled By", width=40)

    for capability, agent_names in sorted(
        cap_map.items()
    ):
        table.add_row(
            capability,
            ", ".join(agent_names)
        )

    console.print(table)


@cli.command()
@click.argument("question")
def ask(question: str) -> None:
    """
    Ask Nexus AI a question about the codebase.

    Example:
        nexus ask "where is rate limiting implemented?"
        nexus ask "which files handle authentication?"
    """
    print_banner()

    from mcp.tools.search_tools import semantic_search
    from core.llm import complete

    console.print(
        f"\n[cyan]🔍 Searching codebase for: "
        f"{question}[/cyan]\n"
    )

    # Search codebase
    results = semantic_search(
        query=     question,
        max_files= 5
    )

    if not results.get("success"):
        console.print("[red]Search failed[/red]")
        return

    # Build context from results
    context = ""
    for r in results.get("results", []):
        context += (
            f"\n--- {r['file']} ---\n"
            f"{r['content'][:500]}\n"
        )

    # Ask LLM with context
    prompt = f"""
Answer this question about the codebase:
{question}

Relevant code found:
{context}

Give a specific, helpful answer.
Reference exact files and line numbers
where relevant.
"""

    answer = complete(prompt, max_tokens=500)

    console.print(Panel(
        answer,
        title=f"[cyan]💡 Answer: {question}[/cyan]",
        border_style="cyan"
    ))


@cli.command()
def mcp() -> None:
    """
    Start the MCP server for Claude Desktop
    or Cursor IDE integration.

    Example:
        nexus mcp
    """
    import asyncio
    from mcp.server import run_mcp_server

    console.print(Panel(
        "[cyan]Starting Nexus AI MCP Server...[/cyan]\n"
        "[dim]Connect via Claude Desktop or Cursor IDE[/dim]",
        title="[cyan]🔌 MCP Server[/cyan]",
        border_style="cyan"
    ))

    asyncio.run(run_mcp_server())


if __name__ == "__main__":
    cli()