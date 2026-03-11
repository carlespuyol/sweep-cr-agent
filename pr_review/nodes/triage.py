"""triage node — LLM-backed complexity classification.

Classifies the PR as "simple" or "complex" to drive conditional
routing in the graph. Uses structured output via Pydantic.
"""

import logging
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from pr_review.config import AgentName, Complexity
from pr_review.observability import get_langchain_handler, observe
from pr_review.prompts.templates import SYSTEM_PROMPT, TRIAGE_PROMPT
from pr_review.state import PRReviewState
from pr_review.utils import format_file_paths, get_llm

logger = logging.getLogger("pr_review.nodes.triage")


class TriageResult(BaseModel):
    """Structured output schema for the triage node."""

    complexity: Literal["simple", "complex"] = Field(
        description="Whether the PR is simple or complex."
    )
    reasoning: str = Field(
        description="One or two sentences explaining the classification."
    )


@observe(name=AgentName.TRIAGE)
def triage(state: PRReviewState) -> dict[str, Any]:
    """Classify PR complexity and store result in state."""
    changed_files = state.get("changed_files", [])
    if not changed_files:
        raise ValueError("triage: 'changed_files' is empty or missing.")

    prompt = TRIAGE_PROMPT.format(
        pr_title=state.get("pr_title", ""),
        pr_description=state.get("pr_description", ""),
        author=state.get("author", ""),
        files_changed=state.get("files_changed", 0),
        total_additions=state.get("total_additions", 0),
        total_deletions=state.get("total_deletions", 0),
        file_paths=format_file_paths(changed_files),
    )

    llm = get_llm(AgentName.TRIAGE)
    structured_llm = llm.with_structured_output(TriageResult)

    handler = get_langchain_handler()
    config = {"callbacks": [handler]} if handler else {}

    try:
        result: TriageResult = structured_llm.invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)],
            config=config,
        )
        if result is None:
            raise ValueError("Structured output parsing returned None — LLM response may not match the expected schema.")
    except Exception as exc:
        logger.error("Triage LLM call failed: %s", exc)
        # Fallback: classify as complex to ensure thorough analysis
        return {
            "triage_complexity": Complexity.COMPLEX,
            "triage_reasoning": f"Defaulted to complex due to LLM error: {exc}",
            "reasoning_trace": [
                "Step 2: Triage failed (LLM error), defaulting to complex."
            ],
        }

    logger.info("Triage result: %s — %s", result.complexity, result.reasoning)

    return {
        "triage_complexity": result.complexity,
        "triage_reasoning": result.reasoning,
        "reasoning_trace": [
            f"Step 2: Triage classified PR as '{result.complexity}': "
            f"{result.reasoning}"
        ],
    }
