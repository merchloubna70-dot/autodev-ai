# autodev-ai — Documentation & Onboarding Audit

**Round:** documentation_onboarding
**Date:** 2026-05-14
**Auditor:** Agent-I (read-only validation)
**Verdict:** `minor_polish_needed`

---

## Summary

| Metric | Value |
|---|---|
| Doc files audited | 23 |
| Total words | 10,625 |
| CLI commands documented | 34 / 35 (97%) |
| Env vars documented | 7 / 8 (88%) |
| Broken relative links (rendered) | 0 |
| Broken relative links (comment-guarded) | 1 (`docs/assets/demo.gif`) |
| Missing expected docs | 4 |
| Findings | 10 (0 high / 4 medium / 4 low / 2 info) |

---

## 1. File Inventory

All files listed in the audit scope exist:

| File | Exists | Words |
|---|---|---|
| `README.md` | yes | 1,228 |
| `docs/quickstart.md` | yes | 671 |
| `docs/architecture.md` | yes | 1,166 |
| `docs/faq.md` | yes | 1,054 |
| `docs/contributing.md` | yes | 195 |
| `docs/tutorials/01-bug-fix.md` | yes | 545 |
| `docs/tutorials/02-rust-project.md` | yes | 521 |
| `docs/tutorials/03-multi-cli-routing.md` | yes | 622 |
| `docs/tutorials/04-sprint-mode.md` | yes | 519 |
| `docs/tutorials/05-roundtable.md` | yes | 569 |
| `docs/tutorials/06-mcp-server.md` | yes | 467 |
| `docs/tutorials/07-a2a-server.md` | yes | 587 |
| `examples/README.md` | yes | 277 |
| `examples/01-mdlines/brief.md` … `10-prfaq-product/brief.md` | yes (all 10) | 2,204 total |
| `CHANGELOG.md` | **no** | — |
| `docs/configuration.md` | **no** | — |
| `docs/troubleshooting.md` | **no** | — |

---

## 2. README Install Paths

| Install method | Correct? | Notes |
|---|---|---|
| pip wheel from GitHub Release | yes | URL structure valid; not network-verified |
| pip install from source (`pip install -e ".[dev]"`) | yes | standard editable install |
| Docker pull | **partial** | org mismatch — see D-002 |
| PyPI badge | **misleading** | package not yet published; badge renders broken |
| PyPI install not offered in body | yes | README correctly says "install from wheel or source for now" |

---

## 3. CLI Command Documentation Coverage (35 commands)

All 35 `@app.command` definitions found in `src/autodev/cli.py`:

```
run-issue, deliver-project, classify-input, create-prd, plan-project,
plan-milestones, plan-tasks, execute-milestone, continue-run, replay, scan,
verify, release-check, report, export-delivery, push, create-pr, fix-bug,
multi-patch-fix-bug, review, roundtable, mcp-serve, a2a-serve, a2a-register,
a2a-call, next, design-ux, investigate, generate-context, document-project,
sprint-start, sprint-status, sprint-retro, sprint-correct, dashboard
```

**Documented: 34 / 35 (97%)**

**Undocumented: `dashboard`** — absent from the README "All CLI Commands" table and from all tutorials. The prior `autodev_cli_surface_audit.md` (finding F-002) confirms it requires the optional `textual` dependency and exits with code 1 if missing. New users will discover it only by running `autodev --help`.

---

## 4. Environment Variable Documentation Coverage

| Var | Source | Docs | Gap |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | yes | yes | — |
| `OPENAI_API_KEY` | yes | yes | — |
| `FACTORY_CODEX_BIN` | yes | yes (quickstart + multi_cli_executor.md) | — |
| `FACTORY_CODEX_CMD` | yes | yes (multi_cli_executor.md only) | README table missing |
| `FACTORY_CLAUDE_BIN` | yes | yes (quickstart + claude_code_adapter.md) | — |
| `FACTORY_CLAUDE_CMD` | yes | yes (claude_code_adapter.md only) | README table missing |
| `FACTORY_FORCE_MOCK` | yes | yes | — |
| `FACTORY_LOG` | yes | **no** | undocumented in all user-facing docs |

