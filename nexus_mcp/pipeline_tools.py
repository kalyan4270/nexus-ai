"""
Exposes the full Nexus AI pipeline as MCP tools.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


async def run_nexus_pipeline(
    instruction:  str,
    safety_level: str = "balanced"
) -> dict[str, Any]:

    import os
    os.environ["NEXUS_MODE"] = "mcp"

    from core.config import get_settings as _get_settings
    _get_settings.cache_clear()
    _settings = _get_settings()

    from agents.orchestrator import NexusOrchestrator

    logger.info(
        "🚀 Nexus pipeline triggered via MCP: %s",
        instruction
    )

    context = {
        "repo_path":    settings.target_repo_path,
        "safety_level": safety_level,
        "mcp_mode":     True
    }

    orchestrator = NexusOrchestrator()

    start_time = time.time()

    try:
        result = await orchestrator.run(instruction, context)

    finally:
        elapsed = time.time() - start_time

        logger.info(
            "✅ Pipeline complete in %.1f seconds",
            elapsed
        )

        os.environ["NEXUS_MODE"] = "cli"
        get_settings.cache_clear()

    result["elapsed_seconds"] = round(elapsed, 1)
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