"""Shared helpers used across graph nodes."""

import logging
import os
import sys
from typing import Any

from langchain_openai import ChatOpenAI

from pr_review.config import AGENT_MODELS, DEFAULT_MODEL

logger = logging.getLogger("pr_review")

_TOGETHER_BASE_URL = "https://api.together.xyz/v1"


def get_llm(agent_name: str = "default") -> ChatOpenAI:
    """Return a configured ChatOpenAI instance pointed at Together.ai for the given agent.

    The model is resolved from AGENT_MODELS in pr_review/config.py.
    Falls back to DEFAULT_MODEL if the agent name is not registered.
    Raises a clear error if TOGETHER_API_KEY is missing.
    """
    api_key = os.environ.get("TOGETHER_API_KEY")
    if not api_key:
        print(
            "Error: TOGETHER_API_KEY is not set. "
            "Add it to your .env file or environment.",
            file=sys.stderr,
        )
        raise ValueError("TOGETHER_API_KEY environment variable is not set.")

    model = AGENT_MODELS.get(agent_name, DEFAULT_MODEL)
    logger.debug("Agent '%s' using model '%s'.", agent_name, model)

    try:
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=_TOGETHER_BASE_URL,
            temperature=0,
            max_tokens=4096,
        )
    except Exception as exc:
        logger.error("Failed to initialize LLM for agent '%s': %s", agent_name, exc)
        raise


def format_file_paths(changed_files: list[dict[str, Any]]) -> str:
    """Format changed file paths as a bulleted list."""
    return "\n".join(
        f"- `{f['path']}` ({f['status']}, +{f['lines_added']}/-{f['lines_removed']})"
        for f in changed_files
    )


def format_changed_files_summary(changed_files: list[dict[str, Any]]) -> str:
    """Format a summary of changed files for architecture analysis."""
    lines = []
    for f in changed_files:
        lines.append(
            f"### {f['path']} ({f['status']})\n"
            f"- Lines added: {f['lines_added']}\n"
            f"- Lines removed: {f['lines_removed']}"
        )
    return "\n\n".join(lines)


def format_diffs(changed_files: list[dict[str, Any]]) -> str:
    """Concatenate all diffs with file path headers."""
    sections = []
    for f in changed_files:
        sections.append(f"### {f['path']}\n```diff\n{f.get('diff', '')}\n```")
    return "\n\n".join(sections)


def format_file_analyses(file_analyses: list[dict[str, Any]]) -> str:
    """Format per-file analysis results for downstream prompts."""
    if not file_analyses:
        return ""
    lines = ["## Per-File Analysis Results"]
    for fa in file_analyses:
        lines.append(f"\n### {fa['path']}")
        lines.append(f"- **Summary**: {fa['summary']}")
        lines.append(f"- **Complexity contribution**: {fa['complexity_contribution']}")
        lines.append(f"- **Risk indicators**: {', '.join(fa['risk_indicators']) if fa['risk_indicators'] else 'None'}")
        lines.append(f"- **Focus areas**: {', '.join(fa['focus_areas']) if fa['focus_areas'] else 'None'}")
    return "\n".join(lines)
