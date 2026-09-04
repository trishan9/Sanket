# tests

- `test_engineering_standards.py` — no comments anywhere, type hints on every signature,
  files under 400 lines, functions under 40. These caught three of the authors own
  violations during Phase 0.
- `test_provider_isolation.py` — only `agent/router.py` may import a provider SDK, each
  lane has exactly one deployment, and the planner and the critic are different model
  families.
