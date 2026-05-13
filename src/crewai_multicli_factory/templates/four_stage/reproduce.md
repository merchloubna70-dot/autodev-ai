# 4-stage Bug Fix — Stage 1/4: Reproduce

## Task

Write a **minimal reproduction script** for the bug below.
**Do NOT modify any existing source code** — only add:
- `tests/repro_{slug}.py` (Python project)
- `tests/repro_{slug}.rs` (Rust project)
- Optionally `docs/repro/{slug}.md` to describe the scenario.

## Bug Description

{bug_description}

## Repo

{repo_path}

## Language

{language}

## Hard Rules

1. **Only add new test files; do not change any existing code** (src/, lib/, handlers/ are off-limits).
2. The reproduction script must **FAIL** on the current commit — proving the bug exists.
3. Test name must be `test_repro_{slug}` with a comment referencing the original issue.
4. Run the test and confirm it **FAILS** (this is expected — it proves the bug).
5. Write the reproduction command + failure output to `{slug}.repro.md` for the next stage (locate).

## Output Contract

```
REPRO_FILE: tests/repro_{slug}.py
REPRO_CMD:  pytest tests/repro_{slug}.py -v
REPRO_RESULT: FAIL (expected — proves bug exists)
REPRO_OUTPUT: <key failure lines>
```

## Do NOT

- Modify any src/ files "while you're at it"
- Run the full test suite (only run the new repro case)
- Make architectural decisions (not needed at this stage)
