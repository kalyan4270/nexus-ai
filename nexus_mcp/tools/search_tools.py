"""Semantic and pattern search tools for Nexus AI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.config import get_settings
from core.llm import complete
from core.logging import get_logger
from safety.guardrails import check_operation

logger   = get_logger(__name__)
settings = get_settings()


def search_pattern(
    pattern:    str,
    directory:  str = ".",
    file_types: list[str] | None = None,
    max_results: int = 30
) -> dict[str, Any]:
    """
    Search for exact pattern across codebase.
    Risk: LOW — fully automatic.
    """
    result = check_operation(
        "search_codebase",
        safety_level=settings.safety_level
    )

    if not result.allowed:
        return {"error": result.reason, "success": False}

    try:
        base       = Path(settings.target_repo_path) / directory
        file_types = file_types or ["*.py"]
        matches    = []

        for file_type in file_types:
            for file_path in base.glob(f"**/{file_type}"):
                if not file_path.is_file():
                    continue
                try:
                    content = file_path.read_text(encoding="utf-8")
                    lines   = content.splitlines()

                    for i, line in enumerate(lines, 1):
                        if pattern.lower() in line.lower():
                            # Include context lines
                            start   = max(0, i - 2)
                            end     = min(len(lines), i + 2)
                            context = lines[start:end]

                            matches.append({
                                "file":       str(
                                    file_path.relative_to(
                                        Path(settings.target_repo_path)
                                    )
                                ),
                                "line":       i,
                                "content":    line.strip(),
                                "context":    "\n".join(context)
                            })

                            if len(matches) >= max_results:
                                break
                except Exception:
                    continue

                if len(matches) >= max_results:
                    break

        logger.info(
            "🔍 Pattern '%s': %d matches",
            pattern, len(matches)
        )

        return {
            "success":  True,
            "pattern":  pattern,
            "matches":  matches,
            "count":    len(matches)
        }

    except Exception as exc:
        logger.error(
            "Pattern search failed: %s", exc
        )
        return {"error": str(exc), "success": False}


def semantic_search(
    query:      str,
    directory:  str = ".",
    max_files:  int = 10
) -> dict[str, Any]:
    """
    Use LLM to find semantically relevant
    code sections for a given query.
    Risk: LOW — fully automatic.
    """
    result = check_operation(
        "search_codebase",
        safety_level=settings.safety_level
    )

    if not result.allowed:
        return {"error": result.reason, "success": False}

    try:
        base = Path(settings.target_repo_path) / directory

        # First collect all Python files
        all_files = [
            f for f in base.glob("**/*.py")
            if f.is_file()
        ][:50]  # limit for LLM context

        # Build file summary for LLM
        file_summaries = []
        for f in all_files:
            try:
                content = f.read_text(encoding="utf-8")
                rel     = str(
                    f.relative_to(
                        Path(settings.target_repo_path)
                    )
                )
                # First 200 chars as preview
                preview = content[:200].replace("\n", " ")
                file_summaries.append(
                    f"{rel}: {preview}"
                )
            except Exception:
                continue

        files_context = "\n".join(file_summaries)

        # Ask LLM to find relevant files
        prompt = f"""
You are a code search assistant.

The developer is looking for: "{query}"

Here are the available files and their previews:
{files_context}

Return ONLY a JSON list of the most relevant
file paths (max {max_files}), ordered by relevance.
Example: ["agents/orchestrator.py", "core/llm.py"]

