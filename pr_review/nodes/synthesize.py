"""synthesize node — LLM-backed final aggregation.

Takes all intermediate results (triage, and optionally file analyses
and architectural analysis) and produces the final review assessment.

On the simple path (triage -> synthesize), this node works directly
from raw PR data and diffs. On the complex path, it also incorporates
per-file analyses and architectural analysis from upstream nodes.
"""

import logging
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from pr_review.config import AgentName
from pr_review.observability import get_langchain_handler, observe
from pr_review.prompts.templates import SYNTHESIZE_PROMPT, SYSTEM_PROMPT
from pr_review.state import PRReviewState
from pr_review.utils import (
    format_changed_files_summary,
    format_diffs,
    format_file_analyses,
    get_llm,
)

logger = logging.getLogger("pr_review.nodes.synthesize")


class SynthesisResult(BaseModel):
    """Structured output for final synthesis."""

    architectural_impact: str = Field(
        description="How this PR affects Flask's architecture — new abstractions, "
        "state management, public API surface, cross-cutting concerns."
    )
    risk_level: Literal["low", "medium", "high"] = Field(
        description="Overall risk level of the PR."
    )
    risk_reasoning: str = Field(
        description="1-3 sentence explanation of the risk level."
    )
    review_focus_areas: list[str] = Field(
        description="3-5 specific areas a human reviewer should focus on."
    )
    complexity_score: float = Field(
        description="Overall complexity on a 1.0-10.0 scale.",
        ge=1.0,
        le=10.0,
    )
    confidence: float = Field(
        description="Confidence in assessment on a 0.0-1.0 scale.",
        ge=0.0,
        le=1.0,
    )


def _build_upstream_section(state: PRReviewState) -> str:
    """Build the upstream analysis section for the prompt.

    On the complex path, this includes file analyses and architectural
    analysis. On the simple path, this is empty — synthesize works
    directly from diffs.
    """
    parts: list[str] = []

    file_analyses = state.get("file_analyses", [])
    if file_analyses:
        parts.append(format_file_analyses(file_analyses))

    arch_impact = state.get("architectural_impact", "")
    cross_cutting = state.get("cross_cutting_concerns", [])
    if arch_impact:
        parts.append("## Architectural Analysis (from upstream)")
        parts.append(f"- **Impact**: {arch_impact}")
        concerns = ", ".join(cross_cutting) if cross_cutting else "None identified"
        parts.append(f"- **Cross-cutting concerns**: {concerns}")

    security_issues = state.get("security_issues", [])
    security_severity = state.get("security_severity", "none")
    if security_issues:
        lines = [
            "## Security Analysis (from upstream)",
            f"- **Overall severity**: {security_severity}",
        ]
        for issue in security_issues:
            lines.append(
                f"- [{issue['severity'].upper()}] **{issue['category']}** in "
                f"`{issue['file_path']}` ({issue['line_reference']}): "
                f"{issue['description']}"
            )
        parts.append("\n".join(lines))
    elif security_severity and security_severity != "none":
        parts.append(
            f"## Security Analysis (from upstream)\n"
            f"- **Overall severity**: {security_severity}"
        )

    if not parts:
        parts.append(
            "## Note\n"
            "No upstream per-file or architectural analysis was performed "
            "(simple PR path). Perform your own architectural assessment "
            "directly from the diffs below."
        )

    return "\n\n".join(parts)


@observe(name=AgentName.SYNTHESIZE)
def synthesize(state: PRReviewState) -> dict[str, Any]:
    """Aggregate all analysis into final review output."""
    changed_files = state.get("changed_files", [])

    prompt = SYNTHESIZE_PROMPT.format(
        pr_title=state.get("pr_title", ""),
        pr_description=state.get("pr_description", ""),
        author=state.get("author", ""),
        files_changed=state.get("files_changed", 0),
        total_additions=state.get("total_additions", 0),
        total_deletions=state.get("total_deletions", 0),
        triage_complexity=state.get("triage_complexity", "unknown"),
        triage_reasoning=state.get("triage_reasoning", ""),
        upstream_analysis_section=_build_upstream_section(state),
        changed_files_summary=format_changed_files_summary(changed_files),
        diffs=format_diffs(changed_files),
        reasoning_trace="\n".join(state.get("reasoning_trace", [])),
    )

    llm = get_llm(AgentName.SYNTHESIZE)
    structured_llm = llm.with_structured_output(SynthesisResult)

    handler = get_langchain_handler()
    config = {"callbacks": [handler]} if handler else {}

    try:
        result: SynthesisResult = structured_llm.invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)],
            config=config,
        )
        if result is None:
            raise ValueError("LLM returned no structured output.")
    except Exception as exc:
        logger.error("Synthesis failed: %s", exc)
        return {
            "architectural_impact": f"Synthesis failed due to LLM error: {exc}",
            "risk_level": "medium",
            "risk_reasoning": f"Synthesis failed due to LLM error: {exc}. "
            "Defaulting to medium risk — manual review recommended.",
            "review_focus_areas": ["Manual review required due to analysis failure."],
            "complexity_score": 5.0,
            "confidence": 0.3,
            "reasoning_trace": [
                "Step 6: Synthesis failed (LLM error), using fallback defaults."
            ],
        }

    logger.info(
        "Synthesis: risk=%s, complexity=%.1f, confidence=%.2f",
        result.risk_level,
        result.complexity_score,
        result.confidence,
    )

    return {
        "architectural_impact": result.architectural_impact,
        "risk_level": result.risk_level,
        "risk_reasoning": result.risk_reasoning,
        "review_focus_areas": result.review_focus_areas,
        "complexity_score": result.complexity_score,
        "confidence": result.confidence,
        "reasoning_trace": [
            f"Step 6: Synthesis complete — risk={result.risk_level}, "
            f"complexity={result.complexity_score:.1f}, "
            f"confidence={result.confidence:.2f}."
        ],
    }
