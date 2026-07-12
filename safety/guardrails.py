"""Safety guardrails for all Nexus AI operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.logging import get_logger
from safety.classifier import RiskLevel, classify, is_blocked, is_auto

logger = get_logger(__name__)


@dataclass
class OperationResult:
    """Result of a safety check."""
    allowed:    bool
    risk_level: RiskLevel
    reason:     str
    requires_confirmation: bool = False


def check_operation(
    operation:    str,
    context:      dict[str, Any] | None = None,
    safety_level: str = "balanced"
) -> OperationResult:
    """
    Main safety check for any operation.
    Call this before executing ANY tool.

    Returns OperationResult with:
    - allowed: can this run?
    - risk_level: how risky is it?
    - reason: why allowed/blocked?
    - requires_confirmation: needs human?
    """
    context = context or {}

    # Step 1 — Check if permanently blocked
    if is_blocked(operation):
        logger.warning(
            "🔴 BLOCKED operation attempted: %s", operation
        )
        return OperationResult(
            allowed=False,
            risk_level=RiskLevel.HIGH,
            reason=f"'{operation}' is permanently blocked. "
                   f"Nexus AI never performs this operation "
                   f"autonomously for safety.",
            requires_confirmation=False
        )

    # Step 2 — Classify risk
    risk = classify(operation)

    # Step 3 — Check if auto allowed
    if is_auto(operation, safety_level):
        logger.info(
            "🟢 AUTO operation: %s [%s]",
            operation, risk.value
        )
        return OperationResult(
            allowed=True,
            risk_level=risk,
            reason=f"'{operation}' is low risk "
                   f"and runs automatically.",
            requires_confirmation=False
        )

    # Step 4 — Needs confirmation
    logger.info(
        "🟡 CONFIRM required: %s [%s]",
        operation, risk.value
    )
    return OperationResult(
        allowed=True,
        risk_level=risk,
        reason=f"'{operation}' requires your approval "
               f"before executing.",
        requires_confirmation=True
    )


def request_confirmation(
    operation:   str,
    description: str,
    diff:        str | None = None
) -> bool:
    """
    Ask human for confirmation in terminal.
    Shows operation details and diff if available.
    Returns True if approved, False if rejected.
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    console = Console()

    # Show operation details
    console.print()
    console.print(Panel(
        f"[yellow]Operation:[/yellow] {operation}\n"
        f"[yellow]Description:[/yellow] {description}"
        + (f"\n\n[cyan]Changes:[/cyan]\n{diff}" if diff else ""),
        title="[yellow]⚠ Confirmation Required[/yellow]",
        border_style="yellow"
    ))

    # Ask for confirmation
    while True:
        response = console.input(
            "[yellow]Proceed? (yes/no): [/yellow]"
        ).strip().lower()

        if response in ("yes", "y"):
            logger.info("✅ User approved: %s", operation)
            return True
        elif response in ("no", "n"):
            logger.info("❌ User rejected: %s", operation)
            return False
        else:
            console.print("[red]Please enter yes or no[/red]")