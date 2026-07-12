"""Domain-specific exceptions."""

from __future__ import annotations


class CodeGuardianError(Exception):
    """Base exception for application errors."""


class GitHubAPIError(CodeGuardianError):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class ReviewNotFoundError(CodeGuardianError):
    def __init__(self, repo: str, pr_number: int) -> None:
        self.repo = repo
        self.pr_number = pr_number
        super().__init__(f"No review found for {repo} PR #{pr_number}")


class TranscriptionError(CodeGuardianError):
    pass


class LLMRateLimitError(CodeGuardianError):
    def __init__(
        self,
        detail: str,
        models_tried: list[str],
        retry_after: str | None = None,
    ) -> None:
        self.detail = detail
        self.models_tried = models_tried
        self.retry_after = retry_after
        hint = f" Retry after {retry_after}." if retry_after else ""
        super().__init__(
            f"Groq rate limit reached for {', '.join(models_tried)}.{hint}"
        )
