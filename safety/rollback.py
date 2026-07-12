"""Automatic file backup and rollback system."""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)


class RollbackManager:
    """
    Backs up files before any write operation.
    Restores them if something goes wrong.
    Keeps full audit log in SQLite.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.db_path  = settings.audit_db_path
        self.backup_dir = Path(".nexus_backups")
        self.backup_dir.mkdir(exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Create audit tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS operations (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT NOT NULL,
                    operation   TEXT NOT NULL,
                    file_path   TEXT,
                    description TEXT,
                    status      TEXT DEFAULT 'pending',
                    task_id     TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS backups (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_id INTEGER NOT NULL,
                    file_path    TEXT NOT NULL,
                    backup_path  TEXT NOT NULL,
                    timestamp    TEXT NOT NULL,
                    FOREIGN KEY (operation_id)
                        REFERENCES operations(id)
                )
            """)
            conn.commit()

    def backup_file(
        self,
        file_path:    str,
        operation_id: int
    ) -> str | None:
        """
        Backs up a file before modification.
        Returns backup path or None if file
        doesn't exist yet (new file).
        """
        source = Path(file_path)

        if not source.exists():
            logger.info(
                "New file — no backup needed: %s",
                file_path
            )
            return None

        # Create timestamped backup
        timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name  = file_path.replace("/", "_").replace("\\", "_")
        backup_path = self.backup_dir / f"{timestamp}_{safe_name}"

        shutil.copy2(source, backup_path)
        logger.info("💾 Backed up: %s → %s", file_path, backup_path)

        # Record in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO backups
                (operation_id, file_path, backup_path, timestamp)
                VALUES (?, ?, ?, ?)
            """, (
                operation_id,
                file_path,
                str(backup_path),
                datetime.now().isoformat()
            ))
            conn.commit()

        return str(backup_path)

    def log_operation(
        self,
        operation:   str,
        file_path:   str | None = None,
        description: str = "",
        task_id:     str | None = None
    ) -> int:
        """
        Logs an operation to audit database.
        Returns operation ID for linking backups.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO operations
                (timestamp, operation, file_path,
                 description, task_id)
                VALUES (?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                operation,
                file_path,
                description,
                task_id
            ))
            conn.commit()
            op_id = cursor.lastrowid
            logger.info(
                "📝 Logged operation #%s: %s",
                op_id, operation
            )
            return op_id

    def complete_operation(
        self,
        operation_id: int,
        status:       str = "completed"
    ) -> None:
        """Mark operation as completed or failed."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE operations
                SET status = ?
                WHERE id = ?
            """, (status, operation_id))
            conn.commit()

    def rollback_operation(self, operation_id: int) -> bool:
        """
        Restores all files backed up for
        a specific operation.
        Returns True if successful.
        """
        with sqlite3.connect(self.db_path) as conn:
            backups = conn.execute("""
                SELECT file_path, backup_path
                FROM backups
                WHERE operation_id = ?
            """, (operation_id,)).fetchall()

        if not backups:
            logger.warning(
                "No backups found for operation #%s",
                operation_id
            )
            return False

        success = True
        for file_path, backup_path in backups:
            try:
                shutil.copy2(backup_path, file_path)
                logger.info(
                    "↩️ Restored: %s", file_path
                )
            except Exception as exc:
                logger.error(
                    "Failed to restore %s: %s",
                    file_path, exc
                )
                success = False

        self.complete_operation(operation_id, "rolled_back")
        return success

    def rollback_latest(self) -> bool:
        """Rollback the most recent operation."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                SELECT id FROM operations
                WHERE status = 'completed'
                ORDER BY id DESC
                LIMIT 1
            """).fetchone()

        if not row:
            logger.warning("No operations to rollback")
            return False

        return self.rollback_operation(row[0])

    def get_history(self, limit: int = 10) -> list[dict]:
        """Get recent operation history."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT id, timestamp, operation,
                       file_path, description, status
                FROM operations
                ORDER BY id DESC
                LIMIT ?
            """, (limit,)).fetchall()

        return [
            {
                "id":          row[0],
                "timestamp":   row[1],
                "operation":   row[2],
                "file_path":   row[3],
                "description": row[4],
                "status":      row[5]
            }
            for row in rows
        ]


# Single shared instance
rollback_manager = RollbackManager()