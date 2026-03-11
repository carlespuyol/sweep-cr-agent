# Test Data for PR Analysis Assignment

## Files Provided

### 1. `pr_input.json` [based on a real PR from Flask](https://github.com/pallets/flask/pull/5853/changes)
The pull request you need to analyze. This contains:
- PR metadata (title, description, author)
- All changed files with their diffs in unified diff format
- Line count statistics

**This is your primary input file.** Your system should read and analyze this.

### 2. Flask repository 
Contains the "before" state of modified files for context:
https://github.com/pallets/flask

**Use this for context** to understand what changed and why.

## How to Use This Data

### In Your Code
Your system should accept `pr_input.json` as input:

```bash
python analyze_pr.py --pr pr_input.json --output code_review_output.json
```

### Understanding the PR
Before coding, **read through the PR yourself** to understand:
- What is the developer trying to achieve?
- What files changed and how?
- What are the architectural implications?

This will help you design your agents effectively.

## Expected Output

Your system should produce a `code_review_output.json` file with analysis like:

```json
{
  "risk_level": "medium",
  "risk_reasoning": "...",
  "architectural_impact": "...",
  "review_focus_areas": [...],
  "complexity_score": 6.5,
  "confidence": 0.75,
  "reasoning_trace": [...]
}
```

## Tips

1. **Start simple**: Make sure you can parse the JSON and extract basic info first
2. **Test iteratively**: Run your agents on this PR frequently as you build
3. **Read the diffs**: The unified diff format is standard - your agents should understand it
4. **Think like a reviewer**: What would you focus on if you were reviewing this PR?

## Questions?

If anything is unclear about the test data format, please reach out.

Good luck! 🚀
