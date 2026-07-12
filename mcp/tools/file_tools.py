"""File system tools for Nexus AI MCP server."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.config import get_settings
from core.logging import get_logger
from safety.guardrails import check_operation, request_confirmation
from safety.rollback import rollback_manager

logger = get_logger(__name__)
settings = get_settings()


def _resolve_path(file_path: str) -> Path:
    """
    Resolve file path relative to
    target repo or absolute.
    """
    path = Path(file_path)
    if path.is_absolute():
        return path
    return Path(settings.target_repo_path) / path


def read_file(file_path: str) -> dict[str, Any]:
    """
    Read contents of any file.
    Risk: LOW — fully automatic.
    """
    result = check_operation(
        "read_file",
        safety_level=settings.safety_level
    )

    if not result.allowed:
        return {"error": result.reason, "success": False}

    try:
        path = _resolve_path(file_path)

        if not path.exists():
            return {
                "error":   f"File not found: {file_path}",
                "success": False
            }

        content = path.read_text(encoding="utf-8")
        logger.info("📖 Read file: %s (%d chars)", file_path, len(content))

        return {
            "success":    True,
            "file_path":  file_path,
            "content":    content,
            "lines":      len(content.splitlines()),
            "size_chars": len(content)
        }

    except Exception as exc:
        logger.error("Failed to read %s: %s", file_path, exc)
        return {"error": str(exc), "success": False}


def list_files(
    directory:  str = ".",
    pattern:    str = "**/*.py",
    max_files:  int = 50
) -> dict[str, Any]:
    """
    List files in directory matching pattern.
    Risk: LOW — fully automatic.
    """
    result = check_operation(
        "list_files",
        safety_level=settings.safety_level
    )

    if not result.allowed:
        return {"error": result.reason, "success": False}

    try:
        base = _resolve_path(directory)

        if not base.exists():
            return {
                "error":   f"Directory not found: {directory}",
                "success": False
            }

        files = [
            str(f.relative_to(base))
            for f in base.glob(pattern)
            if f.is_file()
        ][:max_files]

        logger.info(
            "📁 Listed %d files in %s",
            len(files), directory
        )

        return {
            "success":   True,
            "directory": directory,
            "pattern":   pattern,
            "files":     files,
            "count":     len(files)
        }

    except Exception as exc:
        logger.error(
            "Failed to list files in %s: %s",
            directory, exc
        )
        return {"error": str(exc), "success": False}


def write_file(
    file_path: str,
    content:   str,
    description: str = ""
) -> dict[str, Any]:
    """
    Write content to a file.
    Risk: MEDIUM — requires confirmation
    in strict mode.
    Automatically backs up before writing.
    """
    result = check_operation(
        "write_file",
        safety_level=settings.safety_level
    )

    if not result.allowed:
        return {"error": result.reason, "success": False}

    # Show diff and ask confirmation if needed
    if result.requires_confirmation:
        path = _resolve_path(file_path)
        diff = None

        if path.exists():
            old_content = path.read_text(encoding="utf-8")
            # Simple diff — show first 500 chars of new content
            diff = (
                f"OLD ({len(old_content)} chars) → "
                f"NEW ({len(content)} chars)\n\n"
                f"New content preview:\n"
                f"{content[:500]}..."
            )

        approved = request_confirmation(
            operation=   "write_file",
            description= description or f"Write to {file_path}",
            diff=        diff
        )

        if not approved:
            return {
                "success": False,
                "reason":  "User rejected write operation"
            }

    try:
        path = _resolve_path(file_path)

        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)

        # Log operation
        op_id = rollback_manager.log_operation(
            operation=   "write_file",
            file_path=   file_path,
            description= description or f"Write to {file_path}"
        )

        # Backup existing file
        rollback_manager.backup_file(file_path, op_id)

        # Write new content
        path.write_text(content, encoding="utf-8")

        # Mark complete
        rollback_manager.complete_operation(op_id)

        logger.info(
            "✅ Written: %s (%d chars)",
            file_path, len(content)
        )

        return {
            "success":      True,
            "file_path":    file_path,
            "chars_written": len(content),
            "operation_id": op_id,
            "backed_up":    True
        }

    except Exception as exc:
        logger.error(
            "Failed to write %s: %s",
            file_path, exc
        )
        return {"error": str(exc), "success": False}


def search_codebase(
    query:     str,
    directory: str = ".",
    pattern:   str = "**/*.py",
    max_results: int = 20
) -> dict[str, Any]:
    """
    Search codebase for text pattern.
    Risk: LOW — fully automatic.
    """
    result = check_operation(
        "search_codebase",
        safety_level=settings.safety_level
    )

    if not result.allowed:
        return {"error": result.reason, "success": False}

    try:
        base    = _resolve_path(directory)
        matches = []

        for file_path in base.glob(pattern):
            if not file_path.is_file():
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
                lines   = content.splitlines()

                for i, line in enumerate(lines, 1):
                    if query.lower() in line.lower():
                        matches.append({
                            "file":    str(file_path.relative_to(base)),
                            "line":    i,
                            "content": line.strip()
                        })

                        if len(matches) >= max_results:
                            break

            except Exception:
                continue

            if len(matches) >= max_results:
                break

        logger.info(
            "🔍 Search '%s': %d matches",
            query, len(matches)
        )

        return {
            "success": True,
            "query":   query,
            "matches": matches,
            "count":   len(matches)
        }

    except Exception as exc:
        logger.error(
            "Search failed for '%s': %s",
            query, exc
        )
        return {"error": str(exc), "success": False}


def explain_code(
    file_path:  str,
    start_line: int = 1,
    end_line:   int = 50
) -> dict[str, Any]:
    """
    Extract specific lines from a file
    for agent analysis.
    Risk: LOW — fully automatic.
    """
    result = check_operation(
        "read_file",
        safety_level=settings.safety_level
    )

    if not result.allowed:
        return {"error": result.reason, "success": False}

    try:
        path = _resolve_path(file_path)

        if not path.exists():
            return {
                "error":   f"File not found: {file_path}",
                "success": False
            }

        lines   = path.read_text(encoding="utf-8").splitlines()
        extract = lines[start_line - 1:end_line]

        return {
            "success":    True,
            "file_path":  file_path,
            "start_line": start_line,
            "end_line":   min(end_line, len(lines)),
            "content":    "\n".join(extract),
            "total_lines": len(lines)
        }

    except Exception as exc:
        logger.error(
            "Failed to explain %s: %s",
            file_path, exc
        )
        return {"error": str(exc), "success": False}