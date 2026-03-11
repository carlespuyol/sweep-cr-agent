"""CLI entry point for the PR Review Assistant.

Usage:
    python analyze_pr.py --pr data/input/pr_input.json --output data/output/code_review_output.json
"""

import argparse
import json
import logging
import sys
import warnings
from pathlib import Path

from dotenv import load_dotenv

# Suppress spurious Pydantic serialization warning triggered by openai 2.x internals:
# ParsedChatCompletionMessage.parsed is typed as Optional[T] (generic), which Pydantic
# resolves as `None` type at schema-build time, but the actual value is a Pydantic model.
warnings.filterwarnings(
    "ignore",
    message="Pydantic serializer warnings",
    category=UserWarning,
    module="pydantic",
)

from pr_review.graph import build_review_graph
from pr_review.observability import setup_langfuse, trace_invoke


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Analyze a pull request and produce an intelligent review summary."
    )
    parser.add_argument(
        "--pr",
        required=True,
        help="Path to the PR input JSON file.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write the review output JSON file.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    logger = logging.getLogger("pr_review")

    # Load PR input
    try:
        with open(args.pr, "r", encoding="utf-8") as f:
            pr_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: PR input file not found: {args.pr}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"Error: Invalid JSON in {args.pr}: {exc}", file=sys.stderr)
        sys.exit(1)

    logger.info("Loaded PR input from %s", args.pr)

    setup_langfuse()
    # Build and invoke the graph
    graph = build_review_graph()
    trace_name = f"PR Review - {Path(args.pr).stem}"

    try:
        final_state = trace_invoke(graph, {"raw_pr": pr_data}, name=trace_name)
    except Exception as exc:
        print(f"Error: Graph execution failed: {exc}", file=sys.stderr)
        logger.exception("Graph execution failed")
        sys.exit(1)

    # Normalize reasoning_trace: deduplicate (operator.add accumulates across nodes)
    # and ensure each step is numbered.
    raw_trace = final_state.get("reasoning_trace", [])
    seen: set[str] = set()
    deduped_trace: list[str] = []
    for step in raw_trace:
        if step not in seen:
            seen.add(step)
            deduped_trace.append(step)

    # Extract output fields
    output: dict[str, object] = {
        "risk_level": final_state.get("risk_level", "medium"),
        "risk_reasoning": final_state.get("risk_reasoning", ""),
        "architectural_impact": final_state.get("architectural_impact", ""),
        "review_focus_areas": final_state.get("review_focus_areas", []),
        "complexity_score": final_state.get("complexity_score", 5.0),
        "confidence": final_state.get("confidence", 0.5),
        "reasoning_trace": deduped_trace,
    }

    # Write output
    try:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except OSError as exc:
        print(f"Error: Could not write output file: {exc}", file=sys.stderr)
        sys.exit(1)

    logger.info("Review output written to %s", args.output)
    if args.verbose:
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
