# Intelligent PR Review Assistant

## Project Overview

LangGraph-based multi-agent system that analyzes pull requests and produces structured review summaries. Built for the Flask open-source project to help maintainers triage PRs efficiently.

**Input**: JSON file with PR metadata and diffs
**Output**: JSON file with risk assessment, architectural impact, focus areas, complexity score, confidence, and reasoning trace

## Architecture

### Graph Topology

```
parse_pr -> triage --(complex)--> [analyze_file via Send()] -> arch_analysis -> security_analysis -> synthesize -> format_output
                   --(simple)----------------------------------------------------------------------> synthesize -> format_output
```

- **parse_pr** (pure Python): Parse JSON input, extract metadata. No LLM.
- **triage** (LLM): Classify PR complexity as simple/complex. Conditional routing.
- **analyze_file** (LLM, Send()): Per-file parallel analysis. Complex PRs only.
- **arch_analysis** (LLM): Cross-file architectural analysis. Complex PRs only.
- **security_analysis** (LLM): Scans diffs for OWASP-style security vulnerabilities. Complex PRs only. Findings feed into synthesize to influence risk_level, risk_reasoning, and confidence.
- **synthesize** (LLM): Final aggregation. Always runs. On simple path, performs its own architectural and security assessment from raw diffs.
- **format_output** (pure Python): Validate schema, clamp scores. No LLM.

### Key Files

- `analyze_pr.py` — CLI entry point
- `pr_review/state.py` — State TypedDicts (PRReviewState, FileAnalysis, SecurityIssue)
- `pr_review/graph.py` — Graph construction and compilation
- `pr_review/nodes/` — One file per node
- `pr_review/prompts/templates.py` — All prompt templates
- `tests/test_graph.py` — Integration test

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the PR analysis
python analyze_pr.py --pr data/input/pr_input.json --output data/output/code_review_output.json

# Run tests
python -m pytest tests/ -v
```

## Code Style & Quality Standards

- Python 3.9+ with type hints on all function signatures
- Each node is a pure function: `(state: PRReviewState) -> dict` returning only the fields it sets
- Use `with_structured_output()` (Pydantic models) for all LLM responses — no regex parsing
- Prompts live in `pr_review/prompts/templates.py`, never inline in node code
- `temperature=0` for all LLM calls (deterministic reviews)
- Use `meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8` via Together.ai (OpenAI-compatible endpoint) using `langchain-openai`

## Error Handling Requirements

- Graceful failure on invalid/missing JSON input with clear error messages
- LLM call failures caught and reported (API errors, rate limits, malformed responses)
- Structured output validation with fallback defaults if parsing fails
- CLI exits with non-zero code on failure, descriptive stderr messages
- Each node validates its required state fields before processing

## What NOT to Build

- No UI or web interface
- No real GitHub API integration
- No database or persistence layer
- No authentication system
- No deployment configuration
- No extensive test suite (one integration test is fine)

## Environment

- API key via `.env` file (python-dotenv) or `TOGETHER_API_KEY` env var
- `.env` is gitignored — use `.env.example` as template

