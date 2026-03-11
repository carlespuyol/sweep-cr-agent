# PR Review Assistant

A LangGraph-based multi-agent system that analyzes pull requests and produces structured review summaries. Built to help open-source maintainers (specifically targeting the Flask project) triage PRs efficiently by classifying risk, scoring complexity, identifying architectural impact, and surfacing specific areas for human review — all from a plain JSON representation of a PR.

---

## Architecture

### Graph Topology

The system is a directed acyclic graph with a conditional branch that selects one of two analysis paths based on PR complexity:

```
                    ┌──────────────────────────────────────────────────────────────────────┐
                    │              COMPLEX PATH                                             │
                    │                                                                       │
                    │   analyze_file (Send fan-out, parallel)                               │
                    │      ├── analyze_file [file 1]                                        │
                    │      ├── analyze_file [file 2]  ──► arch_analysis ──► security_analysis│
                    │      └── analyze_file [file N]                                        │
                    │                                                                       │
parse_pr ──► triage ┤                                                                       ├──► synthesize ──► format_output
                    │              SIMPLE PATH                                              │
                    │                                                                       │
                    │   (direct)                                                            │
                    └──────────────────────────────────────────────────────────────────────┘
```

### Node Reference

| Node | LLM | Role |
|------|-----|------|
| `parse_pr` | No | Validates and extracts fields from the raw PR JSON. Fails fast with a clear error if required keys are missing. |
| `triage` | Yes | Classifies the PR as `simple` or `complex`. Drives the conditional routing decision. Falls back to `complex` on LLM error to guarantee thorough analysis. |
| `analyze_file` | Yes | Per-file analysis invoked in parallel via `Send()`. Produces risk indicators, a complexity score, and focus areas for each changed file. Only runs on the complex path. |
| `arch_analysis` | Yes | Receives all per-file analyses and produces a cross-file architectural impact statement and list of cross-cutting concerns. Only runs on the complex path. |
| `security_analysis` | Yes | Scans diffs for OWASP-style security vulnerabilities (injection, XSS, hardcoded secrets, insecure defaults, etc.). Only runs on the complex path. Findings are internal state that feeds into `synthesize` to influence `risk_level`, `risk_reasoning`, and `confidence`. |
| `synthesize` | Yes | Aggregates all upstream analysis into the final assessment: risk level, reasoning, focus areas, complexity score, and confidence. On the simple path it performs its own architectural and security assessment directly from raw diffs. |
| `format_output` | No | Validates output fields and clamps numeric values to their allowed ranges. No LLM call needed — enforcement is pure Python. |

### LangGraph Features Used

- **`StateGraph`** — The graph is defined as a `StateGraph(PRReviewState)`, where each node is a pure function returning only the fields it sets. `total=False` on the TypedDict allows partial returns.
- **Conditional edges** — `add_conditional_edges()` on the `triage` node drives routing. The `route_after_triage` function returns either a node name (`"synthesize"`) or a list of `Send` objects.
- **`Send()` fan-out** — On the complex path, one `Send("analyze_file", {..., "current_file": f})` is emitted per changed file, causing `analyze_file` to run in parallel for each file.
- **`operator.add` reducers** — Three state fields use `Annotated[list[...], operator.add]`: `file_analyses` (receives one append per parallel `analyze_file` invocation), `security_issues` (accumulated by the security analysis node), and `reasoning_trace` (accumulated by every node). This makes parallel writes safe without any locking.
- **`with_structured_output()`** — Every LLM-backed node binds a Pydantic `BaseModel` schema to the LLM via `llm.with_structured_output(Model)`. This ensures responses are deserialized directly into typed objects, with no regex parsing.

---

## Design Decisions

### Two-path routing: simple vs. complex

Routing to a lighter path for simple PRs (e.g., documentation fixes, single-file typo corrections) avoids unnecessary LLM calls for per-file analysis and architectural review. The triage node classifies the PR based on title, description, file count, and line counts — and routes simple PRs directly to `synthesize`, skipping `analyze_file` and `arch_analysis` entirely. This reduces latency and cost for the majority of PRs that are straightforward.

The fallback on triage failure is `complex`, not `simple`. A false-negative (calling a complex PR simple) produces a shallower review; a false-positive (calling a simple PR complex) wastes compute but produces a correct review. The conservative direction is always to be thorough.

### Why `synthesize` handles architectural assessment on the simple path

Rather than adding a separate conditional branch for architectural analysis on the simple path, `synthesize` detects whether upstream analysis is available (by checking `file_analyses` and `architectural_impact` in state) and adapts its prompt accordingly. On the simple path, the prompt instructs the model to perform its own architectural assessment directly from the diffs. This keeps the graph topology clean — two paths converge at a single `synthesize` node — while preserving output schema consistency.

