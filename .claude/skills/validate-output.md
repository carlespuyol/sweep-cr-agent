---
name: validate-output
description: Validate that code_review_output.json matches the expected schema
---

Read `data/output/code_review_output.json` and validate:

1. `risk_level` is one of: "low", "medium", "high"
2. `risk_reasoning` is a non-empty string
3. `architectural_impact` is a non-empty string
4. `review_focus_areas` is a non-empty list of strings
5. `complexity_score` is a number between 1.0 and 10.0
6. `confidence` is a number between 0.0 and 1.0
7. `reasoning_trace` is a non-empty list of strings starting with "Step N:"

Report any violations found.
