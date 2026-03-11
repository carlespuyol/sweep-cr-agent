"""parse_pr node — pure Python, no LLM.

Extracts and validates fields from the raw PR JSON input,
populating the initial graph state.
"""

import logging
from typing import Any

from pr_review.config import AgentName
from pr_review.observability import observe
from pr_review.state import PRReviewState

logger = logging.getLogger("pr_review.nodes.parse")


@observe(name=AgentName.PARSE_PR)
def parse_pr(state: PRReviewState) -> dict[str, Any]:
    """Parse raw PR data and populate state fields.

    Expects ``state["raw_pr"]`` to contain the loaded JSON dict.
    Returns the fields that downstream nodes depend on.
    """
    raw: dict[str, Any] | None = state.get("raw_pr")  # type: ignore[attr-defined]
    if raw is None:
        raise ValueError(
            "parse_pr: 'raw_pr' missing from state. "
            "Ensure the PR JSON is loaded before invoking the graph."
        )

    # Validate required top-level keys
    required_keys = ["pr_title", "changed_files"]
    missing = [k for k in required_keys if k not in raw]
    if missing:
        raise ValueError(
            f"parse_pr: PR input missing required keys: {missing}"
        )

    changed_files = raw["changed_files"]
    if not isinstance(changed_files, list) or not changed_files:
        raise ValueError(
            "parse_pr: 'changed_files' must be a non-empty list."
        )

    # Validate each file entry has required fields
    for i, f in enumerate(changed_files):
        for key in ("path", "status", "diff"):
            if key not in f:
                raise ValueError(
                    f"parse_pr: changed_files[{i}] missing required key '{key}'."
                )

    result = {
        "pr_title": raw.get("pr_title", ""),
        "pr_description": raw.get("pr_description", ""),
        "author": raw.get("author", "unknown"),
        "changed_files": changed_files,
        "total_additions": raw.get("total_additions", 0),
        "total_deletions": raw.get("total_deletions", 0),
        "files_changed": raw.get("files_changed", len(changed_files)),
        "reasoning_trace": [
            f"Step 1: Parsed PR '{raw.get('pr_title', '')}' — "
            f"{len(changed_files)} file(s) changed, "
            f"+{raw.get('total_additions', 0)}/-{raw.get('total_deletions', 0)} lines."
        ],
    }

    logger.info(
        "Parsed PR: %s (%d files, +%d/-%d)",
        result["pr_title"],
        result["files_changed"],
        result["total_additions"],
        result["total_deletions"],
    )

    return result
