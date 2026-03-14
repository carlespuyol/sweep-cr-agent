# Scope Rules — What NOT to Build

These are hard boundaries for this project:

- No UI or web interface (no Flask/FastAPI/Streamlit/etc.)
- No real GitHub API integration (input is always a local JSON file)
- No database or persistence layer (no SQLite, Redis, vector DBs, etc.)
- No authentication or authorization system
- No deployment configuration (no Dockerfile, docker-compose, CI/CD)
- No extensive test suite — one integration test in `tests/test_graph.py` is the limit

When in doubt: keep it as a CLI tool that reads a JSON file and writes a JSON file.
