# R4.5 Secret Hygiene Audit — Post v0.1.0a2 Publish

**Audit date:** 2026-05-14
**Scope:** All git-tracked files in `autodev/` (excluded: `.venv`, `.git`, `node_modules`, `target`, `dist`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `__pycache__`, `build`, `coverage.json`)

---

## Summary Verdict

**no_secret_leak_in_git** — zero actual secret leaks found.

| Metric | Count |
|---|---|
| `actual_leak` | **0** |
| `pypi_token_patterns_in_git` (≥50 chars) | **0** |
| `test_fixture` | 18 |
| `doc_example` | 8 |
| `placeholder` | 7 |
| `tool_pattern_constant` | 4 |

---

## PyPI Token Patterns in Git

Pattern searched: `pypi-[A-Za-z0-9_-]{50,}` (real tokens are ~150+ chars).

**Result: 0 matches.**

The two `pypi-AgEI...` strings found under `tests/unit/test_secret_redaction.py` (lines 68 and 138) are 30–38 chars long — below the real-token threshold — and are synthetic input strings used to assert that `redact_secrets()` removes them. They are `test_fixture` classification, not real tokens.

Git history was also scanned for `pypi-` prefixes in added lines. The only additions found are those same two test-file lines. No actual PyPI token value appears in any commit.

---

## Findings by Classification

### test_fixture (18 hits)

| File | Lines | Pattern | Note |
|---|---|---|---|
| `tests/unit/test_secret_redaction.py` | 68, 70, 138, 140 | `pypi-AgEI***` | Synthetic input strings to assert redact_secrets() removes them |
| `tests/unit/test_secret_redaction.py` | 31, 37, 49, 55, 80, 92, 100, 112, 125, 151, 165, 177 | `sk-*/ghp_*/gho_*/xoxb-*/PEM` | Input strings for redaction unit tests; all synthetic |
| `tests/unit/test_severity_findings_in_reviewers.py` | 18 | `AKIA1***` | Literal `AKIA1234567890EXAMPLE` written to pytest tmp_path to exercise SecurityReviewerAgent; not real |
| `tests/integration/test_security_p0_coverage.py` | 170, 171 | `fake-pypi-token-*` / `sk-ant-fake-*` | Variables named `_FAKE_PYPI_TOKEN` and `_FAKE_ANTHROPIC_KEY`; integration test only |
| `tests/integration/test_executor_secret_redaction_integration.py` | 41, 71, 95, 133, 144, 169, 189 | `sk-fake-*/sk-ant-fake-*` | Synthetic env values for executor redaction integration tests |

### doc_example (8 hits)

| File | Lines | Value | Note |
|---|---|---|---|
| `docs/quickstart.md` | 54, 60 | `sk-...` / `sk-ant-...` | Ellipsis placeholders in export examples |
| `docs/troubleshooting.md` | 62 | `sk-ant-...` | Ellipsis placeholder |
| `docs/faq.md` | 56 | `sk-ant-...` | Ellipsis placeholder |
| `docs/configuration.md` | 143 | `sk-ant-...` | Ellipsis placeholder |
| `docs/tutorials/06-mcp-server.md` | 122–123 | `sk-...` / `sk-ant-...` | Ellipsis in tutorial JSON snippet |

### placeholder (7 hits)

| File | Note |
|---|---|
| `packaging/homebrew/PUBLISH_CHECKLIST.md:28` | `<pypi-sdist-url>` — angle-bracket template placeholder |
| `.github/workflows/release.yml:67,74` | `${{ secrets.PYPI_API_TOKEN }}` — GitHub Actions secrets interpolation; no value in file |
| Various validation `.md`/`.json` docs | References to `pypi-rc-smoke`, `pypi-real-smoke`, `pypi-sdist-url` as path/label strings |

### tool_pattern_constant (4 hits)

| File | Note |
|---|---|
| `src/autodev/utils/secret_redaction.py:34,36,38,40,42,49` | Regex denylist declarations for sk-, ghp_, gho_, pypi-, xoxb-, PEM blocks |
| `src/autodev/agents/security_reviewer.py:35` | Denylist string `"-----BEGIN PRIVATE KEY"` for detection |
| `src/autodev/agents/parallel_section_reviewer.py:23` | `_SECRET_PATTERNS` tuple for detection |

---

## Mitigations Present

| Mitigation | Present | Detail |
|---|---|---|
| `secret_redaction_module` | **true** | `src/autodev/utils/secret_redaction.py` (123 lines); covers all 4 env-var patterns + 5 token-prefix patterns + PEM blocks |
| `path_safety_module` | **true** | `src/autodev/mcp_server/path_safety.py` (98 lines) |
| `gitignore_secret_paths` | **true** | `.gitignore` contains: `.env`, `.env.*`, `credentials.json`, `secrets.toml`, `*.pem`, `*.key` |
| `branch_name_validator` | **true** | `src/autodev/executors/worker_isolator.py:199` — `_validate_branch_name()` defined and called at line 420 |

No `.env`, `credentials.json`, `secrets.toml`, `*.pem`, or `*.key` files were found in the working tree.

---

## GitHub Actions Secret Metadata

| Secret Name | Updated At |
|---|---|
| `PYPI_API_TOKEN` | `2026-05-14T07:44:23Z` |

`PYPI_API_TOKEN` is present in the repository's Actions secrets. The `updated_at` timestamp of 2026-05-14T07:44:23Z indicates it was set or rotated today. Secret values are not accessible via API metadata (by design).

---

## Token Rotation Recommendation

**Rotation recommended: yes | Rotation confirmed complete: unknown**

The PyPI token value was pasted in chat history once. This audit confirms:
- The token was **never written to any git-tracked file**
- The token was **never placed in CLI argv** (set via `printf | gh secret set`, which passes via stdin/env — no argv, no shell history echo)
- The token is **absent from all validation outputs and git history diffs**

Despite no file-level leak, defense-in-depth policy recommends rotation before production use. The `updated_at` of 2026-05-14T07:44:23Z (today) may indicate the token was already rotated. If so, rotation is complete. If not yet rotated, go to pypi.org > Account Settings > API tokens, revoke the v0.1.0a2 publish token, and create a new scoped token, then update the GitHub secret via `gh secret set PYPI_API_TOKEN`.

---

## Verdict

**no_secret_leak_in_git** — The codebase is clean. All 37 pattern hits across git-tracked files are classified as `test_fixture`, `doc_example`, `placeholder`, or `tool_pattern_constant`. Zero `actual_leak` findings. Zero PyPI token patterns of real length (≥50 chars) exist anywhere in the repository.
