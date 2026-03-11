# Intelligent PR Review Assistant

> Home assignment for [Applied ML Engineer](https://jobs.ashbyhq.com/sweep/18f9dc28-9593-41cd-9ed1-ca12a36e0c98) position

## **Background & Context**

You are core-team member of [Flask - popular Python web framework](https://github.com/pallets/flask).
As an open source project, Flask has a large community of contributors.

Every week, there are multiple pull requests submitted to the project.

However, the project has a small team of maintainers who are responsible for reviewing the pull requests.

This is a bottleneck for the project, as the maintainers are not able to review all the pull requests in a timely manner.

To help the maintainers, we want to build an AI agent that can review the pull requests and provide a summary of the changes.

The agent should be able to:

* Understand the changes in the pull request
* Identify potential architectural implications
* Identify risk areas
* Provide a confidence score for the assessment

## **Your Task**

Build a single/multi-agent system (of your choice) using **LangGraph** that analyzes a pull request and produces an intelligent review summary. The system should help reviewers quickly understand:

* What changed and why it matters  
* Potential architectural implications  
* Risk areas to focus on  
* Confidence in the assessment

If you decide to use any additional frameworks, platforms, e.g. Vector DBs, etc., please elaborate and justify your choice.

**Input Format**

Your system should accept a JSON file representing a PR [based on a real PR from Flask](https://github.com/pallets/flask/pull/5853/changes):

```json
{
  "pr_title": "Implement in-memory rate limiting",
  "pr_description": "This PR implements a simple in-memory rate limiter for Flask applications. It introduces a `MemoryRateLimiter` class and integrates it into the Flask app object. The rate limiter is configurable via `RATELIMIT_ENABLED`, `RATELIMIT_REQUESTS`, and `RATELIMIT_WINDOW` configuration keys. It also includes unit tests for the new functionality.",
  "author": "txjas999",
  "changed_files": [
    {
      "path": "src/flask/app.py",
      "status": "modified",
      "lines_added": 62,
      "lines_removed": 0,
      "diff": "@@ -19,6 +19,7 @@ from werkzeug.datas      rv = self.preprocess_request(ctx)\n      if rv is None:"
    },
    {
      "path": "src/flask/rate_limiter.py",
      "status": "added",
      "lines_added": 53,
      "lines_removed": 0,
      "diff": "@@ -0,0 +1,53 @@\n+from __future__ import annotations\n+\n+ defaultdict\n+from ..."
    },
```

### **Output Format**

Your system should produce structured JSON output:

```json
{
  "risk_level": "low",
  "risk_reasoning": "Introduces a new optional feature. Modifies the core request dispatch path in app.py but safeguards it with configuration checks.",
  "architectural_impact": "Adds a native in-memory rate limiting capability to the Flask application object, introducing state management for request tracking.",
  "review_focus_areas": [
    "Thread safety in src/flask/rate_limiter.py (Lock usage)",
    "Performance overhead in src/flask/app.py _enforce_rate_limit",
    "Logic for key generation in _build_rate_limit_key"
  ],
  "complexity_score": 3.5,
  "confidence": 0.9,
  "reasoning_trace": [
    "Step 1: Parsed diff showing addition of rate limiting module and app integration.",
    "Step 2: Validated thread safety implementation in MemoryRateLimiter.",
    "Step 3: Verified opt-in configuration mechanism in Flask app."
  ]
}
```

### **Command-Line Interface**

Your system should be runnable from the command line:

```bash
python analyze_pr.py --pr pr_input.json --output code_review_output.json
```

## **Technical Requirements**

### **Must Use**

* **LangGraph** for workflow orchestration  
* **LangChain** for agent building  
* **Claude API** or **OpenAI API** for LLM calls  
* **Python 3.9+**

### **Encouraged Tools**

* **AI Coding Assistants**: Cursor, Claude, GitHub Copilot, etc.  
* Use them actively \- we want to see how you work with AI tools  
* Document what you used and how in your README

### **What You Should NOT Build**

* ❌ No UI or web interface  
* ❌ No real GitHub API integration  
* ❌ No database or persistence layer  
* ❌ No authentication system  
* ❌ No deployment configuration  
* ❌ No extensive test suite (one simple test is fine)


## **Deliverables**

### **1\. Working Code**

* Complete, runnable LangGraph system  
* Can be executed via command line  
* Successfully analyzes the provided mock PR

### **2\. Example Output**

* Run your system on the mock PR we provide  
* Include the `output.json` file showing results

### **3\. requirements.txt**

* All Python dependencies with versions


## **What We're Assessing**

This assignment is designed to evaluate three key areas:

### 1\. Learning Agility \- Understanding New Material

**What we're looking for:**

* How quickly you can understand and apply LangGraph/LangChain concepts (which may be new to you)  
* Depth of understanding vs. surface-level usage  
* Your approach to learning: Do you cargo-cult examples or truly grasp the patterns?

**We understand you may not have prior LangGraph experience** \- that's intentional. We want to see how you tackle unfamiliar frameworks.

### 2\. AI-Assisted Coding Skills

**What we're looking for:**

* Effective use of AI coding tools (Cursor, Claude, Copilot, etc.)  
* Your ability to guide AI assistants to produce quality code  
* Judgment in when to use AI vs. when to think deeply yourself  
* How you validate and refine AI-generated code

**Feel free to use AI assistants liberally** \- in fact, we expect you to. This reflects how we actually work.

### 3\. System Design Abilities

**What we're looking for:**

* How you decompose complex problems into manageable components  
* Agent architecture decisions and reasoning behind them  
* Trade-offs you consider (accuracy vs. speed, simplicity vs. features)  
* Your intuition about what matters in production systems

**We care more about your design thinking than perfect implementation.**

### What "Good" Looks Like

**System Design:**

* Agents have clear, focused responsibilities  
* Thoughtful state management between agents  
* Evidence of considering alternatives  
* Understanding of when to use agents vs. simpler approaches

**Learning Depth:**

* Proper use of LangGraph patterns (not just minimal example copy)  
* Understanding why LangGraph exists and what problems it solves  
* Code demonstrates grasp of concepts, not just syntax

**Implementation Quality:**

* System runs successfully on provided input  
* Good use of AI tools (where appropriate)  
* Human oversight evident in final code  
* Reasonable error handling

**Communication:**

* Clear explanation of design choices  
* Honest about what's new vs. what you knew  
* Articulates trade-offs made

## **Submission Instructions**

Please submit:

1. A zip file or GitHub repository link containing all code  
2. Ensure the mock PR analysis is already run and `code_review_output.json` is included  
3. Clear instructions in README for how to run your code

**Submission deadline:** Specified in the email


## **Questions?**

If you have clarifying questions about the assignment, please reach out to sergeyb@sweep.io.

We're excited to see your approach to building intelligent agentic systems\!

---

**Good luck\!** 🚀

