"""security_analysis node — LLM-backed security vulnerability analysis.

Only runs on the complex path. Receives diffs and per-file analyses,
scans for OWASP-style security vulnerabilities, and produces findings
that feed into synthesize to influence risk_level, risk_reasoning,
and confidence.
"""

import logging
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from pr_review.config import AgentName
from pr_review.observability import get_langchain_handler, observe
from pr_review.prompts.templates import SECURITY_ANALYSIS_PROMPT, SYSTEM_PROMPT
from pr_review.state import PRReviewState
from pr_review.utils import (
    format_changed_files_summary,
    format_diffs,
    format_file_analyses,
    get_llm,
)

logger = logging.getLogger("pr_review.nodes.security")


class SecurityFinding(BaseModel):
    """A single security vulnerability finding."""

    category: str = Field(
        description="Vulnerability category (injection, xss, hardcoded_secret, "
        "insecure_default, path_traversal, unsafe_deserialization, csrf, "
        "information_disclosure, insecure_crypto)."
    )
    severity: Literal["low", "medium", "high", "critical"] = Field(
        description="Severity of the finding."
    )
    file_path: str = Field(
        description="File where the issue was found."
    )
    description: str = Field(
        description="Description of the vulnerability and its potential exploit scenario."
    )
    line_reference: str = Field(
        description="Function, class, or line range involved."
    )


class SecurityAnalysisResult(BaseModel):
    """Structured output for security analysis."""

    issues: list[SecurityFinding] = Field(
        description="List of security issues found. Empty if none."
    )
    overall_severity: Literal["none", "low", "medium", "high", "critical"] = Field(
        description="Highest severity among all findings, or 'none' if no issues."
    )


@observe(name=AgentName.SECURITY_ANALYSIS)
def security_analysis(state: PRReviewState) -> dict[str, Any]:
    """Scan diffs for security vulnerabilities."""
    changed_files = state.get("changed_files", [])
    if not changed_files:
        raise ValueError("security_analysis: 'changed_files' is empty or missing.")

    file_analyses = state.get("file_analyses", [])
    file_analyses_section = format_file_analyses(file_analyses)

    prompt = SECURITY_ANALYSIS_PROMPT.format(
        pr_title=state.get("pr_title", ""),
        pr_description=state.get("pr_description", ""),
        files_changed=state.get("files_changed", 0),
        total_additions=state.get("total_additions", 0),
        total_deletions=state.get("total_deletions", 0),
        changed_files_summary=format_changed_files_summary(changed_files),
        diffs=format_diffs(changed_files),
        file_analyses_section=file_analyses_section,
    )

    llm = get_llm(AgentName.SECURITY_ANALYSIS)
    structured_llm = llm.with_structured_output(SecurityAnalysisResult)

    handler = get_langchain_handler()
    config = {"callbacks": [handler]} if handler else {}

    try:
        result: SecurityAnalysisResult = structured_llm.invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)],
            config=config,
        )
        if result is None:
            raise ValueError("LLM returned no structured output.")
    except Exception as exc:
        logger.error("Security analysis failed: %s", exc)
        return {
            "security_issues": [],
            "security_severity": "none",
            "reasoning_trace": [
                "Step 5: Security analysis failed (LLM error)."
            ],
        }

    # Convert Pydantic models to dicts for state
    issues = [
        {
            "category": finding.category,
            "severity": finding.severity,
            "file_path": finding.file_path,
            "description": finding.description,
            "line_reference": finding.line_reference,
        }
        for finding in result.issues
    ]

    issue_count = len(issues)
    logger.info(
        "Security analysis: %d issue(s), overall_severity=%s",
        issue_count,
        result.overall_severity,
    )

    return {
        "security_issues": issues,
        "security_severity": result.overall_severity,
        "reasoning_trace": [
            f"Step 5: Security analysis complete — "
            f"{issue_count} issue(s) found, "
            f"overall severity: {result.overall_severity}."
        ],
    }
