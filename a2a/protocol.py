"""
A2A (Agent to Agent) Protocol Implementation.
Enables peer agents to communicate directly
without a central orchestrator.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from core.logging import get_logger

logger = get_logger(__name__)


class MessageType(Enum):
    """Types of messages agents can send."""
    REQUEST   = "request"    # Ask another agent to do something
    RESPONSE  = "response"   # Reply to a request
    BROADCAST = "broadcast"  # Send to all agents
    DELEGATE  = "delegate"   # Hand off a task
    APPROVE   = "approve"    # Approve a proposed action
    REJECT    = "reject"     # Reject a proposed action
    STATUS    = "status"     # Update on progress
    COMPLETE  = "complete"   # Task is done


class Priority(Enum):
    """Message priority levels."""
    LOW    = 1
    MEDIUM = 2
    HIGH   = 3
    URGENT = 4


@dataclass
class A2AMessage:
    """
    A message between two agents.
    Every agent communication uses this format.
    """
    from_agent:  str
    to_agent:    str
    message_type: MessageType
    content:     dict[str, Any]
    priority:    Priority = Priority.MEDIUM
    message_id:  str      = field(
        default_factory=lambda: str(uuid.uuid4())[:8]
    )
    timestamp:   str      = field(
        default_factory=lambda: datetime.now().isoformat()
    )
    reply_to:    str | None = None  # ID of message being replied to
    task_id:     str | None = None  # Task this message belongs to


@dataclass
class AgentCard:
    """
    Describes what an agent can do.
    Used for agent discovery in A2A.
    """
    agent_id:     str
    name:         str
    description:  str
    capabilities: list[str]
    is_available: bool = True


class A2AProtocol:
    """
    Core A2A protocol implementation.

    Manages:
    - Agent registration
    - Message routing between agents
    - Task coordination
    - Agent discovery
    """

    def __init__(self) -> None:
        # Registered agents
        self._agents:   dict[str, AgentCard] = {}

        # Message handlers per agent
        self._handlers: dict[str, Callable] = {}

        # Message queue per agent
        self._queues:   dict[str, asyncio.Queue] = {}

        # Message history for audit
        self._history:  list[A2AMessage] = []

        logger.info("🌐 A2A Protocol initialized")

    def register_agent(
        self,
        agent_card: AgentCard,
        handler:    Callable[[A2AMessage], Any]
    ) -> None:
        """
        Register an agent with the protocol.
        Agent will receive messages via handler.
        """
        self._agents[agent_card.agent_id]   = agent_card
        self._handlers[agent_card.agent_id] = handler
        self._queues[agent_card.agent_id]   = asyncio.Queue()

        logger.info(
            "✅ Agent registered: %s (%s)",
            agent_card.name,
            agent_card.agent_id
        )

    def unregister_agent(self, agent_id: str) -> None:
        """Remove agent from protocol."""
        self._agents.pop(agent_id, None)
        self._handlers.pop(agent_id, None)
        self._queues.pop(agent_id, None)
        logger.info("👋 Agent unregistered: %s", agent_id)

    def get_agent(self, agent_id: str) -> AgentCard | None:
        """Get agent card by ID."""
        return self._agents.get(agent_id)

    def list_agents(
        self,
        available_only: bool = True
    ) -> list[AgentCard]:
        """List all registered agents."""
        agents = list(self._agents.values())
        if available_only:
            agents = [a for a in agents if a.is_available]
        return agents

    def find_agent_by_capability(
        self,
        capability: str
    ) -> AgentCard | None:
        """
        Find an agent that has a specific capability.
        Used for automatic task delegation.
        """
        for agent in self._agents.values():
            if (
                agent.is_available and
                capability in agent.capabilities
            ):
                return agent
        return None

    async def send_message(
        self,
        message: A2AMessage
    ) -> A2AMessage | None:
        """
        Send a message from one agent to another.
        Returns response message if synchronous.
        """
        # Validate target agent exists
        if message.to_agent not in self._agents:
            logger.error(
                "❌ Target agent not found: %s",
                message.to_agent
            )
            return None

        # Log message
        self._history.append(message)
        logger.info(
            "📨 %s → %s: [%s] %s",
            message.from_agent,
            message.to_agent,
            message.message_type.value,
            str(message.content)[:100]
        )

        # Route to handler
        handler = self._handlers.get(message.to_agent)
        if not handler:
            logger.error(
                "No handler for agent: %s",
                message.to_agent
            )
            return None

        try:
            # Call handler and get response
            response = await asyncio.get_event_loop(
            ).run_in_executor(
                None,
                lambda: handler(message)
            )

            if response:
                self._history.append(response)
                logger.info(
                    "📩 %s → %s: [%s] response received",
                    response.from_agent,
                    response.to_agent,
                    response.message_type.value
                )

            return response

        except Exception as exc:
            logger.error(
                "Message delivery failed %s→%s: %s",
                message.from_agent,
                message.to_agent,
                exc
            )
            return None

    async def broadcast(
        self,
        from_agent: str,
        content:    dict[str, Any],
        task_id:    str | None = None
    ) -> list[A2AMessage]:
        """
        Send message to ALL registered agents.
        Returns list of responses.
        """
        responses = []
        for agent_id, agent in self._agents.items():
            if agent_id == from_agent:
                continue  # Don't send to self

            if not agent.is_available:
                continue

            message = A2AMessage(
                from_agent=   from_agent,
                to_agent=     agent_id,
                message_type= MessageType.BROADCAST,
                content=      content,
                task_id=      task_id
            )

            response = await self.send_message(message)
            if response:
                responses.append(response)

        return responses

    def get_history(
        self,
        task_id:    str | None = None,
        agent_id:   str | None = None,
        limit:      int = 50
    ) -> list[dict[str, Any]]:
        """Get message history with optional filters."""
        history = self._history

        if task_id:
            history = [
                m for m in history
                if m.task_id == task_id
            ]

        if agent_id:
            history = [
                m for m in history
                if m.from_agent == agent_id or
                   m.to_agent == agent_id
            ]

        return [
            {
                "message_id":   m.message_id,
                "from":         m.from_agent,
                "to":           m.to_agent,
                "type":         m.message_type.value,
                "content":      m.content,
                "timestamp":    m.timestamp,
                "task_id":      m.task_id
            }
            for m in history[-limit:]
        ]

    def set_agent_availability(
        self,
        agent_id:     str,
        is_available: bool
    ) -> None:
        """Mark agent as available or busy."""
        if agent_id in self._agents:
            self._agents[agent_id].is_available = is_available
            logger.info(
                "Agent %s availability: %s",
                agent_id,
                "available" if is_available else "busy"
            )


# Single shared protocol instance
a2a_protocol = A2AProtocol()