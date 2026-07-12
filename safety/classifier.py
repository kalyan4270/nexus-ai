"""Risk classifier for all Nexus AI operations."""

from __future__ import annotations

from enum import Enum


class RiskLevel(Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


# Operations classified by risk level
_LOW_RISK = {
    "read_file",
    "list_files",
    "search_codebase",
    "query_dependencies",
    "get_impact",
    "run_tests",
    "analyze_code",
    "get_pr_history",
    "get_file_history",
    "explain_code",
    "search_pattern",
}

_MEDIUM_RISK = {
    "write_file",
    "create_file",
    "create_branch",
    "create_pr",
    "install_dependency",
    "modify_function",
    "refactor_code",
}

_HIGH_RISK = {
    "delete_file",
    "merge_pr",
    "deploy_production",
    "modify_env",
    "drop_database",
    "modify_secrets",
    "push_to_main",
    "delete_branch",
    "revert_commit",
    "force_push",
}


def classify(operation: str) -> RiskLevel:
    """
    Classify an operation by risk level.
    Unknown operations default to MEDIUM
    for safety.
    """
    if operation in _LOW_RISK:
        return RiskLevel.LOW
    if operation in _HIGH_RISK:
        return RiskLevel.HIGH
    return RiskLevel.MEDIUM


def is_blocked(operation: str) -> bool:
    """
    Returns True if operation is
    permanently blocked regardless
    of safety level.
    """
    return operation in _HIGH_RISK


def is_auto(
    operation: str,
    safety_level: str = "balanced"
) -> bool:
    """
    Returns True if operation can run
    without human confirmation.

    strict   → only LOW risk auto
    balanced → LOW auto, MEDIUM auto
    auto     → LOW + MEDIUM auto
    """
    risk = classify(operation)

    if safety_level == "strict":
        return risk == RiskLevel.LOW

    if safety_level in ("balanced", "auto"):
        return risk in (RiskLevel.LOW, RiskLevel.MEDIUM)

    return risk == RiskLevel.LOW