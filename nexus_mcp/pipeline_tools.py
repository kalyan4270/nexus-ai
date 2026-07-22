"""
Exposes the full Nexus AI pipeline as MCP tools.
"""

from __future__ import annotations

import asyncio
from typing import Any

from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


async def run_nexus_pipeline(
    instruction:  str,
    safety_level: str = "balanced"
) -> dict[str, Any]:
    """
    Runs the FULL Nexus AI autonomous pipeline:
    PlannerAgent → CoderAgent → ReviewerAgent
    → SecurityAgent → TesterAgent → ValidatorAgent
    → Git commit → GitHub PR

    This is the entire brain of Nexus AI
    exposed as a single MCP tool.
    """
    from agents.orchestrator import NexusOrchestrator

    logger.info(
        "🚀 Nexus pipeline triggered via MCP: %s",
        instruction
    )

    context = {
        "repo_path":    settings.target_repo_path,
        "safety_level": safety_level
    }

    orchestrator = NexusOrchestrator()

    
    result = await orchestrator.run(
        instruction=instruction,
        context=context
    )

    logger.info(
        "Nexus pipeline complete: confidence=%s",
        result.get("confidence", 0)
    )

    return result


def get_nexus_plan(instruction: str) -> dict[str, Any]:
    """
    Shows execution plan without running.
    Useful for previewing what Nexus will do.
    """
    from agents.planner import PlannerAgent

    settings = get_settings()
    planner  = PlannerAgent()

    result = planner.execute(
        task=    instruction,
        context= {
            "repo_path": settings.target_repo_path
        }
    )

    return result


def get_nexus_status() -> dict[str, Any]:
    """
    Returns status of all 6 agents.
    """
    from agents.planner   import PlannerAgent
    from agents.coder     import CoderAgent
    from agents.reviewer  import ReviewerAgent
    from agents.security  import SecurityAgent
    from agents.tester    import TesterAgent
    from agents.validator import ValidatorAgent
    from a2a.registry     import agent_registry

    PlannerAgent()
    CoderAgent()
    ReviewerAgent()
    SecurityAgent()
    TesterAgent()
    ValidatorAgent()

    return agent_registry.get_status()