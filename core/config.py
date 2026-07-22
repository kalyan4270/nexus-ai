from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent

@dataclass(frozen=True, slots=True)
class Settings:
    # LLM
    groq_api_key:          str
    groq_model:            str = "llama-3.3-70b-versatile"
    groq_fallback_models:  tuple[str, ...] = ("llama-3.1-8b-instant",)

    # Neo4j
    neo4j_uri:             str = ""
    neo4j_username:        str = "neo4j"
    neo4j_password:        str = ""

    # GitHub
    github_token:          str = ""

    # Nexus specific
    target_repo_path:      str = ""
    safety_level:          str = "balanced"
    auto_create_pr:        bool = False
    auto_run_tests:        bool = True
    max_diff_chars:        int = 6_000
    audit_db_path:         Path = PROJECT_ROOT / "nexus_audit.db"

    @classmethod
    def from_env(cls) -> Settings:
        fallback_raw = os.getenv(
            "GROQ_FALLBACK_MODELS",
            "llama-3.1-8b-instant"
        )
        fallback_models = tuple(
            m.strip()
            for m in fallback_raw.split(",")
            if m.strip()
        )

        return cls(
            groq_api_key=os.getenv("GROQ_API_KEY", ""),
            groq_model=os.getenv(
                "GROQ_MODEL",
                "llama-3.3-70b-versatile"
            ),
            groq_fallback_models=fallback_models,
            neo4j_uri=os.getenv("NEO4J_URI", ""),
            neo4j_username=os.getenv("NEO4J_USERNAME", "neo4j"),
            neo4j_password=os.getenv("NEO4J_PASSWORD", ""),
            github_token=os.getenv("GITHUB_TOKEN", ""),
            target_repo_path=os.getenv("TARGET_REPO_PATH", ""),
            safety_level=os.getenv("SAFETY_LEVEL", "balanced"),
            auto_create_pr=os.getenv(
                "AUTO_CREATE_PR", "false"
            ).lower() == "true",
            auto_run_tests=os.getenv(
                "AUTO_RUN_TESTS", "true"
            ).lower() == "true",
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()