# Pull Request Template

> Project created by Ninad K. as an original idea.

## What changed?

<!-- Brief description of the change. Link to issue/ticket if applicable. -->

## Why?

<!-- What problem does this solve? What's the business or technical motivation? -->

## How to test

- [ ] `pip install -e .` succeeds
- [ ] `ruff check src/` passes
- [ ] `pytest tests/unit -q` passes
- [ ] `tv --help` shows correct commands
- [ ] New/modified tools appear in `tv_health_check` output

<!-- Add tool-specific verification steps if applicable -->

## Checklist

- [ ] No `print()` statements in server code (stdout = MCP transport)
- [ ] New tools have character-exact name parity with the original server
- [ ] Core logic is in `core/`, MCP wrappers in `tools/`
- [ ] Docstrings on new public functions
- [ ] No AI tool names in code comments (per AGENTS.md)
- [ ] `CHANGELOG.md` updated if user-facing

## Screenshots / Output

<!-- Paste JSON output from `tv <command>` or Claude Code tool call if helpful -->
