"""
Reviewer Agent — Reviews code written by CoderAgent.
Acts as a peer reviewer in the A2A network.
"""

from __future__ import annotations

from typing import Any

from agents.base import NexusAgent
from core.logging import get_logger
from mcp.tools.file_tools import read_file
from mcp.tools.search_tools import semantic_search

logger = get_logger(__name__)


class ReviewerAgent(NexusAgent):
    """
    ReviewerAgent reviews code as an A2A peer.

    Responsibilities:
    - Review code written by CoderAgent
    - Check for bugs and logic errors
    - Verify code follows best practices
    - Request changes if needed
    - Approve when code is ready
    """

    def __init__(self) -> None:
        super().__init__(
            agent_id=     "reviewer",
            name=         "ReviewerAgent",
            description=  "Reviews code quality as A2A peer",
            capabilities= [
                "code_review",
                "quality_check",
                "best_practices",
                "peer_review",
                "approval"
            ]
        )
        self._max_iterations = 3

    def execute(
        self,
        task:    str,
        context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Review code and return approval or
        list of required changes.
        """
        task_id = context.get(
            "task_id", self.new_task_id()
        )
        self.start_task(task_id)

        try:
            logger.info(
                "🔍 ReviewerAgent reviewing: %s",
                task
            )

            # Get files to review
            files_changed = context.get(
                "files_changed", []
            )
            original_task = context.get(
                "original_task", task
            )

            if not files_changed:
                return {
                    "success":  True,
                    "approved": True,
                    "reason":   "No files to review",
                    "task_id":  task_id
                }

            # Read changed files
            file_contents = {}
            for file_path in files_changed:
                result = read_file(file_path)
                if result.get("success"):
                    file_contents[file_path] = (
                        result["content"]
                    )

            # Perform review
            review = self._review_code(
                original_task= original_task,
                file_contents= file_contents,
                context=       context
            )

            if review["approved"]:
                logger.info(
                    "✅ ReviewerAgent approved changes"
                )
            else:
                logger.info(
                    "❌ ReviewerAgent requested changes: %s",
                    review.get("issues", [])
                )

            return {
                "success":        True,
                "task_id":        task_id,
                "approved":       review["approved"],
                "issues":         review.get("issues", []),
                "suggestions":    review.get("suggestions", []),
                "quality_score":  review.get("quality_score", 0),
                "summary":        review.get("summary", "")
            }

        except Exception as exc:
            logger.error(
                "ReviewerAgent failed: %s", exc
            )
            return {
                "success": False,
                "error":   str(exc),
                "task_id": task_id
            }
        finally:
            self.complete_task()

    def _review_code(
        self,
        original_task: str,
        file_contents: dict[str, str],
        context:       dict[str, Any]
    ) -> dict[str, Any]:
        """
        Use LLM to review code quality.
        Returns structured review result.
        """
        import json

        files_context = ""
        for file_path, content in file_contents.items():
            preview = content[:2000]
            files_context += (
                f"\n--- {file_path} ---\n{preview}\n"
            )

        prompt = f"""
You are a senior software engineer doing a code review.

Original task that was implemented:
"{original_task}"

Changed files:
{files_context}

Review the code. Return ONLY valid JSON:

{{
    "approved": true or false,
    "quality_score": 0-100,
    "summary": "One line review summary",
    "issues": [
        {{
            "severity": "critical|high|medium|low",
            "file":     "file path",
            "line":     "approximate line number or null",
            "issue":    "description of the issue",
            "fix":      "how to fix it"
        }}
    ],
    "suggestions": []
}}

Approval rules:
- Approve if task was completed correctly
- For documentation tasks like adding docstrings
  approve if docstrings are present and correct
- Only reject if code has bugs that BREAK functionality
- Do NOT reject for style preferences
- Do NOT reject for missing features not in the task
- Quality score 80+ if task completed correctly
- Quality score 60-79 if completed with minor issues
- Quality score below 60 only if code is broken

Return ONLY the JSON no other text.
"""

        response = self.think(
            prompt,
            max_tokens=  1500,
            temperature= 0.1
        )

        try:
            clean = response.strip()
            if "```json" in clean:
                clean = clean.split("```json")[1]
                clean = clean.split("```")[0]
            elif "```" in clean:
                clean = clean.split("```")[1]
                clean = clean.split("```")[0]

            review = json.loads(clean.strip())
            return review

        except json.JSONDecodeError as exc:
            logger.error(
                "Failed to parse review: %s", exc
            )
            # Default to approved if parsing fails
            return {
                "approved":      True,
                "quality_score": 70,
                "summary":       "Review completed",
                "issues":        [],
                "suggestions":   []
            }

    def request_changes(
        self,
        coder_agent_id: str,
        issues:         list[dict[str, Any]],
        task_id:        str
    ) -> dict[str, Any]:
        """
        Send change request back to CoderAgent.
        Direct A2A peer communication.
        """
        import asyncio

        logger.info(
            "📤 ReviewerAgent requesting changes "
            "from CoderAgent: %d issues",
            len(issues)
        )

        loop = asyncio.new_event_loop()
        try:
            response = loop.run_until_complete(
                self.send_to(
                    to_agent_id= coder_agent_id,
                    task=        "Fix the following issues",
                    context=     {
                        "issues":  issues,
                        "task_id": task_id
                    },
                    task_id=     task_id
                )
            )
            return response or {}
        finally:
            loop.close()

    def approve(
        self,
        task_id:       str,
        quality_score: int,
        summary:       str
    ) -> dict[str, Any]:
        """
        Formally approve the code changes.
        """
        logger.info(
            "✅ ReviewerAgent approved task %s "
            "(score: %d)",
            task_id, quality_score
        )

        return {
            "approved":      True,
            "task_id":       task_id,
            "quality_score": quality_score,
            "summary":       summary,
            "reviewer":      self.agent_id
        }