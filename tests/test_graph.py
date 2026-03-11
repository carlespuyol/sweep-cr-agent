"""Integration test for the PR review graph.

Runs the full pipeline on pr_input.json and validates
the output schema.
"""

import json
import os

import pytest
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture
def pr_data():
    """Load the test PR input."""
    pr_path = os.path.join(os.path.dirname(__file__), "..", "data", "input", "pr_input.json")
    with open(pr_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.skipif(
    not os.environ.get("TOGETHER_API_KEY"),
    reason="TOGETHER_API_KEY not set",
)
def test_full_pipeline(pr_data):
    """Run the graph on pr_input.json and validate the output schema."""
    from pr_review.graph import build_review_graph

    graph = build_review_graph()
    result = graph.invoke({"raw_pr": pr_data})

    # Validate required fields exist
    assert result["risk_level"] in ("low", "medium", "high")
    assert isinstance(result["risk_reasoning"], str) and len(result["risk_reasoning"]) > 0
    assert isinstance(result["architectural_impact"], str) and len(result["architectural_impact"]) > 0
    assert isinstance(result["review_focus_areas"], list) and len(result["review_focus_areas"]) > 0
    assert 1.0 <= result["complexity_score"] <= 10.0
    assert 0.0 <= result["confidence"] <= 1.0
    assert isinstance(result["reasoning_trace"], list) and len(result["reasoning_trace"]) >= 4


def test_parse_pr_validates_input():
    """Test that parse_pr rejects invalid input."""
    from pr_review.nodes.parse import parse_pr

    with pytest.raises(ValueError, match="raw_pr"):
        parse_pr({})

    with pytest.raises(ValueError, match="changed_files"):
        parse_pr({"raw_pr": {"pr_title": "test", "changed_files": []}})