### LLM: Llama 4 Maverick via Together.ai

`meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8` was chosen for three reasons:

1. **Function calling and structured output support** — required for `with_structured_output()` to work reliably. Not all models on Together.ai expose this capability.
2. **1 million token context window** — large diffs (many files, verbose test output) fit without truncation.
3. **Cost** — at $0.27/$0.85 per million input/output tokens, it is substantially cheaper than frontier models while delivering quality sufficient for code review triage.

The model is accessed through Together.ai's OpenAI-compatible `/v1` endpoint using `langchain-openai`'s `ChatOpenAI`, which avoids a separate SDK dependency.

### `temperature=0` for deterministic reviews

Code review is a classification and extraction task, not a creative one. Setting `temperature=0` ensures that identical inputs produce identical outputs, which is important for reproducibility, debugging, and regression testing.

### Pydantic + `with_structured_output()` instead of regex parsing

Every LLM response in this system is typed: `TriageResult`, `FileAnalysisResult`, `ArchAnalysisResult`, `SynthesisResult`. Binding these schemas via `with_structured_output()` means the LLM is instructed (via tool/function-calling) to emit JSON that matches the schema, and LangChain deserializes the result directly into a Pydantic object. Field-level constraints (`ge=1.0`, `le=10.0`, `Literal["low", "medium", "high"]`) are validated at parse time. This eliminates an entire class of bugs that regex-based parsing introduces.

> **Known warning — `Pydantic serializer warnings: Expected 'none'`:** This is a spurious warning emitted by Pydantic when serializing `openai` SDK's `ParsedChatCompletionMessage` objects. The `parsed` field on that message type is typed as `Optional[T]` (a generic), which Pydantic resolves as `NoneType` at schema-build time. At runtime it holds the actual deserialized Pydantic model, causing the mismatch. The warning is harmless — the value is serialized correctly — and is suppressed in both `analyze_pr.py` (via `warnings.filterwarnings`) and `pytest.ini` (via `filterwarnings`). It originates inside `openai`/`langchain-openai` internals and cannot be fixed in application code.

### Pure Python nodes for `parse_pr` and `format_output`

These nodes perform validation and normalization, not reasoning. Adding an LLM call would introduce latency, cost, and failure modes without improving correctness. `parse_pr` validates the input schema and fails fast with a descriptive error before any LLM is invoked. `format_output` clamps numeric fields to their allowed ranges and fills in defaults — deterministic work that a function does better than a language model.

### Prompts in a separate `prompts/templates.py`

All prompt strings live in `pr_review/prompts/templates.py`, not inline in node code. This separation means prompt iteration (the most frequent change during development) does not require touching node logic, and the prompts are easy to read, diff, and hand to a `prompt-tuner` subagent for improvement without navigating implementation code.

### Security findings as internal state, not output fields

The `security_analysis` node produces structured findings (category, severity, file path, description) that are stored in internal graph state but do not appear in the final output JSON. Instead, `synthesize` reads these findings and factors them into the existing `risk_level`, `risk_reasoning`, and `confidence` fields. This preserves output schema stability — downstream consumers do not need to change — while still ensuring security vulnerabilities are reflected in the risk assessment. High or critical severity findings raise the risk level to at least "medium" and deduct from confidence.

### `operator.add` reducers for parallel-safe fan-out state

When `analyze_file` runs in parallel across N files, N concurrent writes to `file_analyses` would race if the field used the default last-write-wins reducer. Annotating with `Annotated[list[FileAnalysis], operator.add]` tells LangGraph to concatenate all returned lists, making the fan-out safe without any explicit synchronization. The same reducer on `reasoning_trace` allows every node to append its step without clobbering other nodes' entries.

---

## Setup and Installation

**Requirements:** Python 3.9+

### 1. Clone the repository

```bash
git clone <repository-url>
cd sweep.io
```

### 2. Create and activate a virtual environment

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (Command Prompt):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

You should see `(.venv)` in your prompt once the environment is active.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure your API key

```bash
cp .env.example .env        # macOS / Linux
copy .env.example .env      # Windows
```

Edit `.env` and set your Together.ai API key:

```
TOGETHER_API_KEY=your-together-api-key-here
```

