# 4-stage Bug Fix — Stage 3/4: Patch

## Task

Using stage-2's `{slug}.root_cause.md`, apply the **minimal fix** to make the stage-1 repro test pass.

## Bug Description

{bug_description}

## Repo

{repo_path}

## Language

{language}

## Strict Constraints

1. **Change scope**: ±20 lines around the fault point identified in root_cause.md — no "while I'm here" cleanups.
2. **Do not touch the repro test** — it is the judge; only fix src/.
3. **No new dependencies** (no pip install / cargo add).
4. **Do not alter security boundaries, RLS policies, or generated files**.

## Workflow

1. Read stage-2 `{slug}.root_cause.md`.
2. Apply the recommended fix (minimal change).
3. Run the stage-1 repro command — must **PASS**.
4. Run adjacent tests (same module / file) — no regressions allowed.
5. Write `{slug}.patch.md` recording what changed and why.

## Output Contract (`{slug}.patch.md`)

```markdown
# Patch: {slug}

## Changed Files
- path/to/core.py:156-158 (primary fix)
- path/to/types.py:42 (associated type update, if any)

## Change Description
[one sentence] — added check X at line Y to ensure condition Z.

## Verification
- Repro test: pytest tests/repro_{slug}.py → PASS
- Adjacent tests: pytest path/to/test_core.py → PASS
- Gate: (deferred to verify stage)

## Known Gaps
- [related scenario A: fixed / needs separate task]
```

## Do NOT

- Modify stage-1 repro tests
- Change `{slug}.root_cause.md` (if root cause was wrong, re-run stage 2)
- Refactor beyond the fault point ±20 lines
- Fix other bugs discovered during investigation — open a separate task
