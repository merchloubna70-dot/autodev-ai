# Round 7 — CLI Surface Contract Validation Report

**Agent**: 3 — cli_surface_contract
**Project**: autodev-ai v0.1.0a3
**Date**: 2026-05-14
**Overall Result**: PASS

---

## Environment

| Item | Value |
|------|-------|
| Binary | `/opt/homebrew/bin/autodev` |
| Version | `autodev-ai 0.1.0a3` |
| Python | `/opt/homebrew/bin/python3.11` |
| Install type | Homebrew system install |
| `--version` exit code | 0 |
| `--help` exit code | 0 |

---

## Summary

| Category | Count |
|----------|-------|
| pass | **35** |
| help_missing | 0 |
| import_crash | 0 |
| missing_command | 0 |
| other_failure | 0 |
| **TOTAL** | **35** |

**Spec vs discovered**: 35 spec commands — 35 discovered — 0 missing from spec — 0 extra vs spec. ✓ Perfect match.

---

## Severity Counts

| Severity | Count |
|----------|-------|
| P0 | 0 |
| P1 | 0 |
| P2 | 1 |
| P3 | 0 |
| P4 | 0 |

---

## Command Results Table

| # | Command | Exit | Result | Has Usage/Options | Traceback | Duration (ms) |
|---|---------|------|--------|-------------------|-----------|---------------|
| 1 | classify-input | 0 | pass | YES | NO | ~593 |
| 2 | create-prd | 0 | pass | YES | NO | ~490 |
| 3 | plan-project | 0 | pass | YES | NO | ~495 |
| 4 | plan-milestones | 0 | pass | YES | NO | ~492 |
| 5 | plan-tasks | 0 | pass | YES | NO | ~494 |
| 6 | execute-milestone | 0 | pass | YES | NO | ~495 |
| 7 | run-issue | 0 | pass | YES | NO | ~493 |
| 8 | deliver-project | 0 | pass | YES | NO | ~491 |
| 9 | continue-run | 0 | pass | YES | NO | ~490 |
| 10 | replay | 0 | pass | YES | NO | ~488 |
| 11 | scan | 0 | pass | YES | NO | ~492 |
| 12 | verify | 0 | pass | YES | NO | ~492 |
| 13 | release-check | 0 | pass | YES | NO | ~491 |
| 14 | report | 0 | pass | YES | NO | ~488 |
| 15 | export-delivery | 0 | pass | YES | NO | ~491 |
| 16 | push | 0 | pass | YES | NO | ~492 |
| 17 | create-pr | 0 | pass | YES | NO | ~490 |
| 18 | fix-bug | 0 | pass | YES | NO | ~493 |
| 19 | multi-patch-fix-bug | 0 | pass | YES | NO | ~488 |
| 20 | review | 0 | pass | YES | NO | ~490 |
| 21 | investigate | 0 | pass | YES | NO | ~492 |
| 22 | roundtable | 0 | pass | YES | NO | ~514 |
| 23 | mcp-serve | 0 | pass | YES | NO | ~468 |
| 24 | a2a-serve | 0 | pass | YES | NO | ~470 |
| 25 | a2a-register | 0 | pass | YES | NO | ~471 |
| 26 | a2a-call | 0 | pass | YES | NO | ~469 |
| 27 | sprint-start | 0 | pass | YES | NO | ~472 |
| 28 | sprint-status | 0 | pass | YES | NO | ~471 |
| 29 | sprint-retro | 0 | pass | YES | NO | ~472 |
| 30 | sprint-correct | 0 | pass | YES | NO | ~470 |
| 31 | design-ux | 0 | pass | YES | NO | ~471 |
| 32 | next | 0 | pass | YES | NO | ~469 |
| 33 | generate-context | 0 | pass | YES | NO | ~470 |
| 34 | document-project | 0 | pass | YES | NO | ~467 |
| 35 | dashboard | 0 | pass | YES | NO | ~467 |

---

## Findings

### [P2] Pydantic UserWarning on every invocation (stderr noise)

**Detail**: Every autodev invocation emits two `pydantic` UserWarnings to stderr:

```
/opt/homebrew/lib/python3.11/site-packages/pydantic/_internal/_fields.py:132: UserWarning:
  Field "model_hint" in AgentCard has conflict with protected namespace "model_".
  You may be able to resolve this warning by setting `model_config['protected_namespaces'] = ()`.

/opt/homebrew/lib/python3.11/site-packages/pydantic/_internal/_fields.py:132: UserWarning:
  Field "model_settings" in AgentSpec has conflict with protected namespace "model_".
  You may be able to resolve this warning by setting `model_config['protected_namespaces'] = ()`.
```

These warnings appear on every command invocation (including `--help` and `--version`). They do not cause crashes or exit non-zero, but they:

- Pollute stderr for every user invocation
- Could confuse users who notice unexpected output
- May interfere with scripts that capture stderr to detect errors

**Fix**: In `AgentCard` and `AgentSpec` Pydantic model classes, add:

```python
model_config = ConfigDict(protected_namespaces=())
```

**Severity**: P2 (cosmetic/UX issue, not blocking, but visible to every user)

---

## Additional Checks

### `autodev --version`

```
autodev-ai 0.1.0a3
```

Exit code: 0. Expected version string confirmed.

### `autodev --help`

Exit code: 0. Lists all 35 commands in the Commands panel. No commands missing or extra vs spec.

### Command Discovery Comparison

**Spec list** (35): classify-input, create-prd, plan-project, plan-milestones, plan-tasks, execute-milestone, run-issue, deliver-project, continue-run, replay, scan, verify, release-check, report, export-delivery, push, create-pr, fix-bug, multi-patch-fix-bug, review, investigate, roundtable, mcp-serve, a2a-serve, a2a-register, a2a-call, sprint-start, sprint-status, sprint-retro, sprint-correct, design-ux, next, generate-context, document-project, dashboard

**Missing from spec**: none

**Extra vs spec**: none

---

## One-Line Summary

35/35 commands pass: exit 0 + Usage/Options in stdout + no Traceback; zero P0/P1; 1 P2 (pydantic `model_` namespace warnings on every invocation).
