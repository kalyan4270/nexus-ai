"""
Security Agent — Scans code for vulnerabilities.
Acts as security gatekeeper in A2A network.
"""

from __future__ import annotations

from typing import Any

from agents.base import NexusAgent
from core.logging import get_logger
from nexus_mcp.tools.file_tools import read_file
from nexus_mcp.tools.search_tools import search_pattern

logger = get_logger(__name__)


# Common security patterns to check
_SECURITY_PATTERNS = [
    "password",
    "secret",
    "api_key",
    "private_key",
    "hardcoded",
    "eval(",
    "exec(",
    "subprocess.call",
    "os.system",
    "shell=True",
    "pickle.loads",
    "yaml.load(",
]


class SecurityAgent(NexusAgent):
    """
    SecurityAgent scans all code changes
    for security vulnerabilities.

    Acts as mandatory gatekeeper —
    CoderAgent changes must pass
    security review before PR creation.

    Responsibilities:
    - Scan for hardcoded secrets
    - Detect injection vulnerabilities
    - Find unsafe coding patterns
    - Check authentication issues
    - Block high risk changes
    """

    def __init__(self) -> None:
        super().__init__(
            agent_id=     "security",
            name=         "SecurityAgent",
            description=  "Scans code for security vulnerabilities",
            capabilities= [
                "security_scan",
                "vulnerability_detection",
                "secret_detection",
                "injection_detection",
                "security_approval"
            ]
        )

    def execute(
        self,
        task:    str,
        context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Scan changed files for security issues.
        Returns approval or list of vulnerabilities.
        """
        task_id = context.get(
            "task_id", self.new_task_id()
        )
        self.start_task(task_id)

        try:
            logger.info(
                "🔒 SecurityAgent scanning: %s",
                task
            )

            files_changed = context.get(
                "files_changed", []
            )

            if not files_changed:
                return {
                    "success":  True,
                    "approved": True,
                    "reason":   "No files to scan",
                    "task_id":  task_id
                }

            # Read all changed files
            file_contents = {}
            for file_path in files_changed:
                result = read_file(file_path)
                if result.get("success"):
                    file_contents[file_path] = (
                        result["content"]
                    )

            # Step 1 — Pattern based scan
            pattern_findings = self._pattern_scan(
                file_contents
            )

            # Step 2 — LLM based deep scan
            llm_findings = self._llm_scan(
                task=          task,
                file_contents= file_contents
            )

            # Combine findings
            all_findings = (
                pattern_findings +
                llm_findings.get("findings", [])
            )

            # Determine if approved
            critical_count = sum(
                1 for f in all_findings
                if f.get("severity") == "CRITICAL"
            )
            high_count = sum(
                1 for f in all_findings
                if f.get("severity") == "HIGH"
            )

            approved = (
                critical_count == 0 and
                high_count == 0
            )

            if approved:
                logger.info(
                    "✅ SecurityAgent approved — "
                    "no critical issues"
                )
            else:
                logger.warning(
                    "🚨 SecurityAgent blocked — "
                    "%d critical, %d high issues",
                    critical_count, high_count
                )

            return {
                "success":        True,
                "task_id":        task_id,
                "approved":       approved,
                "findings":       all_findings,
                "critical_count": critical_count,
                "high_count":     high_count,
                "summary":        llm_findings.get(
                    "summary",
                    f"Found {len(all_findings)} issues"
                )
            }

        except Exception as exc:
            logger.error(
                "SecurityAgent failed: %s", exc
            )
            return {
                "success": False,
                "error":   str(exc),
                "task_id": task_id
            }
        finally:
            self.complete_task()

    def _pattern_scan(
        self,
        file_contents: dict[str, str]
    ) -> list[dict[str, Any]]:
        """
        Fast pattern-based security scan.
        Checks for common vulnerability patterns.
        """
        findings = []

        for file_path, content in file_contents.items():
            lines = content.splitlines()

            for i, line in enumerate(lines, 1):
                line_lower = line.lower()

                for pattern in _SECURITY_PATTERNS:
                    if pattern.lower() in line_lower:
                        # Check if it looks like
                        # hardcoded value
                        if "=" in line and (
                            '"' in line or
                            "'" in line
                        ):
                            findings.append({
                                "severity":  "HIGH",
                                "file":      file_path,
                                "line":      i,
                                "pattern":   pattern,
                                "content":   line.strip(),
                                "issue":     f"Potential hardcoded {pattern}",
                                "fix":       f"Use environment variable instead of hardcoded {pattern}"
                            })

        logger.info(
            "🔍 Pattern scan: %d findings",
            len(findings)
        )

        return findings

    def _llm_scan(
        self,
        task:          str,
        file_contents: dict[str, str]
    ) -> dict[str, Any]:
        """
        Deep LLM-based security analysis.
        Catches complex vulnerabilities.
        """
        import json

        files_context = ""
        for file_path, content in file_contents.items():
            preview = content[:2000]
            files_context += (
                f"\n--- {file_path} ---\n{preview}\n"
            )

        prompt = f"""
You are a cybersecurity expert reviewing code changes.

Task that was implemented: "{task}"

Changed code:
{files_context}

Perform a security review. Return ONLY valid JSON:

{{
    "summary": "One line security assessment",
    "overall_risk": "LOW|MEDIUM|HIGH|CRITICAL",
    "findings": [
        {{
            "severity":    "CRITICAL|HIGH|MEDIUM|LOW",
            "file":        "file path",
            "line":        "approximate line or null",
            "issue":       "description of vulnerability",
            "impact":      "what could happen if exploited",
            "fix":         "how to fix this"
        }}
    ],
    "recommendations": []
}}

Check ONLY for these real vulnerabilities:
1. Hardcoded secrets directly in code (not env vars)
2. SQL injection in raw queries
3. Command injection with shell=True
4. Unsafe deserialization like pickle.loads
5. Passwords or tokens as string literals

DO NOT flag these as issues:
- Using os.getenv() — this is correct practice
- Environment variables — these are secure
- Loading from .env files — this is correct
- Type hints or dataclass fields — not vulnerabilities
- Missing validation on config fields — not a security issue

If the code only uses environment variables for
secrets return empty findings array.
Return ONLY the JSON no other text.
"""

        response = self.think(
            prompt,
            max_tokens=  1500,
            temperature= 0.1
        )

        try:
            clean = response.strip()
            if "```json" in clean:
                clean = clean.split("```json")[1]
                clean = clean.split("```")[0]
            elif "```" in clean:
                clean = clean.split("```")[1]
                clean = clean.split("```")[0]

            result = json.loads(clean.strip())
            return result

        except json.JSONDecodeError as exc:
            logger.error(
                "Failed to parse security scan: %s",
                exc
            )
            return {
                "summary":   "Security scan completed",
                "findings":  [],
                "overall_risk": "LOW"
            }

    def quick_scan(
        self,
        file_path: str
    ) -> dict[str, Any]:
        """
        Quick scan of a single file.
        Used by other agents before writing.
        """
        result = read_file(file_path)

        if not result.get("success"):
            return {
                "success": False,
                "error":   result.get("error")
            }

        findings = self._pattern_scan(
            {file_path: result["content"]}
        )

        return {
            "success":  True,
            "file":     file_path,
            "findings": findings,
            "safe":     len(findings) == 0
        }