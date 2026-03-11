"""LangGraph workflow for PR review analysis.

Constructs and compiles the StateGraph with conditional routing
(simple vs complex path) and Send() fan-out for per-file analysis.

Topology:
    parse_pr -> triage --(complex)--> analyze_file (Send fan-out) -> arch_analysis -> security_analysis -> synthesize -> format_output
                       --(simple)----------------------------------------------------------------------> synthesize -> format_output
"""

import logging
from typing import Union

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from pr_review.config import AgentName, Complexity
from pr_review.nodes.architecture import arch_analysis
from pr_review.nodes.file_analyzer import analyze_file
from pr_review.nodes.format import format_output
from pr_review.nodes.parse import parse_pr
from pr_review.nodes.security import security_analysis
from pr_review.nodes.synthesize import synthesize
from pr_review.nodes.triage import triage
from pr_review.state import PRReviewState

logger = logging.getLogger("pr_review.graph")


def route_after_triage(state: PRReviewState) -> Union[str, list[Send]]:
    """Conditional edge after triage.

    - **simple**: Skip per-file fan-out and arch_analysis, go directly
      to synthesize. The synthesize node handles architectural assessment
      from raw diffs when no upstream analysis is available.
    - **complex**: Fan-out via Send() to analyze each file in parallel,
      then converge at arch_analysis before synthesize.
    """
    complexity = state.get("triage_complexity", Complexity.COMPLEX)

    if complexity == Complexity.SIMPLE:
        logger.info("Simple PR — routing directly to synthesize.")
        return AgentName.SYNTHESIZE

    # Complex path: fan-out one Send() per changed file
    changed_files = state.get("changed_files", [])
    logger.info(
        "Complex PR — fanning out to %d file analysis node(s).",
        len(changed_files),
    )
    return [
        Send(AgentName.FILE_ANALYZER, {**state, "current_file": f})
        for f in changed_files
    ]


def build_review_graph() -> StateGraph:
    """Build and compile the PR review graph.

    Returns a compiled StateGraph ready for invocation.
    """
    graph = StateGraph(PRReviewState)

    # -- Add nodes --
    graph.add_node(AgentName.PARSE_PR, parse_pr)
    graph.add_node(AgentName.TRIAGE, triage)
    graph.add_node(AgentName.FILE_ANALYZER, analyze_file)
    graph.add_node(AgentName.ARCH_ANALYSIS, arch_analysis)
    graph.add_node(AgentName.SECURITY_ANALYSIS, security_analysis)
    graph.add_node(AgentName.SYNTHESIZE, synthesize)
    graph.add_node(AgentName.FORMAT_OUTPUT, format_output)

    # -- Wire edges --
    graph.add_edge(START, AgentName.PARSE_PR)
    graph.add_edge(AgentName.PARSE_PR, AgentName.TRIAGE)

    # Conditional: triage decides simple (-> synthesize) or complex (-> Send fan-out)
    graph.add_conditional_edges(
        AgentName.TRIAGE,
        route_after_triage,
        [AgentName.FILE_ANALYZER, AgentName.SYNTHESIZE],
    )

    # Fan-in: all analyze_file instances converge at arch_analysis
    graph.add_edge(AgentName.FILE_ANALYZER, AgentName.ARCH_ANALYSIS)

    # Complex path continues: arch_analysis -> security_analysis -> synthesize
    graph.add_edge(AgentName.ARCH_ANALYSIS, AgentName.SECURITY_ANALYSIS)
    graph.add_edge(AgentName.SECURITY_ANALYSIS, AgentName.SYNTHESIZE)

    # Both paths converge: synthesize -> format_output -> END
    graph.add_edge(AgentName.SYNTHESIZE, AgentName.FORMAT_OUTPUT)
    graph.add_edge(AgentName.FORMAT_OUTPUT, END)

    return graph.compile()