**7 / 8 documented (88%).** `FACTORY_LOG` is used in source but absent from all docs.

---

## 5. Broken Relative Links

| Source | Link | Status |
|---|---|---|
| `README.md` | `docs/assets/demo.gif` | File absent — inside comment block (`<!-- ... -->`), not rendered |

All other relative links in `README.md`, `docs/quickstart.md`, `docs/architecture.md`, `docs/faq.md`, and all seven tutorials resolve to existing files.

---

## 6. Five-Minute Quickstart Assessment

**Realistic: yes** — with one fix.

The quickstart path (install from source → `autodev deliver-project --allow-mock-executor true`) is complete, self-contained, requires no API key, and has expected-output blocks. The only blocker is that `docs/quickstart.md` Step 1 contains a placeholder clone URL (`your-org`) instead of the real repository. A new user copy-pasting verbatim will clone from a non-existent URL.

Once that placeholder is replaced, the five-minute path is fully copy-pasteable.

---

## 7. Missing Docs

| Missing file | Impact |
|---|---|
| `CHANGELOG.md` | Returning users / evaluators cannot track what changed between releases |
| `docs/configuration.md` | No single reference for all config options (FactoryConfig fields, env vars, executor params); currently scattered across FAQ + quickstart + adapter docs |
| `docs/troubleshooting.md` | No error-message → fix mapping; FAQ covers 15 Qs but not error codes |
| `docs/assets/demo.gif` | README has a comment-guarded placeholder; visual demo absent |

---

## 8. Outdated or Incorrect Content

| ID | Severity | File | Issue |
|---|---|---|---|
| D-001 | medium | `docs/quickstart.md` | Clone URL placeholder `your-org` not replaced |
| D-002 | medium | `README.md` | Docker org mismatch: `ghcr.io/merchloubna70-dot/` vs `ghcr.io/macworkers/` in `packaging/docker/README.md` |
| D-003 | low | `README.md` | PyPI badge points to unpublished package — renders as broken shield |
| D-004 | low | `README.md` | `dashboard` command absent from "All CLI Commands" table |
| D-005 | low | `docs/contributing.md` | Clone URL uses unreplaced `<org>` placeholder |
| D-006 | low | docs/ (all) | `FACTORY_LOG` env var used in source, undocumented |
| D-007 | low | (absent) | `CHANGELOG.md` missing |
| D-008 | low | (absent) | `docs/configuration.md` and `docs/troubleshooting.md` missing |
| D-009 | info | `README.md` | Demo GIF placeholder comment present; file absent |
| D-010 | info | `examples/README.md` | `run_example.sh` exists but executable status not verified |

---

## 9. Tutorial Quality

All 7 tutorials have:
- Copy-pasteable `bash` code blocks
- Expected-output blocks
- Correct relative links back to sibling tutorials and `architecture.md` / `faq.md`

No tutorial references a CLI command that does not exist in `cli.py`.

---

## 10. Verdict: `minor_polish_needed`

The documentation corpus is structurally sound: 23 files, 10,625 words, 7 tutorials with expected-output blocks, 97% CLI coverage, and a working 5-minute quickstart path. No tutorials reference phantom commands. All relative links resolve (except a comment-guarded GIF placeholder).

**Top 5 items to fix before GA:**

1. **D-001** — Replace `your-org` placeholder in `docs/quickstart.md` with `merchloubna70-dot`
2. **D-002** — Resolve Docker image org inconsistency (`merchloubna70-dot` vs `macworkers`)
3. **D-004 / D-006** — Add `dashboard` to README command table with dep note; add `FACTORY_LOG` to env var reference
4. **D-007** — Create `CHANGELOG.md` (even stub format) before v0.1.0-alpha promotion
5. **D-008** — Create `docs/configuration.md` consolidating FactoryConfig fields, all env vars, and executor config options currently scattered across three files
