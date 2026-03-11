"""format_output node — pure Python, no LLM.

Validates and formats the final output, ensuring all fields
are present and values are within expected ranges.
"""

import logging
from typing import Any

from pr_review.config import AgentName
from pr_review.observability import observe
from pr_review.state import PRReviewState

logger = logging.getLogger("pr_review.nodes.format")

VALID_RISK_LEVELS = {"low", "medium", "high"}


@observe(name=AgentName.FORMAT_OUTPUT)
def format_output(state: PRReviewState) -> dict[str, Any]:
    """Validate and clamp final output fields."""
    risk_level = state.get("risk_level", "medium")
    if risk_level not in VALID_RISK_LEVELS:
        logger.warning("Invalid risk_level '%s', defaulting to 'medium'.", risk_level)
        risk_level = "medium"

    complexity_score = state.get("complexity_score", 5.0)
    complexity_score = max(1.0, min(10.0, float(complexity_score)))

    confidence = state.get("confidence", 0.5)
    confidence = max(0.0, min(1.0, float(confidence)))

    review_focus_areas = state.get("review_focus_areas", [])
    if not review_focus_areas:
        review_focus_areas = ["No specific focus areas identified — full review recommended."]

    # Note: reasoning_trace is NOT returned here — it uses operator.add reducer,
    # so returning it would double-count all accumulated steps. The CLI reads
    # the accumulated trace directly from final_state.
    result = {
        "risk_level": risk_level,
        "risk_reasoning": state.get("risk_reasoning", "No reasoning provided."),
        "architectural_impact": state.get("architectural_impact", "No architectural analysis available."),
        "review_focus_areas": review_focus_areas,
        "complexity_score": round(complexity_score, 1),
        "confidence": round(confidence, 2),
    }

    logger.info("Formatted output: risk=%s, complexity=%.1f", result["risk_level"], result["complexity_score"])

    return result
