"""
Audit log for all Nexus AI operations.
Tracks every action for transparency
and debugging.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)


class AuditLog:
    """
    Persistent audit log for Nexus AI.

    Tracks:
    - Every instruction given
    - Every agent action taken
    - Every file modified
    - Every PR created
    - Full execution timeline
    """

    def __init__(self) -> None:
        settings    = get_settings()
        self.db_path = settings.audit_db_path
        self._init_db()
        logger.info("📝 Audit log initialized")

    def _init_db(self) -> None:
        """Create audit tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id      TEXT NOT NULL,
                    instruction  TEXT NOT NULL,
                    status       TEXT DEFAULT 'running',
                    confidence   INTEGER DEFAULT 0,
                    pr_url       TEXT,
                    summary      TEXT,
                    started_at   TEXT NOT NULL,
                    completed_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_actions (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id     TEXT NOT NULL,
                    agent_name  TEXT NOT NULL,
                    action      TEXT NOT NULL,
                    result      TEXT,
                    success     INTEGER DEFAULT 1,
                    timestamp   TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_changes (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id     TEXT NOT NULL,
                    file_path   TEXT NOT NULL,
                    operation   TEXT NOT NULL,
                    timestamp   TEXT NOT NULL
                )
            """)
            conn.commit()

    def log_task_start(
        self,
        task_id:     str,
        instruction: str
    ) -> None:
        """Log start of a new task."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO tasks
                (task_id, instruction, started_at)
                VALUES (?, ?, ?)
            """, (
                task_id,
                instruction,
                datetime.now().isoformat()
            ))
            conn.commit()

        logger.info(
            "📝 Task started: %s", task_id
        )

    def log_task_complete(
        self,
        task_id:    str,
        status:     str,
        confidence: int = 0,
        pr_url:     str | None = None,
        summary:    str = ""
    ) -> None:
        """Log completion of a task."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE tasks
                SET status       = ?,
                    confidence   = ?,
                    pr_url       = ?,
                    summary      = ?,
                    completed_at = ?
                WHERE task_id = ?
            """, (
                status,
                confidence,
                pr_url,
                summary,
                datetime.now().isoformat(),
                task_id
            ))
            conn.commit()

        logger.info(
            "📝 Task completed: %s [%s]",
            task_id, status
        )

    def log_agent_action(
        self,
        task_id:    str,
        agent_name: str,
        action:     str,
        result:     dict[str, Any] | None = None,
        success:    bool = True
    ) -> None:
        """Log an agent action."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO agent_actions
                (task_id, agent_name, action,
                 result, success, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                task_id,
                agent_name,
                action,
                json.dumps(result) if result else None,
                1 if success else 0,
                datetime.now().isoformat()
            ))
            conn.commit()

    def log_file_change(
        self,
        task_id:   str,
        file_path: str,
        operation: str
    ) -> None:
        """Log a file change."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO file_changes
                (task_id, file_path, operation, timestamp)
                VALUES (?, ?, ?, ?)
            """, (
                task_id,
                file_path,
                operation,
                datetime.now().isoformat()
            ))
            conn.commit()

    def get_task_history(
        self,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get recent task history."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT task_id, instruction,
                       status, confidence,
                       pr_url, summary,
                       started_at, completed_at
                FROM tasks
                ORDER BY id DESC
                LIMIT ?
            """, (limit,)).fetchall()

        return [
            {
                "task_id":      row[0],
                "instruction":  row[1],
                "status":       row[2],
                "confidence":   row[3],
                "pr_url":       row[4],
                "summary":      row[5],
                "started_at":   row[6],
                "completed_at": row[7]
            }
            for row in rows
        ]

    def get_task_details(
        self,
        task_id: str
    ) -> dict[str, Any]:
        """Get full details of a specific task."""
        with sqlite3.connect(self.db_path) as conn:
            # Get task
            task = conn.execute("""
                SELECT * FROM tasks
                WHERE task_id = ?
            """, (task_id,)).fetchone()

            # Get agent actions
            actions = conn.execute("""
                SELECT agent_name, action,
                       result, success, timestamp
                FROM agent_actions
                WHERE task_id = ?
                ORDER BY id ASC
            """, (task_id,)).fetchall()

            # Get file changes
            changes = conn.execute("""
                SELECT file_path, operation, timestamp
                FROM file_changes
                WHERE task_id = ?
                ORDER BY id ASC
            """, (task_id,)).fetchall()

        return {
            "task":    dict(task) if task else {},
            "actions": [
                {
                    "agent":     row[0],
                    "action":    row[1],
                    "result":    json.loads(row[2])
                                 if row[2] else None,
                    "success":   bool(row[3]),
                    "timestamp": row[4]
                }
                for row in actions
            ],
            "file_changes": [
                {
                    "file":      row[0],
                    "operation": row[1],
                    "timestamp": row[2]
                }
                for row in changes
            ]
        }

    def get_stats(self) -> dict[str, Any]:
        """Get overall Nexus AI statistics."""
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM tasks"
            ).fetchone()[0]

            successful = conn.execute("""
                SELECT COUNT(*) FROM tasks
                WHERE status = 'success'
            """).fetchone()[0]

            avg_confidence = conn.execute("""
                SELECT AVG(confidence) FROM tasks
                WHERE status = 'success'
            """).fetchone()[0]

            total_files = conn.execute(
                "SELECT COUNT(*) FROM file_changes"
            ).fetchone()[0]

            total_prs = conn.execute("""
                SELECT COUNT(*) FROM tasks
                WHERE pr_url IS NOT NULL
            """).fetchone()[0]

        return {
            "total_tasks":      total,
            "successful_tasks": successful,
            "success_rate":     (
                round(successful / total * 100, 1)
                if total > 0 else 0
            ),
            "avg_confidence":   round(
                avg_confidence or 0, 1
            ),
            "files_modified":   total_files,
            "prs_created":      total_prs
        }


# Single shared instance
audit_log = AuditLog()