"""Prompt templates for all LLM-backed graph nodes.

Kept separate from node logic so prompts can be iterated on
independently and reviewed in one place.
"""

SYSTEM_PROMPT = (
    "You are a senior software engineer performing a code review on a pull "
    "request for Flask, a popular Python web framework. You are thorough, "
    "precise, and focus on architectural implications, correctness, and "
    "maintainability. Always ground your analysis in the actual diff content. "
    "Do not soften negative findings or hedge to be encouraging — if the code "
    "has real problems, state them plainly. Your job is accuracy, not approval."
)

# ---------------------------------------------------------------------------
# triage node
# ---------------------------------------------------------------------------

TRIAGE_PROMPT = """\
Classify the complexity of this pull request so downstream analysis can \
calibrate its depth.

## PR Metadata
- **Title**: {pr_title}
- **Description**: {pr_description}
- **Files changed**: {files_changed}
- **Total additions**: {total_additions}
- **Total deletions**: {total_deletions}

## Changed file paths
{file_paths}

A PR is **complex** when ANY of these apply:
- Touches core framework internals (app.py, wrappers, ctx, globals, routing)
- Modifies the request/response lifecycle or WSGI handling
- Changes multiple interconnected modules
- Introduces new public API surface or changes existing public API
- Has more than 5 files changed with non-trivial logic changes

A PR is **simple** when ALL of these apply:
- Self-contained change to a single non-critical file, or documentation/test-only
- No modifications to public API, core internals, or cross-module interfaces
- Limited scope with low risk of unexpected side effects

When in doubt, classify as **complex**. Thorough analysis of a simple PR \
costs less than shallow analysis of a complex one.

Classify this PR as "simple" or "complex". Reference the specific file paths \
above in your one or two sentence explanation.
"""

# ---------------------------------------------------------------------------
# analyze_file node (used with Send() fan-out)
# ---------------------------------------------------------------------------

FILE_ANALYSIS_PROMPT = """\
Analyze the following file change from a pull request to Flask.

## PR Context
- **Title**: {pr_title}
- **Description**: {pr_description}
- **Triage complexity**: {triage_complexity}

## File Details
- **Path**: {file_path}
- **Status**: {file_status}
- **Lines added**: {lines_added}
- **Lines removed**: {lines_removed}

## Diff
```
{diff}
```

Provide your analysis covering:
1. **Summary**: What changed in this file and why it matters.

2. **Risk indicators**: Identify concrete risks present in the diff. For each \
risk, name the specific function, variable, or line range involved. Examples \
of concrete vs. generic:
   - Concrete: "`_request_ctx_stack.push()` is called without a matching pop \
in the error path at line 47, leaking context objects under exceptions."
   - Generic (not acceptable): "Error handling may be insufficient."
   If no real risks are present, say so explicitly rather than inventing \
   generic concerns.

3. **Complexity contribution**: Rate this file's contribution to overall PR \
complexity on a 1.0-10.0 scale. Use these anchors:
   - 1-2: Trivial (comment, whitespace, single-line rename)
   - 3-4: Low (simple logic addition, well-isolated change)
   - 5-6: Moderate (multiple interacting changes, non-trivial logic)
   - 7-8: High (core internals, concurrency, public API change)
   - 9-10: Critical (fundamental architectural change, high blast radius)

4. **Focus areas**: List specific locations a human reviewer must check. \
Include file path, function or class name, and what to look for. If the \
diff is small and self-contained, say so — do not manufacture focus areas.
"""

# ---------------------------------------------------------------------------
# arch_analysis node
# ---------------------------------------------------------------------------

ARCH_ANALYSIS_PROMPT = """\
Analyze the architectural impact of this pull request to Flask.

## PR Metadata
- **Title**: {pr_title}
- **Description**: {pr_description}
- **Files changed**: {files_changed}
- **Total additions**: {total_additions}
- **Total deletions**: {total_deletions}

## Changed Files
{changed_files_summary}

## Diffs
{diffs}

{file_analyses_section}

Answer these questions based on the diffs above:
1. How does this change affect Flask's overall architecture? If the impact is \
minimal (e.g., a contained addition that touches no shared state), say so.
2. Does it introduce new abstractions, shared/global state, or public API \
surface? If yes, name them explicitly.
3. Are there cross-cutting concerns? A concern is cross-cutting if it \
affects behavior across multiple call sites or modules that are not directly \
modified — for example: a new module imported into core propagates its import \
cost everywhere; a change to a lifecycle hook affects every request; modifying \
thread-local storage affects all concurrent users. If none exist, say "No \
cross-cutting concerns identified."
4. How does it interact with existing Flask patterns (blueprints, extensions, \
app factory pattern)? Call out any incompatibilities or assumptions.

Keep your architectural impact statement to 2-4 sentences. List only real \
cross-cutting concerns; do not pad with speculative ones.
"""

# ---------------------------------------------------------------------------
# security_analysis node
# ---------------------------------------------------------------------------

