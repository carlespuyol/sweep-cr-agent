"""analyze_file node — LLM-backed per-file analysis.

Used as the target of Send() fan-out. Each invocation receives
state with ``current_file`` set to one changed file dict.
"""

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from pr_review.config import AgentName, Complexity
from pr_review.observability import get_langchain_handler, observe
from pr_review.prompts.templates import FILE_ANALYSIS_PROMPT, SYSTEM_PROMPT
from pr_review.state import PRReviewState
from pr_review.utils import get_llm

logger = logging.getLogger("pr_review.nodes.file_analyzer")


class FileAnalysisResult(BaseModel):
    """Structured output for per-file analysis."""

    summary: str = Field(description="What changed in this file and why it matters.")
    risk_indicators: list[str] = Field(
        description="Concrete risk concerns (thread safety, performance, etc.)."
    )
    complexity_contribution: float = Field(
        description="File's complexity contribution on a 1.0-10.0 scale.",
        ge=1.0,
        le=10.0,
    )
    focus_areas: list[str] = Field(
        description="Specific code locations or patterns to review closely."
    )


@observe(name=AgentName.FILE_ANALYZER)
def analyze_file(state: PRReviewState) -> dict[str, Any]:
    """Analyze a single changed file and return a FileAnalysis dict."""
    current_file = state.get("current_file")
    if current_file is None:
        raise ValueError(
            "analyze_file: 'current_file' missing from state. "
            "This node must be invoked via Send()."
        )

    file_path = current_file.get("path", "unknown")

    prompt = FILE_ANALYSIS_PROMPT.format(
        pr_title=state.get("pr_title", ""),
        pr_description=state.get("pr_description", ""),
        triage_complexity=state.get("triage_complexity", Complexity.COMPLEX),
        file_path=file_path,
        file_status=current_file.get("status", "unknown"),
        lines_added=current_file.get("lines_added", 0),
        lines_removed=current_file.get("lines_removed", 0),
        diff=current_file.get("diff", ""),
    )

    llm = get_llm(AgentName.FILE_ANALYZER)
    structured_llm = llm.with_structured_output(FileAnalysisResult)

    handler = get_langchain_handler()
    config = {"callbacks": [handler]} if handler else {}

    try:
        result: FileAnalysisResult = structured_llm.invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)],
            config=config,
        )
        if result is None:
            raise ValueError("LLM returned no structured output.")
    except Exception as exc:
        logger.error("File analysis failed for %s: %s", file_path, exc)
        return {
            "file_analyses": [
                {
                    "path": file_path,
                    "risk_indicators": [f"Analysis failed: {exc}"],
                    "complexity_contribution": 5.0,
                    "summary": f"LLM analysis failed for this file: {exc}",
                    "focus_areas": ["Manual review required due to analysis failure."],
                }
            ],
            "reasoning_trace": [
                f"Step 3 (file): File analysis for {file_path} failed (LLM error)."
            ],
        }

    logger.info("Analyzed file: %s (complexity: %.1f)", file_path, result.complexity_contribution)

    return {
        "file_analyses": [
            {
                "path": file_path,
                "risk_indicators": result.risk_indicators,
                "complexity_contribution": result.complexity_contribution,
                "summary": result.summary,
                "focus_areas": result.focus_areas,
            }
        ],
        "reasoning_trace": [
            f"Step 3 (file): Analyzed {file_path} — "
            f"complexity {result.complexity_contribution:.1f}/10, "
            f"{len(result.risk_indicators)} risk indicator(s)."
        ],
    }
