"""arch_analysis node — LLM-backed architectural impact analysis.

Only runs on the complex path. Receives per-file analyses from the
analyze_file fan-out and produces a cross-file architectural impact
statement and list of cross-cutting concerns.
"""
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from pr_review.config import AgentName
from pr_review.observability import get_langchain_handler, observe
from pr_review.prompts.templates import ARCH_ANALYSIS_PROMPT, SYSTEM_PROMPT
from pr_review.state import PRReviewState
from pr_review.utils import (
    format_changed_files_summary,
    format_diffs,
    format_file_analyses,
    get_llm,
)

logger = logging.getLogger("pr_review.nodes.architecture")


class ArchAnalysisResult(BaseModel):
    """Structured output for architectural analysis."""

    architectural_impact: str = Field(
        description="Concise statement of how this PR affects Flask's architecture."
    )
    cross_cutting_concerns: list[str] = Field(
        description="Cross-cutting concerns identified (new imports into core, "
        "lifecycle changes, thread safety, etc.)."
    )


@observe(name=AgentName.ARCH_ANALYSIS)
def arch_analysis(state: PRReviewState) -> dict[str, Any]:
    """Analyze cross-file architectural impact."""
    changed_files = state.get("changed_files", [])
    if not changed_files:
        raise ValueError("arch_analysis: 'changed_files' is empty or missing.")

    file_analyses = state.get("file_analyses", [])
    file_analyses_section = format_file_analyses(file_analyses)

    prompt = ARCH_ANALYSIS_PROMPT.format(
        pr_title=state.get("pr_title", ""),
        pr_description=state.get("pr_description", ""),
        files_changed=state.get("files_changed", 0),
        total_additions=state.get("total_additions", 0),
        total_deletions=state.get("total_deletions", 0),
        changed_files_summary=format_changed_files_summary(changed_files),
        diffs=format_diffs(changed_files),
        file_analyses_section=file_analyses_section,
    )

    llm = get_llm(AgentName.ARCH_ANALYSIS)
    structured_llm = llm.with_structured_output(ArchAnalysisResult)

    handler = get_langchain_handler()
    config = {"callbacks": [handler]} if handler else {}

    try:
        result: ArchAnalysisResult = structured_llm.invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)],
            config=config,
        )
        if result is None:
            raise ValueError("LLM returned no structured output.")
    except Exception as exc:
        logger.error("Architectural analysis failed: %s", exc)
        return {
            "architectural_impact": f"Analysis failed due to LLM error: {exc}",
            "cross_cutting_concerns": ["Manual architectural review required."],
            "reasoning_trace": [
                "Step 4: Architectural analysis failed (LLM error)."
            ],
        }

    logger.info("Architectural impact: %s", result.architectural_impact[:80])

    return {
        "architectural_impact": result.architectural_impact,
        "cross_cutting_concerns": result.cross_cutting_concerns,
        "reasoning_trace": [
            f"Step 4: Architectural analysis complete — "
            f"{len(result.cross_cutting_concerns)} cross-cutting concern(s) identified."
        ],
    }