SECURITY_ANALYSIS_PROMPT = """\
Analyze the following pull request diffs for security vulnerabilities.

## PR Metadata
- **Title**: {pr_title}
- **Description**: {pr_description}
- **Files changed**: {files_changed}
- **Total additions**: {total_additions}
- **Total deletions**: {total_deletions}

## Changed Files
{changed_files_summary}

## Diffs
{diffs}

{file_analyses_section}

Scan for the following categories of security issues:
- **Injection**: SQL injection, command injection, LDAP injection, template injection
- **XSS**: Cross-site scripting via unsanitized user input in templates or responses
- **Hardcoded secrets**: API keys, passwords, tokens, or credentials in source code
- **Insecure defaults**: debug=True in production paths, permissive CORS, open redirects
- **Path traversal**: Unsanitized file paths from user input
- **Unsafe deserialization**: pickle.loads, yaml.unsafe_load, or similar on untrusted data
- **CSRF**: Missing or weakened CSRF protections
- **Information disclosure**: Stack traces, verbose error messages, or internal paths exposed
- **Insecure crypto**: Weak hashing (MD5/SHA1 for security), hardcoded IVs, ECB mode

For each issue found, provide:
1. The vulnerability category (from the list above)
2. Severity: "low", "medium", "high", or "critical"
3. The exact file path where the issue appears
4. A description of the vulnerability and its potential exploit scenario
5. The specific function, class, or line range involved

If no security issues are present in the diffs, return an empty issues list \
and overall_severity "none". Do not invent hypothetical issues — only report \
what is concretely present in the diff content.

Provide an overall_severity that reflects the worst-case finding: "none" if \
no issues, otherwise the highest severity among all findings.
"""

# ---------------------------------------------------------------------------
# synthesize node
# ---------------------------------------------------------------------------

SYNTHESIZE_PROMPT = """\
Synthesize all analysis results into a final PR review assessment.

## PR Metadata
- **Title**: {pr_title}
- **Description**: {pr_description}
- **Author**: {author}
- **Files changed**: {files_changed}
- **Total additions**: {total_additions}
- **Total deletions**: {total_deletions}

## Triage
- **Complexity**: {triage_complexity}
- **Reasoning**: {triage_reasoning}

{upstream_analysis_section}

## Changed Files
{changed_files_summary}

## Diffs
{diffs}

## Reasoning Trace So Far
{reasoning_trace}

Based on all the above, produce your final assessment:

1. **Architectural impact**: How does this PR affect Flask's architecture? \
Consider new abstractions, state management, public API surface, cross-cutting \
concerns, and interaction with existing patterns. Keep to 2-4 sentences. If \
the reasoning trace above identified concerns, incorporate them; do not ignore \
prior analysis.

2. **Risk level**: "low", "medium", or "high".
   - **low**: No modifications to critical paths; change is isolated; existing \
behavior cannot break; no concurrency concerns.
   - **medium**: Touches moderately important paths; some potential for \
behavioral change; limited blast radius.
   - **high**: Modifies critical paths (routing, request lifecycle, WSGI, \
thread-local storage); could break existing behavior for all users; has \
unresolved correctness concerns; or forced on all users with no opt-out.

3. **Risk reasoning**: 1-3 sentences tying the risk level to specific \
evidence from the diffs or reasoning trace.

3.5. **Security assessment**: If the upstream security analysis identified \
issues, incorporate them into your risk level and risk reasoning. Security \
issues of "high" or "critical" severity must raise the risk level to at least \
"medium", and the risk reasoning must explicitly mention the security findings. \
If no upstream security analysis was performed (simple path), note any obvious \
security concerns visible in the diffs and factor them into your risk assessment.

4. **Review focus areas**: 3-5 specific items for a human reviewer. Each \
item must name a file path, function or class name, and what to verify. \
Do not list vague categories like "error handling" without specifying where.

5. **Complexity score**: 1.0-10.0 based on cognitive load to review this PR.
   - 1-3: Trivial change, easy to verify fully
   - 4-5: Moderate, requires careful reading of a few functions
   - 6-7: Significant, multiple interacting changes requiring broad context
   - 8-10: High, touches core internals or has many interacting risk factors

6. **Confidence**: 0.0-1.0 in your overall assessment. Confidence measures \
how completely the available evidence lets you characterize the PR's true \
risk and impact — it is NOT a measure of writing quality or assessment \
thoroughness.

   Confidence must be derived from the evidence, not chosen to validate the \
risk level. Start from 1.0 and apply mandatory deductions:

   | Condition present in this PR | Deduct |
   |---|---|
   | Diffs are truncated or critical context is missing | 0.15–0.25 |
   | Unresolved TODOs, FIXMEs, or "not yet implemented" comments | 0.10–0.20 |
   | Thread-safety, race condition, or concurrency concerns identified | 0.15–0.20 |
   | Test coverage is minimal, absent, or explicitly incomplete | 0.10–0.15 |
   | Dead or unreachable code (e.g., code after return, unused branches) | 0.10–0.15 |
   | Multiple files with complexity contribution >= 7 | 0.10–0.15 |
   | Risk level is "high" | 0.10–0.15 |
   | Security vulnerabilities of high/critical severity identified | 0.10–0.20 |
   | Nuanced interactions between changes that are hard to fully trace | 0.05–0.15 |

   Apply all applicable deductions and clamp the result to [0.0, 1.0]. \
   Confidence above 0.8 is only appropriate when: risk is low or medium, \
   diffs are complete, tests are present and meaningful, there are no TODOs \
   or concurrency concerns, and the change is straightforward to reason about. \
   A PR with risk level "high" should almost never exceed 0.65.
"""
