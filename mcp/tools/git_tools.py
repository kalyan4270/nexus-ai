"""Git operation tools for Nexus AI MCP server."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import git

from core.config import get_settings
from core.logging import get_logger
from safety.guardrails import check_operation, request_confirmation
from safety.rollback import rollback_manager

logger   = get_logger(__name__)
settings = get_settings()


def _get_repo() -> git.Repo:
    """Get git repo from target path."""
    return git.Repo(settings.target_repo_path)


def get_status() -> dict[str, Any]:
    """
    Get current git status.
    Risk: LOW — fully automatic.
    """
    result = check_operation(
        "read_file",
        safety_level=settings.safety_level
    )

    if not result.allowed:
        return {"error": result.reason, "success": False}

    try:
        repo = _get_repo()

        changed = [item.a_path for item in repo.index.diff(None)]
        untracked = repo.untracked_files
        staged = [item.a_path for item in repo.index.diff("HEAD")]

        return {
            "success":      True,
            "branch":       repo.active_branch.name,
            "changed":      changed,
            "untracked":    untracked,
            "staged":       staged,
            "is_dirty":     repo.is_dirty(),
            "commit":       repo.head.commit.hexsha[:8],
            "commit_msg":   repo.head.commit.message.strip()
        }

    except Exception as exc:
        logger.error("Git status failed: %s", exc)
        return {"error": str(exc), "success": False}


def create_branch(branch_name: str) -> dict[str, Any]:
    try:
        repo = _get_repo()

        # ✅ Always checkout main first
        # so nexus branch is based on main
        try:
            repo.git.checkout("main")
            repo.git.pull("origin", "main")
            logger.info("✅ Checked out main before branching")
        except Exception as e:
            logger.warning(
                "Could not checkout main: %s", e
            )

        branch = repo.create_head(branch_name)
        branch.checkout()

        op_id = rollback_manager.log_operation(
            operation=   "create_branch",
            description= f"Created branch: {branch_name}"
        )
        rollback_manager.complete_operation(op_id)

        logger.info("🌿 Created branch: %s", branch_name)

        return {
            "success":     True,
            "branch_name": branch_name,
            "base":        "main",
            "message":     f"Created from main: {branch_name}"
        }

    except Exception as exc:
        logger.error("Failed to create branch: %s", exc)
        return {"error": str(exc), "success": False}


def get_diff(
    file_path: str | None = None
) -> dict[str, Any]:
    """
    Get current diff of changes.
    Risk: LOW — fully automatic.
    """
    result = check_operation(
        "read_file",
        safety_level=settings.safety_level
    )

    if not result.allowed:
        return {"error": result.reason, "success": False}

    try:
        repo = _get_repo()
        diff = repo.git.diff(file_path) if file_path else repo.git.diff()

        return {
            "success":   True,
            "diff":      diff,
            "file_path": file_path,
            "has_changes": bool(diff)
        }

    except Exception as exc:
        logger.error("Failed to get diff: %s", exc)
        return {"error": str(exc), "success": False}


def stage_files(
    file_paths: list[str] | None = None
) -> dict[str, Any]:
    """
    Stage files for commit.
    Risk: MEDIUM — confirms in strict mode.
    """
    result = check_operation(
        "create_branch",
        safety_level=settings.safety_level
    )

    if not result.allowed:
        return {"error": result.reason, "success": False}

    if result.requires_confirmation:
        files_str = ", ".join(file_paths or ["all files"])
        approved  = request_confirmation(
            operation=   "stage_files",
            description= f"Stage for commit: {files_str}"
        )
        if not approved:
            return {
                "success": False,
                "reason":  "User rejected staging"
            }

    try:
        repo = _get_repo()

        if file_paths:
            repo.index.add(file_paths)
        else:
            repo.git.add(A=True)

        staged = [
            item.a_path
            for item in repo.index.diff("HEAD")
        ]

        logger.info(
            "📦 Staged %d files",
            len(staged)
        )

        return {
            "success":     True,
            "staged_files": staged,
            "count":       len(staged)
        }

    except Exception as exc:
        logger.error("Failed to stage files: %s", exc)
        return {"error": str(exc), "success": False}

def create_pr(
    title:       str,
    description: str,
    base_branch: str = "main"
) -> dict[str, Any]:

    result = check_operation(
        "create_pr",
        safety_level=settings.safety_level
    )

    if not result.allowed:
        return {"error": result.reason, "success": False}

    if result.requires_confirmation:
        approved = request_confirmation(
            operation=   "create_pr",
            description= f"Create PR: {title}",
            diff=        f"Base: {base_branch}\n\n{description}"
        )
        if not approved:
            return {
                "success": False,
                "reason":  "User rejected PR creation"
            }

    try:
        import httpx
        # ✅ Fix — use module level settings not local
        from core.config import get_settings as _get_settings
        _settings = _get_settings()

        repo   = _get_repo()
        origin = repo.remotes.origin.url

        # Extract owner/repo
        if "github.com" in origin:
            parts     = origin.replace(".git", "").split("/")
            repo_name = f"{parts[-2]}/{parts[-1]}"
        else:
            return {
                "error":   "Not a GitHub repository",
                "success": False
            }

        current_branch = repo.active_branch.name

        # Push current branch
        repo.remotes.origin.push(
            refspec=f"{current_branch}:{current_branch}"
        )
        logger.info("⬆️ Pushed branch: %s", current_branch)

        # Check if PR already exists
        existing = httpx.get(
            f"https://api.github.com/repos/{repo_name}/pulls",
            headers={
                "Authorization": f"Bearer {_settings.github_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            params={
                "head":  f"kalyan4270:{current_branch}",
                "base":  base_branch,
                "state": "open"
            }
        )

        if existing.status_code == 200:
            existing_prs = existing.json()
            if existing_prs:
                pr = existing_prs[0]
                logger.info(
                    "PR already exists: #%s",
                    pr["number"]
                )
                return {
                    "success":   True,
                    "pr_number": pr["number"],
                    "pr_url":    pr["html_url"],
                    "title":     pr["title"],
                    "message":   "PR already exists"
                }

        # Create new PR
        response = httpx.post(
            f"https://api.github.com/repos/{repo_name}/pulls",
            headers={
                "Authorization": f"Bearer {_settings.github_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            json={
                "title": title,
                "body":  description,
                "head":  current_branch,
                "base":  base_branch
            }
        )

        # Handle 422
        if response.status_code == 422:
            error_data = response.json()
            errors     = error_data.get("errors", [])
            logger.error("PR 422 details: %s", error_data)

            for err in errors:
                msg = str(err.get("message", ""))
                if "already exists" in msg:
                    return {
                        "success": True,
                        "message": "PR already exists",
                        "pr_url":  None
                    }
                if "No commits between" in msg:
                    return {
                        "success": False,
                        "error":   "No changes to merge"
                    }

            return {
                "success": False,
                "error":   f"422: {error_data}"
            }

        response.raise_for_status()
        pr_data = response.json()

        op_id = rollback_manager.log_operation(
            operation=   "create_pr",
            description= f"PR #{pr_data['number']}: {title}"
        )
        rollback_manager.complete_operation(op_id)

        logger.info(
            "🔗 PR created: #%s — %s",
            pr_data["number"],
            pr_data["html_url"]
        )

        return {
            "success":     True,
            "pr_number":   pr_data["number"],
            "pr_url":      pr_data["html_url"],
            "title":       title,
            "base_branch": base_branch,
            "head_branch": current_branch
        }

    except Exception as exc:
        logger.error("Failed to create PR: %s", exc)
        return {"error": str(exc), "success": False}

def commit_changes(
    message: str,
    files:   list[str] | None = None
) -> dict[str, Any]:
    """
    Stage and commit all changes.
    Called after CoderAgent writes files.
    Risk: MEDIUM — auto in balanced mode.
    """
    result = check_operation(
        "create_branch",
        safety_level=settings.safety_level
    )

    if not result.allowed:
        return {"error": result.reason, "success": False}

    try:
        repo = _get_repo()

        # Stage files
        if files:
            for f in files:
                try:
                    repo.index.add([f])
                except Exception as e:
                    logger.warning(
                        "Could not stage %s: %s", f, e
                    )
        else:
            # Stage all changed files
            repo.git.add(A=True)

        # Check if anything to commit
        if not repo.index.diff("HEAD") and \
           not repo.untracked_files:
            logger.warning("Nothing to commit")
            return {
                "success": False,
                "error":   "No changes to commit"
            }

        # Commit
        commit = repo.index.commit(message)

        logger.info(
            "📝 Committed: %s [%s]",
            message, commit.hexsha[:8]
        )

        op_id = rollback_manager.log_operation(
            operation=   "commit",
            description= message
        )
        rollback_manager.complete_operation(op_id)

        return {
            "success":     True,
            "commit_hash": commit.hexsha[:8],
            "message":     message,
            "files":       files or ["all changed files"]
        }

    except Exception as exc:
        logger.error("Failed to commit: %s", exc)
        return {"error": str(exc), "success": False}


def get_commit_history(
    file_path: str | None = None,
    limit:     int = 10
) -> dict[str, Any]:
    """
    Get recent commit history.
    Risk: LOW — fully automatic.
    """
    result = check_operation(
        "read_file",
        safety_level=settings.safety_level
    )

    if not result.allowed:
        return {"error": result.reason, "success": False}

    try:
        repo    = _get_repo()
        commits = list(repo.iter_commits(
            paths=file_path,
            max_count=limit
        ))

        history = [
            {
                "hash":    c.hexsha[:8],
                "message": c.message.strip(),
                "author":  c.author.name,
                "date":    c.authored_datetime.isoformat()
            }
            for c in commits
        ]

        return {
            "success":   True,
            "file_path": file_path,
            "commits":   history,
            "count":     len(history)
        }

    except Exception as exc:
        logger.error(
            "Failed to get commit history: %s", exc
        )
        return {"error": str(exc), "success": False}