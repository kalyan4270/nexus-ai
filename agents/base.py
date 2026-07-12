"""
Base agent class for all Nexus AI agents.
All agents inherit from NexusAgent.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Any

from a2a.protocol import (
    A2AMessage,
    AgentCard,
    MessageType,
    Priority,
    a2a_protocol,
)
from a2a.registry import agent_registry
from core.llm import complete
from core.logging import get_logger

logger = get_logger(__name__)


class NexusAgent(ABC):
    """
    Base class for all Nexus AI agents.

    Every agent:
    - Has a unique ID and capabilities
    - Can send/receive A2A messages
    - Can use LLM for reasoning
    - Registers itself with the protocol
    """

    def __init__(
        self,
        agent_id:     str,
        name:         str,
        description:  str,
        capabilities: list[str]
    ) -> None:
        self.agent_id     = agent_id
        self.name         = name
        self.description  = description
        self.capabilities = capabilities
        self.current_task: str | None = None

        # Register with A2A protocol
        agent_registry.register(
            agent_id=     agent_id,
            name=         name,
            description=  description,
            capabilities= capabilities,
            handler=      self.handle_message
        )

        logger.info(
            "🤖 Agent initialized: %s [%s]",
            name, agent_id
        )

    # ─── Abstract Methods ────────────────────────────────

    @abstractmethod
    def execute(
        self,
        task:    str,
        context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Main execution method.
        Each agent implements its own logic here.
        """
        ...

    # ─── A2A Communication ───────────────────────────────

    def handle_message(
        self,
        message: A2AMessage
    ) -> A2AMessage | None:
        """
        Handle incoming A2A message.
        Routes to correct handler based on type.
        """
        logger.info(
            "📨 %s received [%s] from %s",
            self.name,
            message.message_type.value,
            message.from_agent
        )

        if message.message_type == MessageType.REQUEST:
            return self._handle_request(message)

        if message.message_type == MessageType.DELEGATE:
            return self._handle_delegate(message)

        if message.message_type == MessageType.BROADCAST:
            return self._handle_broadcast(message)

        if message.message_type == MessageType.STATUS:
            return self._handle_status(message)

        return None

    def _handle_request(
        self,
        message: A2AMessage
    ) -> A2AMessage:
        """Handle a request from another agent."""
        task    = message.content.get("task", "")
        context = message.content.get("context", {})

        try:
            result = self.execute(task, context)
            return self._make_response(
                to_agent=    message.from_agent,
                content=     result,
                message_type=MessageType.RESPONSE,
                reply_to=    message.message_id,
                task_id=     message.task_id
            )
        except Exception as exc:
            logger.error(
                "%s failed request: %s",
                self.name, exc
            )
            return self._make_response(
                to_agent=    message.from_agent,
                content=     {"error": str(exc)},
                message_type=MessageType.RESPONSE,
                reply_to=    message.message_id,
                task_id=     message.task_id
            )

    def _handle_delegate(
        self,
        message: A2AMessage
    ) -> A2AMessage:
        """Handle a delegated task from another agent."""
        return self._handle_request(message)

    def _handle_broadcast(
        self,
        message: A2AMessage
    ) -> A2AMessage | None:
        """Handle a broadcast message."""
        content = message.content
        logger.info(
            "%s received broadcast: %s",
            self.name,
            str(content)[:100]
        )
        return None

    def _handle_status(
        self,
        message: A2AMessage
    ) -> A2AMessage:
        """Return current status."""
        return self._make_response(
            to_agent=    message.from_agent,
            content=     {
                "agent_id":     self.agent_id,
                "name":         self.name,
                "is_available": self.current_task is None,
                "current_task": self.current_task
            },
            message_type=MessageType.STATUS,
            reply_to=    message.message_id,
            task_id=     message.task_id
        )

    def _make_response(
        self,
        to_agent:     str,
        content:      dict[str, Any],
        message_type: MessageType = MessageType.RESPONSE,
        reply_to:     str | None = None,
        task_id:      str | None = None,
        priority:     Priority = Priority.MEDIUM
    ) -> A2AMessage:
        """Create a response message."""
        return A2AMessage(
            from_agent=   self.agent_id,
            to_agent=     to_agent,
            message_type= message_type,
            content=      content,
            priority=     priority,
            reply_to=     reply_to,
            task_id=      task_id
        )

    async def send_to(
        self,
        to_agent_id: str,
        task:        str,
        context:     dict[str, Any] | None = None,
        task_id:     str | None = None,
        priority:    Priority = Priority.MEDIUM
    ) -> dict[str, Any] | None:
        """
        Send a task request to another agent.
        Returns their response content.
        """
        message = A2AMessage(
            from_agent=   self.agent_id,
            to_agent=     to_agent_id,
            message_type= MessageType.REQUEST,
            content=      {
                "task":    task,
                "context": context or {}
            },
            priority=    priority,
            task_id=     task_id
        )

        response = await a2a_protocol.send_message(message)

        if response:
            return response.content
        return None

    async def delegate_to(
        self,
        capability:  str,
        task:        str,
        context:     dict[str, Any] | None = None,
        task_id:     str | None = None
    ) -> dict[str, Any] | None:
        """
        Delegate task to best agent with capability.
        Automatically finds right agent.
        """
        agent = agent_registry.get_best_agent(capability)

        if not agent:
            logger.error(
                "No agent found for capability: %s",
                capability
            )
            return None

        logger.info(
            "📤 %s delegating '%s' to %s",
            self.name, capability, agent.name
        )

        return await self.send_to(
            to_agent_id=agent.agent_id,
            task=       task,
            context=    context,
            task_id=    task_id,
            priority=   Priority.HIGH
        )

    # ─── LLM Helper ──────────────────────────────────────

    def think(
        self,
        prompt:      str,
        max_tokens:  int = 1024,
        temperature: float = 0.3
    ) -> str:
        """
        Use LLM to reason about something.
        All agents use this for intelligence.
        """
        return complete(
            prompt,
            max_tokens=  max_tokens,
            temperature= temperature
        )

    # ─── Task Management ─────────────────────────────────

    def start_task(self, task_id: str) -> None:
        """Mark agent as busy with a task."""
        self.current_task = task_id
        agent_registry.increment_task(self.agent_id)
        a2a_protocol.set_agent_availability(
            self.agent_id, False
        )

    def complete_task(self) -> None:
        """Mark agent as available again."""
        self.current_task = None
        agent_registry.decrement_task(self.agent_id)
        a2a_protocol.set_agent_availability(
            self.agent_id, True
        )

    def new_task_id(self) -> str:
        """Generate unique task ID."""
        return str(uuid.uuid4())[:8]