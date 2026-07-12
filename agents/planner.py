"""
Planner Agent — The brain of Nexus AI.
Breaks down user instructions into
executable steps and coordinates agents.
"""

from __future__ import annotations

import json
from typing import Any

from agents.base import NexusAgent
from core.logging import get_logger

logger = get_logger(__name__)


class PlannerAgent(NexusAgent):
    """
    PlannerAgent is the entry point for every task.

    Responsibilities:
    - Understand user instruction
    - Break it into concrete steps
    - Assign steps to right agents
    - Track overall progress
    - Report final result
    """

    def __init__(self) -> None:
        super().__init__(
            agent_id=     "planner",
            name=         "PlannerAgent",
            description=  "Breaks down tasks and coordinates agents",
            capabilities= [
                "planning",
                "task_decomposition",
                "agent_coordination",
                "progress_tracking"
            ]
        )

    def execute(
        self,
        task:    str,
        context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Main planning method.
        Takes user instruction and creates
        execution plan with steps.
        """
        task_id = self.new_task_id()
        self.start_task(task_id)

        try:
            logger.info(
                "📋 PlannerAgent planning: %s",
                task
            )

            # Step 1 — Understand the task
            plan = self._create_plan(task, context)

            # Step 2 — Validate plan
            if not plan.get("steps"):
                return {
                    "success": False,
                    "error":   "Could not create execution plan",
                    "task_id": task_id
                }

            logger.info(
                "✅ Plan created: %d steps",
                len(plan["steps"])
            )

            return {
                "success": True,
                "task_id": task_id,
                "task":    task,
                "plan":    plan
            }

        except Exception as exc:
            logger.error(
                "PlannerAgent failed: %s", exc
            )
            return {
                "success": False,
                "error":   str(exc),
                "task_id": task_id
            }
        finally:
            self.complete_task()

    def _create_plan(
        self,
        task:    str,
        context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Use LLM to create detailed execution plan.
        Returns structured plan with steps.
        """
        # Get available capabilities
        from a2a.registry import agent_registry
        capabilities = agent_registry.get_all_capabilities()

        repo_path = context.get(
            "repo_path", "the repository"
        )

        prompt = f"""
You are a senior software engineering planner.
A developer has given you this instruction:

"{task}"

Repository: {repo_path}

Available agent capabilities:
{json.dumps(capabilities, indent=2)}

Create a detailed execution plan.
Return ONLY valid JSON in this exact format:

{{
    "summary": "One sentence describing what will be done",
    "risk_level": "LOW|MEDIUM|HIGH",
    "estimated_time": "X minutes",
    "steps": [
        {{
            "step_number": 1,
            "description": "What this step does",
            "agent": "which agent handles this",
            "capability": "which capability to use",
            "tool": "which MCP tool to call",
            "risk": "LOW|MEDIUM|HIGH",
            "requires_confirmation": false,
            "depends_on": []
        }}
    ]
}}

Rules:
- Keep steps atomic and specific
- Order steps by dependency
- Mark file writes as MEDIUM risk
- Mark deletions as HIGH risk (avoid if possible)
- Maximum 8 steps
- Use only available capabilities listed above
- Return ONLY the JSON, no other text
"""

        response = self.think(
            prompt,
            max_tokens=  1500,
            temperature= 0.2
        )

        # Parse JSON response
        try:
            # Clean response — remove markdown
            clean = response.strip()
            if "```json" in clean:
                clean = clean.split("```json")[1]
                clean = clean.split("```")[0]
            elif "```" in clean:
                clean = clean.split("```")[1]
                clean = clean.split("```")[0]

            plan = json.loads(clean.strip())
            return plan

        except json.JSONDecodeError as exc:
            logger.error(
                "Failed to parse plan JSON: %s\n%s",
                exc, response
            )
            # Return basic fallback plan
            return {
                "summary":        task,
                "risk_level":     "MEDIUM",
                "estimated_time": "5 minutes",
                "steps": [
                    {
                        "step_number":          1,
                        "description":          f"Analyze and execute: {task}",
                        "agent":                "coder",
                        "capability":           "code_writing",
                        "tool":                 "semantic_search",
                        "risk":                 "LOW",
                        "requires_confirmation": False,
                        "depends_on":           []
                    }
                ]
            }

    def display_plan(
        self,
        plan: dict[str, Any]
    ) -> str:
        """
        Format plan for terminal display.
        """
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        from rich import box

        console = Console()
        steps   = plan.get("steps", [])

        # Header
        risk_color = {
            "LOW":    "green",
            "MEDIUM": "yellow",
            "HIGH":   "red"
        }.get(plan.get("risk_level", "LOW"), "white")

        console.print()
        console.print(Panel(
            f"[bold]{plan.get('summary', '')}[/bold]\n\n"
            f"[{risk_color}]Risk: "
            f"{plan.get('risk_level', 'LOW')}[/{risk_color}]  "
            f"[cyan]Est. time: "
            f"{plan.get('estimated_time', 'Unknown')}[/cyan]",
            title="[cyan]📋 Execution Plan[/cyan]",
            border_style="cyan"
        ))

        # Steps table
        table = Table(
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan"
        )
        table.add_column("#",           width=4)
        table.add_column("Step",        width=40)
        table.add_column("Agent",       width=15)
        table.add_column("Risk",        width=8)
        table.add_column("Confirm",     width=8)

        for step in steps:
            risk  = step.get("risk", "LOW")
            color = {
                "LOW":    "green",
                "MEDIUM": "yellow",
                "HIGH":   "red"
            }.get(risk, "white")

            confirm = (
                "✓" if step.get(
                    "requires_confirmation"
                ) else "auto"
            )

            table.add_row(
                str(step.get("step_number", "")),
                step.get("description", ""),
                step.get("agent", ""),
                f"[{color}]{risk}[/{color}]",
                confirm
            )

        console.print(table)
        return plan.get("summary", "")