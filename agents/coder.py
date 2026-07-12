"""
Coder Agent — Writes and modifies code.
The primary execution agent in Nexus AI.
"""

from __future__ import annotations

from typing import Any

from agents.base import NexusAgent
from core.logging import get_logger
from mcp.tools.file_tools import (
    read_file,
    write_file,
    list_files,
)
from mcp.tools.search_tools import (
    semantic_search,
    find_function,
    analyze_imports,
)

logger = get_logger(__name__)


class CoderAgent(NexusAgent):
    """
    CoderAgent writes, modifies and fixes code.

    Responsibilities:
    - Read existing code via MCP tools
    - Understand context and requirements
    - Write new or modified code
    - Fix bugs and implement features
    - Collaborate with ReviewerAgent via A2A
    """

    def __init__(self) -> None:
        super().__init__(
            agent_id=     "coder",
            name=         "CoderAgent",
            description=  "Writes and modifies code autonomously",
            capabilities= [
                "code_writing",
                "bug_fixing",
                "refactoring",
                "feature_implementation",
                "code_reading",
                "dependency_analysis"
            ]
        )

    def execute(
        self,
        task:    str,
        context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Main coding execution.
        Reads context, writes solution,
        returns result.
        """
        task_id = context.get(
            "task_id", self.new_task_id()
        )
        self.start_task(task_id)

        try:
            logger.info(
                "💻 CoderAgent executing: %s",
                task
            )

            # Step 1 — Understand what files are relevant
            relevant_files = self._find_relevant_files(
                task, context
            )

            # Step 2 — Read relevant files
            file_contents = self._read_files(
                relevant_files
            )

            # Step 3 — Generate solution
            solution = self._generate_solution(
                task=          task,
                context=       context,
                file_contents= file_contents
            )

            if not solution.get("success"):
                return solution

            # Step 4 — Write changes
            written_files = []
            for change in solution.get("changes", []):
                result = write_file(
                    file_path=   change["file_path"],
                    content=     change["content"],
                    description= change.get(
                        "description", task
                    )
                )
                if result.get("success"):
                    written_files.append(
                        change["file_path"]
                    )
                    logger.info(
                        "✅ Written: %s",
                        change["file_path"]
                    )
                else:
                    logger.error(
                        "❌ Failed to write: %s — %s",
                        change["file_path"],
                        result.get("error")
                    )

            return {
                "success":       True,
                "task":          task,
                "task_id":       task_id,
                "files_changed": written_files,
                "summary":       solution.get("summary", ""),
                "explanation":   solution.get("explanation", "")
            }

        except Exception as exc:
            logger.error(
                "CoderAgent failed: %s", exc
            )
            return {
                "success": False,
                "error":   str(exc),
                "task_id": task_id
            }
        finally:
            self.complete_task()

    def _find_relevant_files(
        self,
        task:    str,
        context: dict[str, Any]
    ) -> list[str]:
        """
        Find files relevant to the task
        using semantic search.
        """
        # Check if context already has files
        if context.get("files"):
            return context["files"]

        # Use semantic search to find relevant files
        search_result = semantic_search(
            query=     task,
            max_files= 5
        )

        if search_result.get("success"):
            return [
                r["file"]
                for r in search_result.get("results", [])
            ]

        return []

    def _read_files(
        self,
        file_paths: list[str]
    ) -> dict[str, str]:
        """
        Read content of all relevant files.
        Returns dict of file_path → content.
        """
        contents = {}
        for file_path in file_paths[:5]:  # max 5 files
            result = read_file(file_path)
            if result.get("success"):
                contents[file_path] = result["content"]
                logger.info(
                    "📖 Read: %s (%d lines)",
                    file_path,
                    result.get("lines", 0)
                )
        return contents

    def _generate_solution(
        self,
        task:          str,
        context:       dict[str, Any],
        file_contents: dict[str, str]
    ) -> dict[str, Any]:
        """
        Use LLM to generate code solution.
        Returns structured changes to make.
        """
        import json
        import re

        # Build context from file contents
        files_context = ""
        for file_path, content in file_contents.items():
            preview = content[:2000]
            files_context += (
                f"\n--- {file_path} ---\n{preview}\n"
            )

        prompt = f"""
    You are an expert Python software engineer.

    Task: {task}

    Additional context:
    {json.dumps(context.get('extra', {}), indent=2)}

    Current relevant files:
    {files_context if files_context else "No existing files found"}

    Generate the solution. Return ONLY valid JSON in this exact format:

    {{
        "summary": "One line summary of changes",
        "explanation": "Why these changes solve the task",
        "changes": [
            {{
                "file_path": "relative/path/to/file.py",
                "content": "COMPLETE file content here",
                "description": "What changed in this file"
            }}
        ]
    }}

    Rules:
    - Return COMPLETE file content not just diffs
    - Follow existing code style and patterns
    - Add proper type hints and docstrings
    - Keep changes minimal and focused
    - Escape all special characters in JSON strings
    - Use double quotes for JSON strings
    - Return ONLY the JSON no other text
    """

        response = self.think(
            prompt,
            max_tokens=  3000,
            temperature= 0.2
        )

        # ✅ Improved JSON parsing with multiple fallbacks
        try:
            clean = response.strip()

            # Remove markdown code blocks
            if "```json" in clean:
                clean = clean.split("```json")[1]
                clean = clean.split("```")[0]
            elif "```" in clean:
                clean = clean.split("```")[1]
                clean = clean.split("```")[0]

            clean = clean.strip()

            # Try direct parse first
            try:
                solution = json.loads(clean)
                logger.info(
                    "💡 Solution generated: %d file(s) to change",
                    len(solution.get("changes", []))
                )
                return {"success": True, **solution}

            except json.JSONDecodeError:
                # ✅ Fallback 1 — Fix common JSON issues
                # Replace unescaped newlines in strings
                fixed = re.sub(
                    r'(?<!\\)\n',
                    '\\n',
                    clean
                )
                try:
                    solution = json.loads(fixed)
                    logger.info(
                        "💡 Solution generated (fixed): "
                        "%d file(s)",
                        len(solution.get("changes", []))
                    )
                    return {"success": True, **solution}
                except json.JSONDecodeError:
                    pass

                # ✅ Fallback 2 — Extract content directly
                # Ask LLM again with simpler format
                logger.warning(
                    "JSON parse failed, retrying with "
                    "simpler prompt..."
                )
                return self._generate_solution_simple(
                    task, file_contents
                )

        except Exception as exc:
            logger.error(
                "Failed to parse solution: %s", exc
            )
            return {
                "success": False,
                "error":   f"Failed to generate solution: {exc}"
            }

    def _generate_solution_simple(
        self,
        task:          str,
        file_contents: dict[str, str]
    ) -> dict[str, Any]:
        """
        Simpler fallback solution generator.
        Used when main generator returns malformed JSON.
        """
        import json

        # Get first relevant file
        if not file_contents:
            return {
                "success": False,
                "error":   "No files to modify"
            }

        file_path    = list(file_contents.keys())[0]
        file_content = list(file_contents.values())[0]

        prompt = f"""
    You are a Python expert. Complete this task:
    {task}

    File to modify: {file_path}

    Current content:
    {file_content[:3000]}

    Return the COMPLETE updated file content.
    Return ONLY the Python code, nothing else.
    No JSON, no markdown, just pure Python code.
    """

        new_content = self.think(
            prompt,
            max_tokens=  3000,
            temperature= 0.1
        )

        # Clean response
        clean = new_content.strip()
        if "```python" in clean:
            clean = clean.split("```python")[1]
            clean = clean.split("```")[0]
        elif "```" in clean:
            clean = clean.split("```")[1]
            clean = clean.split("```")[0]

        clean = clean.strip()

        if not clean:
            return {
                "success": False,
                "error":   "Empty response from LLM"
            }

        logger.info(
            "💡 Simple solution generated for %s",
            file_path
        )

        return {
            "success":     True,
            "summary":     f"Applied: {task}",
            "explanation": f"Modified {file_path}",
            "changes": [
                {
                    "file_path":   file_path,
                    "content":     clean,
                    "description": task
                }
            ]
        }

    def fix_bug(
        self,
        file_path:   str,
        bug_description: str,
        error_message:   str | None = None
    ) -> dict[str, Any]:
        """
        Specialized method for bug fixing.
        Called directly by other agents.
        """
        context = {
            "files": [file_path],
            "extra": {
                "bug":   bug_description,
                "error": error_message or ""
            }
        }

        task = (
            f"Fix this bug in {file_path}: "
            f"{bug_description}"
            + (
                f". Error: {error_message}"
                if error_message else ""
            )
        )

        return self.execute(task, context)

    def add_feature(
        self,
        feature_description: str,
        target_files:        list[str] | None = None
    ) -> dict[str, Any]:
        """
        Specialized method for feature implementation.
        Called directly by other agents.
        """
        context = {
            "files": target_files or [],
            "extra": {"feature": feature_description}
        }

        return self.execute(
            f"Implement this feature: {feature_description}",
            context
        )