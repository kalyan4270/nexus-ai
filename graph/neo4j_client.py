from __future__ import annotations

from typing import Any

from core.config import get_settings
from core.logging import get_logger
from neo4j import GraphDatabase

logger = get_logger(__name__)

_VALID_DEPENDENCY_TYPES = frozenset({"IMPORTS", "CALLS", "EXTENDS", "IMPLEMENTS"})


class Neo4jClient:
    """Neo4j driver wrapper for repository knowledge graph operations."""

    def __init__(self) -> None:
        settings = get_settings()
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )

    def close(self) -> None:
        self._driver.close()

    def verify_connection(self) -> str:
        with self._driver.session() as session:
            result = session.run("RETURN 'Connected to Neo4j' AS message")
            record = result.single()
            return record["message"] if record else "Connected to Neo4j"

    def create_repository(self, repo_name: str) -> None:
        with self._driver.session() as session:
            session.run(
                """
                MERGE (r:Repository {name: $repo_name})
                ON CREATE SET r.created_at = datetime()
                ON MATCH SET r.last_seen = datetime()
                """,
                repo_name=repo_name,
            )

    def create_file_node(self, repo_name: str, file_path: str) -> None:
        with self._driver.session() as session:
            session.run(
                """
                MERGE (r:Repository {name: $repo_name})
                MERGE (f:File {path: $file_path, repo: $repo_name})
                ON CREATE SET f.created_at = datetime()
                MERGE (r)-[:CONTAINS]->(f)
                """,
                repo_name=repo_name,
                file_path=file_path,
            )

    def create_dependency(
        self,
        repo_name: str,
        source_file: str,
        target_file: str,
        dependency_type: str = "IMPORTS",
    ) -> None:
        if dependency_type not in _VALID_DEPENDENCY_TYPES:
            raise ValueError(f"Unsupported dependency type: {dependency_type}")

        with self._driver.session() as session:
            session.run(
                f"""
                MERGE (s:File {{path: $source, repo: $repo_name}})
                MERGE (t:File {{path: $target, repo: $repo_name}})
                MERGE (s)-[:{dependency_type}]->(t)
                """,
                source=source_file,
                target=target_file,
                repo_name=repo_name,
            )

    def store_pr_review(
        self,
        repo_name: str,
        pr_number: int,
        pr_title: str,
        changed_files: list[str],
        summary: str,
    ) -> None:
        with self._driver.session() as session:
            session.run(
                """
                MERGE (r:Repository {name: $repo_name})
                CREATE (pr:PullRequest {
                    number: $pr_number,
                    title: $pr_title,
                    reviewed_at: datetime(),
                    summary: $summary
                })
                MERGE (r)-[:HAS_PR]->(pr)
                """,
                repo_name=repo_name,
                pr_number=pr_number,
                pr_title=pr_title,
                summary=summary,
            )
            for file_path in changed_files:
                session.run(
                    """
                    MATCH (pr:PullRequest {number: $pr_number})
                    MERGE (f:File {path: $file_path, repo: $repo_name})
                    MERGE (pr)-[:CHANGED]->(f)
                    """,
                    pr_number=pr_number,
                    file_path=file_path,
                    repo_name=repo_name,
                )

    def get_file_dependencies(self, repo_name: str, file_path: str) -> list[str]:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (f:File {path: $file_path, repo: $repo_name})
                      <-[:IMPORTS|CALLS|EXTENDS|IMPLEMENTS]-(dependent:File)
                RETURN dependent.path AS path
                """,
                file_path=file_path,
                repo_name=repo_name,
            )
            return [record["path"] for record in result]

    def get_downstream_impact(self, repo_name: str, changed_files: list[str]) -> dict[str, list[str]]:
        impact_map: dict[str, list[str]] = {}
        for file_path in changed_files:
            dependents = self.get_file_dependencies(repo_name, file_path)
            if dependents:
                impact_map[file_path] = dependents
        return impact_map

    def get_pr_history(self, repo_name: str, file_path: str, limit: int = 5) -> list[dict[str, Any]]:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (pr:PullRequest)-[:CHANGED]->(f:File {
                    path: $file_path,
                    repo: $repo_name
                })
                RETURN pr.number AS pr_number,
                       pr.title AS title,
                       pr.reviewed_at AS reviewed_at
                ORDER BY pr.reviewed_at DESC
                LIMIT $limit
                """,
                file_path=file_path,
                repo_name=repo_name,
                limit=limit,
            )
            return [dict(record) for record in result]

    def get_most_changed_files(self, repo_name: str, limit: int = 10) -> list[dict[str, Any]]:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (pr:PullRequest)-[:CHANGED]->(f:File {repo: $repo_name})
                RETURN f.path AS file, COUNT(pr) AS change_count
                ORDER BY change_count DESC
                LIMIT $limit
                """,
                repo_name=repo_name,
                limit=limit,
            )
            return [dict(record) for record in result]


neo4j_client = Neo4jClient()
