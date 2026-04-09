# CI/CD Pipeline Notes

| Field | Value |
|---|---|
| **Author** | Ninad K. |
| **Created** | 2026-04-09 |

> This project was Ninad K.'s own original idea.

## Overview

tradingview-mcp-ninad is a local-only tool — it is not deployed to any cloud environment. CI/CD is focused on code quality gates, not deployment.

## Proposed Pipeline Stages

```
Push to branch
    │
    ├── Lint (ruff check src/)
    ├── Type check (mypy src/tradingview_mcp_ninad --ignore-missing-imports)
    ├── Unit tests (pytest tests/unit -q)
    │
    └── (Manual) Integration test against headless Chrome
```

## GitHub Actions Workflow (Proposed)

```yaml
name: CI
on: [push, pull_request]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: tools/tradingview-mcp-ninad
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - run: ruff check src/
      - run: pytest tests/unit -q
```

## Quality Gates

| Gate | Tool | Threshold |
|---|---|---|
| Lint | ruff | Zero errors |
| Type safety | mypy (future) | Zero errors on strict mode |
| Unit tests | pytest | 100% pass |
| Import check | `python -c "from tradingview_mcp_ninad.server import build_server"` | Must succeed |
| Tool count | Script that asserts `len(tools) == 78` | Must match |

## No Production Deployment

This tool runs locally inside Claude Code. There is no:
- Docker image to build
- Cloud service to deploy
- Database to migrate
- Load balancer to configure

The "deployment" is `pip install -e .` and adding the server to `~/.claude/.mcp.json`.

---

*Authored by Ninad K.*
