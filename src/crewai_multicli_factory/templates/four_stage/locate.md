# 4-stage Bug Fix — Stage 2/4: Locate

## Task

Using the stage-1 output (`{slug}.repro.md`), **locate the root cause**.
**Do NOT modify any code** — output only `{slug}.root_cause.md`.

## Bug Description

{bug_description}

## Repo

{repo_path}

## Language

{language}

## Workflow

1. Read stage-1 repro script + failure output.
2. Use grep / Read / search to find the failure point (file:line).
3. Read the relevant functions and their call chains.
4. Form at least one root-cause hypothesis.
5. Support or eliminate each hypothesis with evidence (log / test output / code).
6. Lock the highest-confidence root cause.

## Hard Rules

1. **Read-only** (the only output file allowed is `{slug}.root_cause.md`).
2. Every conclusion must cite a file:line — no guesswork.
3. If the root cause is architectural (cross-module / security boundary / race condition), STOP and escalate.
4. If it's a trivial single-file change, proceed directly to patch stage.

## Output Contract (`{slug}.root_cause.md`)

```markdown
# Root Cause: {slug}

## Trigger Conditions
[repro command + key input]

## Failure Path
1. Entry: path/to/handler.py:42
2. Call:  path/to/lib.py:88
3. Fault: path/to/core.py:156  ← logic error here

## Root Cause
[one sentence] — because `path/to/core.py:156` does not X under condition Y, causing Z.

## Evidence
- file:line + quote
- test output + error message

## Fix Direction (no code yet)
- Option A: ...
- Option B: ...
- Recommended: [A/B], reason

## Risk Surface
- Affected callers: [list]
- Test coverage gaps: [list]

## Architectural Escalation Required
- Yes / No
```

## Do NOT

- Modify any source files
- Run the full test suite
- Invent causes without file:line evidence
