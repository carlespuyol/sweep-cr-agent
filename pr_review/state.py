"""State schema for the PR review graph.

Defines the TypedDicts that flow through the LangGraph StateGraph.
Uses Annotated reducers for fields that receive parallel writes (fan-out).
"""

import operator
from typing import Annotated, Any, Literal, TypedDict


class FileAnalysis(TypedDict):
    """Result of analyzing a single changed file."""

    path: str
    risk_indicators: list[str]
    complexity_contribution: float
    summary: str
    focus_areas: list[str]


class SecurityIssue(TypedDict):
    """A single security finding from the security analysis node."""

    category: str  # e.g., "injection", "xss", "hardcoded_secret", "insecure_default"
    severity: str  # "low", "medium", "high", "critical"
    file_path: str
    description: str
    line_reference: str  # function, class, or line range


class PRReviewState(TypedDict, total=False):
    """Full state flowing through the PR review graph.

    Fields are grouped by the node that writes them.
    ``total=False`` allows nodes to return partial dicts
    containing only the keys they set.
    """

    # -- Input: loaded from JSON before graph invocation --
    raw_pr: dict[str, Any]

    # -- Set by parse_pr (immutable after) --
    pr_title: str
    pr_description: str
    author: str
    changed_files: list[dict[str, Any]]
    total_additions: int
    total_deletions: int
    files_changed: int

    # -- Set by triage --
    triage_complexity: Literal["simple", "complex"]
    triage_reasoning: str

    # -- Set per Send() invocation for analyze_file --
    current_file: dict[str, Any]

    # -- Parallel-safe: each Send() target appends via reducer --
    file_analyses: Annotated[list[FileAnalysis], operator.add]

    # -- Set by arch_analysis --
    architectural_impact: str
    cross_cutting_concerns: list[str]

    # -- Set by security_analysis (internal, not exposed in output) --
    security_issues: Annotated[list[SecurityIssue], operator.add]
    security_severity: str  # "none", "low", "medium", "high", "critical"

    # -- Set by synthesize --
    risk_level: Literal["low", "medium", "high"]
    risk_reasoning: str
    review_focus_areas: list[str]
    complexity_score: float
    confidence: float

    # -- Accumulated by every node via reducer --
    reasoning_trace: Annotated[list[str], operator.add]
