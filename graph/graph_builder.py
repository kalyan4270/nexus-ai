from __future__ import annotations

from typing import Any

from graph.neo4j_client import neo4j_client

_STD_LIBRARY_PREFIXES = frozenset({
    "os", "sys", "re", "json", "typing", "asyncio", "datetime", "concurrent",
})
_THIRD_PARTY_PREFIXES = frozenset({
    "fastapi", "groq", "neo4j", "langchain", "langgraph", "pydantic", "dotenv", "httpx",
})


def extract_changed_files(pr_diff: str) -> list[str]:
    files: list[str] = []
    for line in pr_diff.splitlines():
        if not line.startswith("diff --git"):
            continue
        parts = line.split()
        if len(parts) >= 4:
            files.append(parts[3].removeprefix("b/"))
    return files


def extract_imports(pr_diff: str, file_path: str) -> list[str]:
    imports: list[str] = []
    in_target_file = False

    for line in pr_diff.splitlines():
        if line.startswith("diff --git"):
            in_target_file = file_path in line
            continue
        if in_target_file and line.startswith("+") and (
            line.startswith("+import ") or line.startswith("+from ")
        ):
            imports.append(line[1:].strip())

    return imports


def import_to_file_path(import_str: str) -> str | None:
    if import_str.startswith("from "):
        module = import_str.split()[1]
    elif import_str.startswith("import "):
        module = import_str.split()[1].split(" as ")[0]
    else:
        return None

    root_module = module.split(".")[0]
    if root_module in _STD_LIBRARY_PREFIXES or root_module in _THIRD_PARTY_PREFIXES:
        return None

    return module.replace(".", "/") + ".py"


def build_knowledge_graph(
    repo_name: str,
    pr_number: int,
    pr_title: str,
    pr_diff: str,
    pr_summary: str = "",
) -> dict[str, Any]:
    neo4j_client.create_repository(repo_name)
    changed_files = extract_changed_files(pr_diff)

    if not changed_files:
        return {
            "changed_files": [],
            "dependencies_mapped": 0,
            "message": "No file changes detected in diff",
        }

    dependencies_mapped = 0
    for file_path in changed_files:
        neo4j_client.create_file_node(repo_name, file_path)
        for import_str in extract_imports(pr_diff, file_path):
            dep_path = import_to_file_path(import_str)
            if not dep_path:
                continue
            neo4j_client.create_file_node(repo_name, dep_path)
            neo4j_client.create_dependency(
                repo_name=repo_name,
                source_file=file_path,
                target_file=dep_path,
            )
            dependencies_mapped += 1

    neo4j_client.store_pr_review(
        repo_name=repo_name,
        pr_number=pr_number,
        pr_title=pr_title,
        changed_files=changed_files,
        summary=pr_summary,
    )

    return {
        "changed_files": changed_files,
        "dependencies_mapped": dependencies_mapped,
        "message": f"Graph updated with {len(changed_files)} files",
    }
