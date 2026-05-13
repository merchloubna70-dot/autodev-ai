# 4-stage Bug Fix — Stage 4/4: Verify (Local Gate)

## Task

Run the project's local dev-CI gate to prove the patch introduces no regressions.

## Bug Description

{bug_description}

## Repo

{repo_path}

## Language

{language}

## Workflow

1. Read stage-3 `{slug}.patch.md` — confirm which files were changed.
2. Run the fast gate:
   ```bash
   # Python
   pytest {repo_path} -x -q

   # Rust
   cargo test --workspace
   ```
3. If fast gate passes, run the full gate (project-specific).
4. Parse and record the gate result.
5. Write `{slug}.verify.md` with the full gate report.

## Hard Rules

1. **Gate FAIL = task FAIL** — "core functionality OK" is not acceptable.
2. **Do not skip or weaken gate checks** to make the task pass.
3. **Gate FAIL triggers rollback**: mark task FAIL, attach full failure log, re-dispatch stage 2 (locate) or stage 3 (patch).
4. **Do not force-push**: local gate is the last safety line.

## Output Contract (`{slug}.verify.md`)

```markdown
# Verify: {slug}

## Gate Result
- Mode: fast / full
- Result: PASS / FAIL
- SHA: <git short>
- Duration: Xs

## Stage Detail
| Stage | Name  | Result | Duration |
|-------|-------|--------|----------|
| 1     | TESTS | PASS   | 12s      |

## Failure Analysis (if FAIL)
- Failed stage: [id]
- Key logs (50 lines): [...]
- Probable cause: [one sentence]
- Next step: re-run stage 2 / stage 3 / escalate

## Checklist
- [ ] Gate PASS
- [ ] Repro test still PASS
- [ ] Ready to commit + push
```

## Critical Reminders

- Do not weaken acceptance criteria checks to make a test pass — fix the code.
- Gate report is audit evidence — do not delete.
- If the patch touches security/auth/RLS paths, escalate before committing.
