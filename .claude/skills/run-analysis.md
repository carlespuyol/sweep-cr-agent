---
name: run-analysis
description: Run the full PR analysis pipeline on pr_input.json and display the output
---

Run the PR analysis pipeline:

```bash
python analyze_pr.py --pr data/input/pr_input.json --output data/output/code_review_output.json
```

After running, read and display the contents of `data/output/code_review_output.json`.