Return ONLY the JSON list, nothing else.
"""

        response = complete(
            prompt,
            max_tokens=256,
            temperature=0.1
        )

        # Parse response
        import json
        try:
            relevant_files = json.loads(response.strip())
        except json.JSONDecodeError:
            # Fallback — extract file paths from response
            relevant_files = [
                line.strip().strip('"').strip("'")
                for line in response.splitlines()
                if ".py" in line
            ][:max_files]

        # Read relevant files
        results = []
        for file_path in relevant_files[:max_files]:
            full_path = Path(settings.target_repo_path) / file_path
            if full_path.exists():
                content = full_path.read_text(encoding="utf-8")
                results.append({
                    "file":    file_path,
                    "content": content[:2000],  # first 2000 chars
                    "lines":   len(content.splitlines())
                })

        logger.info(
            "🧠 Semantic search '%s': %d files found",
            query, len(results)
        )

        return {
            "success": True,
            "query":   query,
            "results": results,
            "count":   len(results)
        }

    except Exception as exc:
        logger.error(
            "Semantic search failed: %s", exc
        )
        return {"error": str(exc), "success": False}


def find_function(
    function_name: str,
    directory:     str = "."
) -> dict[str, Any]:
    """
    Find a specific function definition
    across the codebase.
    Risk: LOW — fully automatic.
    """
    result = check_operation(
        "search_codebase",
        safety_level=settings.safety_level
    )

    if not result.allowed:
        return {"error": result.reason, "success": False}

    try:
        base    = Path(settings.target_repo_path) / directory
        matches = []

        for file_path in base.glob("**/*.py"):
            if not file_path.is_file():
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
                lines   = content.splitlines()

                for i, line in enumerate(lines, 1):
                    if (
                        f"def {function_name}" in line or
                        f"class {function_name}" in line
                    ):
                        # Get full function body
                        end = min(i + 30, len(lines))
                        body = "\n".join(lines[i-1:end])

                        matches.append({
                            "file":      str(
                                file_path.relative_to(
                                    Path(settings.target_repo_path)
                                )
                            ),
                            "line":      i,
                            "signature": line.strip(),
                            "body":      body
                        })
            except Exception:
                continue

        logger.info(
            "🔍 Function '%s': %d matches",
            function_name, len(matches)
        )

        return {
            "success":       True,
            "function_name": function_name,
            "matches":       matches,
            "count":         len(matches)
        }

    except Exception as exc:
        logger.error(
            "Function search failed: %s", exc
        )
        return {"error": str(exc), "success": False}


def analyze_imports(
    file_path: str
) -> dict[str, Any]:
    """
    Analyze all imports in a file to
    understand dependencies.
    Risk: LOW — fully automatic.
    """
    result = check_operation(
        "read_file",
        safety_level=settings.safety_level
    )

    if not result.allowed:
        return {"error": result.reason, "success": False}

    try:
        full_path = Path(settings.target_repo_path) / file_path

        if not full_path.exists():
            return {
                "error":   f"File not found: {file_path}",
                "success": False
            }

        content = full_path.read_text(encoding="utf-8")
        lines   = content.splitlines()

        imports         = []
        local_imports   = []
        stdlib_imports  = []
        third_party     = []

        for line in lines:
            line = line.strip()
            if not (
                line.startswith("import ") or
                line.startswith("from ")
            ):
                continue

            imports.append(line)

            # Classify import
            if line.startswith("from .") or \
               line.startswith("from .."):
                local_imports.append(line)
            elif any(
                line.startswith(f"from {pkg}") or
                line.startswith(f"import {pkg}")
                for pkg in [
                    "agents", "core", "graph",
                    "mcp", "a2a", "safety",
                    "services", "models", "storage"
                ]
            ):
                local_imports.append(line)
            elif any(
                pkg in line
                for pkg in [
                    "os", "sys", "re", "json",
                    "typing", "pathlib", "datetime",
                    "threading", "subprocess",
                    "dataclasses", "functools",
                    "collections", "itertools"
                ]
            ):
                stdlib_imports.append(line)
            else:
                third_party.append(line)

        logger.info(
            "📦 Analyzed imports in %s: %d total",
            file_path, len(imports)
        )

        return {
            "success":        True,
            "file_path":      file_path,
            "all_imports":    imports,
            "local":          local_imports,
            "stdlib":         stdlib_imports,
            "third_party":    third_party,
            "total":          len(imports)
        }

    except Exception as exc:
        logger.error(
            "Import analysis failed: %s", exc
        )
        return {"error": str(exc), "success": False}