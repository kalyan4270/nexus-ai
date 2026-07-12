"""
Agent Registry for Nexus AI.
Manages agent discovery and capability matching.
"""

from __future__ import annotations

from typing import Any

from a2a.protocol import A2AProtocol, AgentCard, a2a_protocol
from core.logging import get_logger

logger = get_logger(__name__)


class AgentRegistry:
    """
    Central registry for all Nexus AI agents.

    Manages:
    - Agent registration
    - Capability discovery
    - Task routing to right agent
    - Agent health tracking
    """

    def __init__(self, protocol: A2AProtocol) -> None:
        self._protocol = protocol
        self._task_counts: dict[str, int] = {}
        logger.info("📋 Agent Registry initialized")

    def register(
        self,
        agent_id:     str,
        name:         str,
        description:  str,
        capabilities: list[str],
        handler:      Any
    ) -> AgentCard:
        """
        Register a new agent.
        Returns the created AgentCard.
        """
        card = AgentCard(
            agent_id=     agent_id,
            name=         name,
            description=  description,
            capabilities= capabilities,
            is_available= True
        )

        self._protocol.register_agent(card, handler)
        self._task_counts[agent_id] = 0

        logger.info(
            "📌 Registered: %s — capabilities: %s",
            name,
            ", ".join(capabilities)
        )

        return card

    def get_best_agent(
        self,
        capability: str
    ) -> AgentCard | None:
        """
        Find best available agent for a capability.
        Prefers agents with fewer active tasks.
        """
        candidates = [
            agent
            for agent in self._protocol.list_agents()
            if capability in agent.capabilities
        ]

        if not candidates:
            logger.warning(
                "No agent found for capability: %s",
                capability
            )
            return None

        # Pick agent with fewest tasks
        best = min(
            candidates,
            key=lambda a: self._task_counts.get(
                a.agent_id, 0
            )
        )

        logger.info(
            "🎯 Best agent for '%s': %s",
            capability,
            best.name
        )

        return best

    def increment_task(self, agent_id: str) -> None:
        """Track that agent has taken a task."""
        self._task_counts[agent_id] = (
            self._task_counts.get(agent_id, 0) + 1
        )

    def decrement_task(self, agent_id: str) -> None:
        """Track that agent completed a task."""
        current = self._task_counts.get(agent_id, 0)
        self._task_counts[agent_id] = max(0, current - 1)

    def get_all_capabilities(self) -> list[str]:
        """Get all capabilities across all agents."""
        caps = set()
        for agent in self._protocol.list_agents(
            available_only=False
        ):
            caps.update(agent.capabilities)
        return sorted(caps)

    def get_status(self) -> dict[str, Any]:
        """Get status of all registered agents."""
        agents = self._protocol.list_agents(
            available_only=False
        )
        return {
            "total_agents":     len(agents),
            "available_agents": sum(
                1 for a in agents if a.is_available
            ),
            "agents": [
                {
                    "id":           a.agent_id,
                    "name":         a.name,
                    "available":    a.is_available,
                    "capabilities": a.capabilities,
                    "active_tasks": self._task_counts.get(
                        a.agent_id, 0
                    )
                }
                for a in agents
            ]
        }

    def list_agents_by_capability(
        self
    ) -> dict[str, list[str]]:
        """
        Group agents by their capabilities.
        Useful for understanding what system can do.
        """
        capability_map: dict[str, list[str]] = {}

        for agent in self._protocol.list_agents(
            available_only=False
        ):
            for cap in agent.capabilities:
                if cap not in capability_map:
                    capability_map[cap] = []
                capability_map[cap].append(agent.name)

        return capability_map


# Single shared registry
agent_registry = AgentRegistry(a2a_protocol)