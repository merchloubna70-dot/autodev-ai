# Round 7 Baseline Inventory — Repo Baseline Auditor (Agent 1)

Generated: 2026-05-14  
Round: round7 | Agent: 1 — repo_baseline_auditor  
Overall Result: **PASS**

---

## 1. Git State

| Field | Value |
|---|---|
| Branch | main |
| HEAD (full) | 0a227d4701edb48208a2d1dcfc161dd1140c0f49 |
| HEAD (short) | 0a227d4 |
| Dirty working tree | No (clean) |
| Total commits | 88 |

### Latest Tags (most recent first)

| Tag |
|---|
| v0.1.0a3 |
| v0.1.0a2 |
| v0.1.0a1 |
| v0.1.0-alpha |

### Last 10 Commits

| Hash | Message |
|---|---|
| 0a227d4 | homebrew: tap published + audit reorder |
| f862968 | post-publish: v0.1.0a3 verified — Homebrew formula backfilled to 0.1.0a3 |
| cc76f05 | release: v0.1.0a3 — bump version + CHANGELOG (typer + shim fix → PyPI) |
| e52fbad | fix(r5): quick post-publish hygiene — typer dep + gate wheel-shim + Homebrew tap prep |
| 967a13b | audit(r4.5): post-release hygiene — PyPI/GH/Docker verified, secret-leak=0, rotation checklist ready |
| 762719d | release(v0.1.0a2): PyPI published + Homebrew sha256 backfilled (Path B full) |
| d674d08 | release: v0.1.0a2 — bump version + CHANGELOG (PyPI Path B publish) |
| 357af6a | audit(post-publish): v0.1.0a1 verification — GitHub Release + Docker live, PyPI/Homebrew honestly skipped |
| 1e2bf90 | fix(docker): glob pattern for wheel COPY — 5th pre-publish blocker |
| 70a6e70 | fix(ci): add mypy>=1.5 to [dev] extras — 4th pre-publish blocker |

---

## 2. Environment

| Tool | Version |
|---|---|
| Python | 3.14.4 |
| pip | 26.0.1 |
| uv | present (/opt/homebrew/bin/uv) |

---

## 3. Code Inventory

### 3.1 src/autodev — Python Source

| Metric | Value |
|---|---|
| Total .py files | 174 |
| Total LoC | 25,681 |

#### Per-Module Breakdown

| Module | .py Files | LoC |
|---|---|---|
| agents | 44 | 7,465 |
| flows | 19 | 3,080 |
| adapters | 20 | 2,932 |
| executors | 14 | 2,150 |
| gates | 9 | 911 |
| mcp_server | 4 | 964 |
| planners | 8 | 1,120 |
| reports | 5 | 399 |
| scanners | 7 | 469 |
| tasks | 16 | 214 |
| tui | 4 | 634 |
| utils | 11 | 795 |
| context_providers | 6 | 262 |
| top-level .py | 7 | 4,286 |
| **TOTAL** | **174** | **25,681** |

### 3.2 Tests

| Suite | .py Files | LoC | Test Functions |
|---|---|---|---|
| tests/unit | 117 | 17,007 | 780 |
| tests/integration | 36 | 5,174 | 100 |
| **TOTAL** | **153** | **22,181** | **880** |

Note: `tests/conftest.py` exists at root (1 additional file not counted in suite totals above).

### 3.3 Documentation

| Category | Count |
|---|---|
| Total tracked .md files | 149 |
| docs/validation/ files | 162 (md + json combined) |
| docs/validation/ .md files | 80 |
| Other docs .md files | 32 |
| Non-validation .md LoC | 6,245 |
| README.md | 294 lines |
| CHANGELOG.md | 190 lines |
| LICENSE | 21 lines |

### 3.4 Packaging

| Category | Files |
|---|---|
| packaging/ directory | 23 |
| pyproject.toml | 1 |
| .github/ files (total) | 5 |
| **Total packaging-related** | **29** |

### 3.5 Workflows (.github/workflows/)

| File | Lines |
|---|---|
| docker-publish.yml | 109 |
| release.yml | 75 |
| test.yml | 37 |
| lint.yml | 28 |

---

## 4. pyproject.toml Analysis

| Field | Value |
|---|---|
| name | autodev-ai |
| version | 0.1.0a3 |
| requires-python | >=3.10 |
| build-backend | hatchling.build |

### 4.1 Dependencies

```
pydantic>=2.5,<3.0
typer>=0.12
rich>=13.7
shellingham>=1.5
PyYAML>=6.0
jinja2>=3.1
```

### 4.2 Optional Dependencies

| Group | Packages |
|---|---|
| crewai | crewai>=0.30 |
| tui | textual>=0.60 |
| dev | pytest>=8.0, pytest-asyncio>=0.23, pytest-cov>=4.1, ruff>=0.4, mypy>=1.5, tomli>=2.0 (py<3.11) |

### 4.3 Entry Points (scripts)

| Script | Target |
|---|---|
| autodev | autodev.cli:app |

### 4.4 Hatch Build Target

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/autodev"]
```

---

## 5. Findings

| Severity | Title | Detail |
|---|---|---|
| P4 | tasks module thin LoC | 16 .py files but only 214 LoC — average 13 lines/file; task definitions appear intentionally minimal (stub/data containers). Not a defect but worth noting. |
| P4 | Python 3.14.4 runtime vs declared >=3.10 | Dev environment runs 3.14.4, which is newer than classifiers list (3.10–3.12). No compatibility issues observed but classifier list is slightly stale. |

**P0=0  P1=0  P2=0  P3=0  P4=2**

---

## 6. Summary

**BASELINE: 174 src .py / 25,681 src LoC / 880 test funcs (22,181 test LoC) / 4 tags (latest v0.1.0a3) / git clean / Python 3.14.4 + uv present**