Get a free API key at [together.ai](https://together.ai). The key is only used for LLM calls; no other network requests are made.

---

## Observability (Langfuse)

The pipeline integrates with [Langfuse](https://langfuse.com) for end-to-end tracing. Every LLM call is captured automatically — model name, prompt, response, token counts, latency — grouped by graph node into a single trace per run.

Tracing is **optional**. If the Langfuse keys are not set in `.env`, the pipeline runs normally with no change in behavior.

### Start the Langfuse stack

```bash
docker compose --profile monitoring up -d
```

This starts two containers: `langfuse-server` (UI + API on port 3000) and `langfuse-db` (Postgres). Data is persisted in a named Docker volume.

> **Before first use:** Open [http://localhost:3000](http://localhost:3000), create an account, then go to **Settings → API Keys** and create a new key pair.

### Configure the keys

Add the keys to your `.env` file:

```
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000
```

### View traces

Run the analysis as usual:

```bash
python analyze_pr.py --pr data/input/pr_input.json --output data/output/code_review_output.json
```

Open [http://localhost:3000/traces](http://localhost:3000/traces) to see the trace. Each run appears as a single root trace with child spans for `triage`, `analyze_file` (one per file on complex PRs), `arch_analysis`, `security_analysis`, and `synthesize`.

### Stop the stack

```bash
docker compose --profile monitoring down
```

To also remove persisted data:

```bash
docker compose --profile monitoring down -v
```

---

## Usage

```bash
# Standard run
python analyze_pr.py --pr data/input/pr_input.json --output data/output/code_review_output.json

# With verbose logging (prints structured output to stdout, detailed logs to stderr)
python analyze_pr.py --pr data/input/pr_input.json --output data/output/code_review_output.json --verbose
```

**Arguments:**

| Flag | Required | Description |
|------|----------|-------------|
| `--pr` | Yes | Path to the PR input JSON file |
| `--output` | Yes | Path to write the review output JSON file |
| `--verbose` | No | Enable DEBUG-level logging and print final output to stdout |

The CLI exits with code `0` on success and code `1` on any failure (missing input file, invalid JSON, graph execution error), with a descriptive message written to stderr.

---

## Output Format

The output file is a JSON object with the following fields:

```json
{
  "risk_level": "low | medium | high",
  "risk_reasoning": "1-3 sentence explanation of the risk classification.",
  "architectural_impact": "Concise statement of how the PR affects the codebase architecture.",
  "review_focus_areas": [
    "Specific code location or concern the human reviewer should examine.",
    "..."
  ],
  "complexity_score": 7.5,
  "confidence": 0.9,
  "reasoning_trace": [
    "Step 1: Parsed PR '...' — N file(s) changed, +X/-Y lines.",
    "Step 2: Triage classified PR as 'complex': ...",
    "Step 3 (file): Analyzed path/to/file.py — complexity Z/10, N risk indicator(s).",
    "Step 4: Architectural analysis complete — N cross-cutting concern(s) identified.",
    "Step 5: Security analysis complete — N issue(s) found, overall severity: none.",
    "Step 6: Synthesis complete — risk=medium, complexity=7.5, confidence=0.90."
  ]
}
```

**Field descriptions:**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `risk_level` | string | `"low"`, `"medium"`, or `"high"` | Overall risk classification for merging this PR |
| `risk_reasoning` | string | Non-empty | Human-readable explanation of the risk classification |
| `architectural_impact` | string | Non-empty | How the PR affects the project's architecture, abstractions, or public API surface |
| `review_focus_areas` | list of strings | 3-5 items | Specific, actionable areas a human reviewer should examine closely |
| `complexity_score` | float | 1.0 – 10.0 | Overall complexity of the PR (clamped in `format_output`) |
| `confidence` | float | 0.0 – 1.0 | Model's confidence in its assessment |
| `reasoning_trace` | list of strings | Non-empty | Ordered log of processing steps, one entry per graph node |

### Example output

```json
{
  "risk_level": "medium",
  "risk_reasoning": "The change modifies critical paths in the request handling lifecycle and introduces new state management, which could potentially break existing behavior or introduce performance issues if not properly managed. However, the rate limiting feature is opt-in via configuration, mitigating some of the risk.",
  "architectural_impact": "The PR introduces a new abstraction for rate limiting and integrates it into the Flask app object, modifying the request handling lifecycle. It adds new configuration keys and state management through the MemoryRateLimiter class, affecting the application's request processing pipeline.",
  "review_focus_areas": [
    "The thread safety of the _get_rate_limiter method and its interaction with self._rate_limiter in src/flask/app.py.",
    "The reliability and potential edge cases of the _build_rate_limit_key method, particularly behind proxies or load balancers.",
    "The performance implications of the synchronization mechanism using self._lock in MemoryRateLimiter, especially under high concurrency.",
    "The test coverage for the rate limiter's time window functionality and edge cases in tests/test_rate_limit.py.",
    "The potential memory growth issue due to the use of defaultdict and deque in MemoryRateLimiter."
  ],
  "complexity_score": 7.5,
  "confidence": 0.9,
  "reasoning_trace": [
    "Step 1: Parsed PR 'Implement in-memory rate limiting' — 3 file(s) changed, +151/-0 lines.",
    "Step 2: Triage classified PR as 'complex': This PR is classified as complex because it introduces a new feature that modifies the request lifecycle by integrating a rate limiter into the Flask app object.",
    "Step 3 (file): Analyzed src/flask/app.py — complexity 8.0/10, 3 risk indicator(s).",
    "Step 3 (file): Analyzed src/flask/rate_limiter.py — complexity 6.0/10, 4 risk indicator(s).",
    "Step 3 (file): Analyzed tests/test_rate_limit.py — complexity 6.0/10, 2 risk indicator(s).",
    "Step 4: Architectural analysis complete — 5 cross-cutting concern(s) identified.",
    "Step 5: Security analysis complete — 0 issue(s) found, overall severity: none.",
    "Step 6: Synthesis complete — risk=medium, complexity=7.5, confidence=0.90."
  ]
}
```

---

## Running Tests

Make sure your virtual environment is active, then:

```bash
python -m pytest tests/ -v
```

The test suite includes an integration test that runs the full graph against a fixture PR input and validates that the output schema is correct.

---

## AI-Assisted Development

This project was built with Claude Code as an active development partner, not just a code generator. The workflow used several specialized subagents, each with a narrow responsibility:

### Subagents

- **reviewer** — Acts as a principal developer before every commit. Reviews staged changes against `CLAUDE.md` (code style, architecture, quality standards), the assignment requirements (LangGraph usage, output format, CLI interface, what not to build), and test data format compliance. Blocks commits until all standards are met.
- **documentator** — Generates and updates this README, covering usage, architecture, design decisions, and trade-offs.
- **prompt-tuner** — Reviews and improves LLM prompt templates in `pr_review/prompts/templates.py`, analyzing clarity, specificity, and potential failure modes.
- **test-runner** — Runs the test suite and full analysis pipeline and reports results.

### Custom Skills

Two reusable slash commands were defined in `.claude/skills/`:

- `/run-analysis` — Runs `python analyze_pr.py --pr data/input/pr_input.json --output data/output/code_review_output.json` and displays the output. Used to quickly verify the pipeline end-to-end during development.
- `/validate-output` — Reads `data/output/code_review_output.json` and validates every field against the expected schema (correct types, value ranges, non-empty required fields). Surfaces violations immediately.

### What this demonstrates

This is not a one-shot "write me a LangGraph app" prompt. The workflow iterated: build a node, have the reviewer check it against the spec, tune the prompt with the prompt-tuner, run the analysis with `/run-analysis`, validate the output with `/validate-output`, then commit. Each subagent enforces a specific quality gate. The result is code that is consistent with its own specification throughout — not because a single long prompt tried to hold all constraints at once, but because different agents were responsible for different concerns at different stages.

---

## Trade-offs

### No `create_react_agent`

ReAct (Reason + Act) is appropriate when an agent needs to decide which tools to call at runtime based on intermediate observations. This system has no tools to call — each node's inputs and outputs are fully determined by the graph topology. Using `create_react_agent` here would be cargo-culting: it would add prompt overhead, unpredictable routing, and a harder-to-audit execution trace without providing any benefit.

### No human-in-the-loop

LangGraph supports interrupt-and-resume patterns that allow a human to review or edit state mid-execution. This is a CLI tool with no UI, and the use case (async PR triage) does not require synchronous human approval during graph execution. Adding checkpointing infrastructure for a tool that runs to completion in under a minute would be over-engineering.

### No checkpointing or persistence

LangGraph's checkpointing requires a database backend (SQLite, Postgres, etc.). The assignment explicitly excludes a persistence layer, and the tool's stateless, single-run nature makes checkpointing unnecessary. The `reasoning_trace` field in the output provides sufficient audit trail without a database.

### Simple path: speed vs. depth

The simple path skips per-file analysis and architectural review, relying on `synthesize` to perform a one-shot assessment from raw diffs. This is faster and cheaper but produces a shallower review than the complex path. For genuinely simple PRs (documentation fixes, single-line corrections) this is the right trade-off. The triage node's conservative fallback to `complex` on uncertainty limits the cases where depth is sacrificed incorrectly.
