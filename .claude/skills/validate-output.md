---
name: validate-output
description: Validate that a PR analysis output JSON file matches the expected schema. Use after running the analysis pipeline or when checking output correctness.
argument-hint: "[file-path]"
allowed-tools: Read, Glob
---

## Task

Validate the PR analysis output file at `$ARGUMENTS` against the expected schema. If no file path is provided, default to `data/output/code_review_output.json`.

## Steps

1. **Read the file** — if the file does not exist or is not valid JSON, report the error immediately and stop.
2. **Check every field** against the schema below.
3. **Report results** — list each violation found. If all checks pass, confirm the output is valid.

## Expected Schema

| Field | Type | Constraint |
|---|---|---|
| `risk_level` | string | One of: `"low"`, `"medium"`, `"high"` |
| `risk_reasoning` | string | Non-empty |
| `architectural_impact` | string | Non-empty |
| `review_focus_areas` | list[string] | Non-empty list; each element non-empty |
| `complexity_score` | number | Between 1.0 and 10.0 inclusive |
| `confidence` | number | Between 0.0 and 1.0 inclusive |
| `reasoning_trace` | list[string] | Non-empty list; each element starts with `"Step N:"` where N is sequential |

## Validation Rules

- **Missing fields**: flag any field from the schema that is absent in the output.
- **Extra fields**: note any unexpected top-level keys (informational, not a failure).
- **Type mismatches**: flag when a value does not match the expected type.
- **Range violations**: flag numeric values outside their allowed bounds.
- **Format violations**: flag `reasoning_trace` entries that do not match the `"Step N:"` pattern.
- **Empty values**: flag empty strings or empty lists where non-empty is required.

## Output Format

```
Validation: VALID | INVALID
File: <path validated>
Violations: <count>

[If INVALID, list each violation as:]
- <field>: <description of violation>
```

## Constraints

- Do NOT modify the output file — only read and report.
- Do NOT re-run the pipeline — only validate the existing file.
