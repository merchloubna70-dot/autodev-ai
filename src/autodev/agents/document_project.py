"""DocumentProjectAgent — brownfield project documentation generator.

Scans an existing repo using pure-Python (AST + regex + git CLI) and
produces a set of AI-friendly onboarding Markdown documents under
``<repo_path>/.autodev/brownfield-docs/``.  Writes are idempotent.
"""
from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

from ..schemas import BrownfieldDoc, BrownfieldDocSection, Language

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_git(args: list[str], cwd: str) -> str:
    """Run a git sub-command; return stdout or '' on error."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _find_python_files(root: Path, limit: int = 300) -> list[Path]:
    files: list[Path] = []
    for p in sorted(root.rglob("*.py")):
        # skip hidden dirs, venv, __pycache__, build
        set(p.parts)
        if any(
            part.startswith(".") or part in {"__pycache__", "venv", ".venv", "node_modules", "dist", "build", "site-packages"}
            for part in p.relative_to(root).parts
        ):
            continue
        files.append(p)
        if len(files) >= limit:
            break
    return files


def _parse_toml_simple(text: str, section: str) -> dict[str, str]:
    """Naive TOML parser: extract key = "value" pairs inside a given [section]."""
    result: dict[str, str] = {}
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_section = stripped.startswith(f"[{section}") or stripped.startswith(f"[{section}.")
            continue
        if in_section and "=" in stripped:
            key, _, val = stripped.partition("=")
            val = val.strip().strip('"').strip("'")
            result[key.strip()] = val
    return result


# ---------------------------------------------------------------------------
# Section generators
# ---------------------------------------------------------------------------

class DocumentProjectAgent:
    """Generate brownfield AI-onboarding docs for an existing repository."""

    def document(
        self,
        repo_path: str,
        languages: list[Language] | None = None,
    ) -> BrownfieldDoc:
        root = Path(repo_path).resolve()
        output_dir = root / ".autodev" / "brownfield-docs"
        output_dir.mkdir(parents=True, exist_ok=True)

        langs = languages or []
        lang_strs = [lang.value for lang in langs]

        sections: list[BrownfieldDocSection] = []

        sections.append(self._overview(root))
        sections.append(self._architecture_overview(root))
        sections.append(self._entry_points(root))
        sections.append(self._key_data_models(root))
        sections.append(self._external_deps(root))
        sections.append(self._testing_conventions(root))
        sections.append(self._commit_history_patterns(root))

        for section in sections:
            file_path = output_dir / f"{section.name}.md"
            file_path.write_text(f"# {section.title}\n\n{section.body_markdown}\n", encoding="utf-8")
            section.file_path = str(file_path)

        return BrownfieldDoc(
            repo_path=str(root),
            sections=sections,
            output_dir=str(output_dir),
            languages=lang_strs,
        )

    # ------------------------------------------------------------------
    # 1. overview.md
    # ------------------------------------------------------------------

    def _overview(self, root: Path) -> BrownfieldDocSection:
        description = ""
        project_name = root.name

        # pyproject.toml
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            text = _read_file(pyproject)
            m = re.search(r'description\s*=\s*"([^"]+)"', text)
            if m:
                description = m.group(1)
            nm = re.search(r'name\s*=\s*"([^"]+)"', text)
            if nm:
                project_name = nm.group(1)

        # package.json
        if not description:
            pkg = root / "package.json"
            if pkg.exists():
                text = _read_file(pkg)
                m = re.search(r'"description"\s*:\s*"([^"]+)"', text)
                if m:
                    description = m.group(1)
                nm = re.search(r'"name"\s*:\s*"([^"]+)"', text)
                if nm and project_name == root.name:
                    project_name = nm.group(1)

        # Cargo.toml
        if not description:
            cargo = root / "Cargo.toml"
            if cargo.exists():
                text = _read_file(cargo)
                m = re.search(r'description\s*=\s*"([^"]+)"', text)
                if m:
                    description = m.group(1)

        # README fallback
        readme_text = ""
        for name in ("README.md", "README.rst", "README.txt", "README"):
            readme = root / name
            if readme.exists():
                readme_text = _read_file(readme)
                if not description:
                    # take first non-empty, non-heading line
                    for line in readme_text.splitlines():
                        line = line.strip()
                        if line and not line.startswith("#"):
                            description = line[:200]
                            break
                break

        lines = [
            f"**Project**: `{project_name}`",
            "",
            f"**Description**: {description or '(not found — add a description to pyproject.toml/package.json)'}",
            "",
        ]
        if readme_text:
            # Include first ~30 non-empty lines of README as context
            preview_lines = [ln for ln in readme_text.splitlines() if ln.strip()][:30]
            lines.append("## README Preview\n")
            lines.extend(preview_lines[:30])

        return BrownfieldDocSection(
            name="overview",
            title="Project Overview",
            body_markdown="\n".join(lines),
        )

    # ------------------------------------------------------------------
    # 2. architecture-overview.md
    # ------------------------------------------------------------------

    def _architecture_overview(self, root: Path) -> BrownfieldDocSection:
        lines: list[str] = []

        # Top-level directory tree (exclude hidden + common noise)
        skip = {".git", ".venv", "venv", "__pycache__", "node_modules", "dist", "build", ".mypy_cache", ".pytest_cache"}
        top_dirs: list[str] = []
        top_files: list[str] = []
        if root.exists():
            for child in sorted(root.iterdir()):
                if child.name in skip or child.name.startswith("."):
                    continue
                if child.is_dir():
                    top_dirs.append(child.name + "/")
                else:
                    top_files.append(child.name)

        lines.append("## Directory Structure\n")
        lines.append("```")
        lines.append(f"{root.name}/")
        for d in top_dirs:
            lines.append(f"  {d}")
        for f in top_files:
            lines.append(f"  {f}")
        lines.append("```\n")

        # Python module map: collect top-level packages
        python_pkgs: dict[str, list[str]] = {}
        for src_dir in sorted(root.rglob("__init__.py")):
            rel = src_dir.parent.relative_to(root)
            parts = rel.parts
            if not parts:
                continue
            # skip venv etc.
            if any(p in skip or p.startswith(".") for p in parts):
                continue
            pkg = parts[0]
            sub = ".".join(parts[1:]) if len(parts) > 1 else "(root)"
            python_pkgs.setdefault(pkg, []).append(sub)

        if python_pkgs:
            lines.append("## Python Packages\n")
            for pkg, subs in sorted(python_pkgs.items()):
                lines.append(f"- **`{pkg}`** — sub-modules: {', '.join(sorted(subs)[:10])}")
            lines.append("")

        # Detect common architectural layers by directory names
        arch_clues: dict[str, str] = {
            "agents": "Agent layer",
            "flows": "Orchestration flows",
            "gates": "Quality / safety gates",
            "executors": "Execution backends",
            "scanners": "Repo / code scanners",
            "planners": "Planning agents",
            "reports": "Reporting layer",
            "adapters": "External service adapters",
            "schemas": "Shared data schemas",
            "utils": "Utilities",
            "api": "HTTP API layer",
            "routes": "HTTP routes",
            "models": "Database / ORM models",
            "tasks": "Async task queue",
            "templates": "Templates",
        }
        found_layers: list[str] = []
        for child in sorted(root.rglob("*")):
            if child.is_dir() and child.name in arch_clues:
                rel_str = str(child.relative_to(root))
                if not any(s in rel_str for s in skip):
                    found_layers.append(f"- `{rel_str}/` — {arch_clues[child.name]}")

        if found_layers:
            lines.append("## Architectural Layers Detected\n")
            lines.extend(found_layers[:20])
            lines.append("")

        return BrownfieldDocSection(
            name="architecture-overview",
            title="Architecture Overview",
            body_markdown="\n".join(lines),
        )

    # ------------------------------------------------------------------
    # 3. entry-points.md
    # ------------------------------------------------------------------

    def _entry_points(self, root: Path) -> BrownfieldDocSection:
        lines: list[str] = []

        # pyproject.toml [project.scripts]
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            text = _read_file(pyproject)
            scripts_match = re.search(r'\[project\.scripts\](.*?)(?=\[|\Z)', text, re.DOTALL)
            if scripts_match:
                lines.append("## pyproject.toml `[project.scripts]`\n")
                for line in scripts_match.group(1).splitlines():
                    if "=" in line.strip():
                        lines.append(f"- `{line.strip()}`")
                lines.append("")

            # also check [tool.poetry.scripts]
            poetry_scripts = re.search(r'\[tool\.poetry\.scripts\](.*?)(?=\[|\Z)', text, re.DOTALL)
            if poetry_scripts:
                lines.append("## `[tool.poetry.scripts]`\n")
                for line in poetry_scripts.group(1).splitlines():
                    if "=" in line.strip():
                        lines.append(f"- `{line.strip()}`")
                lines.append("")

        # package.json bin
        pkg = root / "package.json"
        if pkg.exists():
            text = _read_file(pkg)
            bin_match = re.search(r'"bin"\s*:\s*\{([^}]+)\}', text)
            if bin_match:
                lines.append("## package.json `bin` entries\n")
                for line in bin_match.group(1).splitlines():
                    if ":" in line:
                        lines.append(f"- {line.strip()}")
                lines.append("")

        # main.py / __main__.py
        for name in ("main.py", "__main__.py", "app.py", "server.py", "run.py"):
            candidates = list(root.rglob(name))[:5]
            for c in candidates:
                rel = c.relative_to(root)
                parts = set(rel.parts)
                if any(p in {".venv", "venv", "__pycache__", "node_modules"} for p in parts):
                    continue
                lines.append(f"## `{rel}` (main / entrypoint)\n")
                # show first 20 lines
                content_lines = _read_file(c).splitlines()[:20]
                lines.append("```python")
                lines.extend(content_lines)
                lines.append("```\n")

        # HTTP routes (FastAPI / Flask / Django)
        route_patterns = [
            (re.compile(r'@(?:app|router|bp)\.(get|post|put|patch|delete|route)\s*\(\s*["\']([^"\']+)["\']'), "HTTP route"),
            (re.compile(r'path\s*\(\s*["\']([^"\']+)["\']'), "Django urlpattern"),
        ]
        route_hits: list[str] = []
        for py_file in _find_python_files(root, limit=200):
            text = _read_file(py_file)
            rel_str = str(py_file.relative_to(root))
            for pat, label in route_patterns:
                for m in pat.finditer(text):
                    if label == "HTTP route":
                        route_hits.append(f"- `{rel_str}` — {m.group(1).upper()} `{m.group(2)}`")
                    else:
                        route_hits.append(f"- `{rel_str}` — {label} `{m.group(1)}`")

        if route_hits:
            lines.append("## HTTP Routes Detected\n")
            lines.extend(route_hits[:40])
            lines.append("")

        if not lines:
            lines.append("_No entry points detected. Add `[project.scripts]` to pyproject.toml or create a `main.py`._")

        return BrownfieldDocSection(
            name="entry-points",
            title="Entry Points",
            body_markdown="\n".join(lines),
        )

    # ------------------------------------------------------------------
    # 4. key-data-models.md
    # ------------------------------------------------------------------

    def _key_data_models(self, root: Path) -> BrownfieldDocSection:
        lines: list[str] = []

        pydantic_models: list[tuple[str, str, list[str]]] = []  # (file, class, fields)
        dataclasses_found: list[tuple[str, str]] = []
        sql_tables: list[tuple[str, str]] = []

        for py_file in _find_python_files(root, limit=200):
            text = _read_file(py_file)
            if not text:
                continue
            rel = str(py_file.relative_to(root))

            # SQL table detection (SQLAlchemy / raw CREATE TABLE)
            for m in re.finditer(r'__tablename__\s*=\s*["\'](\w+)["\']', text):
                sql_tables.append((rel, m.group(1)))
            for m in re.finditer(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?["`]?(\w+)["`]?', text, re.IGNORECASE):
                sql_tables.append((rel, m.group(1)))

            # AST-based Pydantic / dataclass detection
            try:
                tree = ast.parse(text, filename=str(py_file))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                # Check if it extends BaseModel or is @dataclass
                bases = [ast.unparse(b) if hasattr(ast, "unparse") else getattr(b, "id", "") for b in node.bases]
                is_pydantic = any("BaseModel" in b or "pydantic" in b.lower() for b in bases)
                is_dataclass = any(
                    (isinstance(d, ast.Name) and d.id == "dataclass") or
                    (isinstance(d, ast.Attribute) and d.attr == "dataclass")
                    for d in node.decorator_list
                )

                if is_pydantic:
                    fields: list[str] = []
                    for item in node.body:
                        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                            ann = ast.unparse(item.annotation) if hasattr(ast, "unparse") else "?"
                            fields.append(f"{item.target.id}: {ann}")
                    pydantic_models.append((rel, node.name, fields[:10]))
                elif is_dataclass:
                    dataclasses_found.append((rel, node.name))

        if pydantic_models:
            lines.append("## Pydantic Models\n")
            for rel, cls, fields in pydantic_models[:30]:
                lines.append(f"### `{cls}` — `{rel}`\n")
                if fields:
                    lines.append("```")
                    for f in fields:
                        lines.append(f"  {f}")
                    lines.append("```\n")
                else:
                    lines.append("_(no annotated fields detected)_\n")

        if dataclasses_found:
            lines.append("## Dataclasses\n")
            for rel, cls in dataclasses_found[:20]:
                lines.append(f"- `{cls}` — `{rel}`")
            lines.append("")

        if sql_tables:
            lines.append("## SQL Tables / ORM Models\n")
            seen: set[str] = set()
            for rel, tbl in sql_tables:
                key = f"{rel}::{tbl}"
                if key not in seen:
                    seen.add(key)
                    lines.append(f"- `{tbl}` — `{rel}`")
            lines.append("")

        if not lines:
            lines.append("_No Pydantic models, dataclasses, or SQL tables detected._")

        return BrownfieldDocSection(
            name="key-data-models",
            title="Key Data Models",
            body_markdown="\n".join(lines),
        )

    # ------------------------------------------------------------------
    # 5. external-deps.md
    # ------------------------------------------------------------------

    def _external_deps(self, root: Path) -> BrownfieldDocSection:
        lines: list[str] = []

        # pyproject.toml
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            text = _read_file(pyproject)
            # [project.dependencies]
            dep_match = re.search(r'\[project\.dependencies\](.*?)(?=\[|\Z)', text, re.DOTALL)
            if dep_match:
                lines.append("## Python dependencies (`[project.dependencies]`)\n")
                for line in dep_match.group(1).splitlines():
                    s = line.strip().strip('"').strip("'").strip(",")
                    if s and not s.startswith("[") and not s.startswith("#"):
                        lines.append(f"- `{s}`")
                lines.append("")

            # [tool.poetry.dependencies]
            poetry_match = re.search(r'\[tool\.poetry\.dependencies\](.*?)(?=\[|\Z)', text, re.DOTALL)
            if poetry_match:
                lines.append("## Python dependencies (`[tool.poetry.dependencies]`)\n")
                for line in poetry_match.group(1).splitlines():
                    s = line.strip()
                    if s and not s.startswith("[") and not s.startswith("#") and "=" in s:
                        lines.append(f"- `{s}`")
                lines.append("")

        # requirements.txt
        req_files = list(root.glob("requirements*.txt"))[:3]
        for req in req_files:
            text = _read_file(req)
            lines.append(f"## `{req.name}`\n")
            pkgs = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
            for p in pkgs[:40]:
                lines.append(f"- `{p}`")
            lines.append("")

        # package.json
        pkg = root / "package.json"
        if pkg.exists():
            text = _read_file(pkg)
            dep_section = re.search(r'"dependencies"\s*:\s*\{([^}]+)\}', text)
            dev_section = re.search(r'"devDependencies"\s*:\s*\{([^}]+)\}', text)
            if dep_section:
                lines.append("## npm `dependencies`\n")
                for m in re.finditer(r'"([\w@/.-]+)"\s*:\s*"([^"]+)"', dep_section.group(1)):
                    lines.append(f"- `{m.group(1)}@{m.group(2)}`")
                lines.append("")
            if dev_section:
                lines.append("## npm `devDependencies`\n")
                for m in re.finditer(r'"([\w@/.-]+)"\s*:\s*"([^"]+)"', dev_section.group(1)):
                    lines.append(f"- `{m.group(1)}@{m.group(2)}`")
                lines.append("")

        # Cargo.toml
        cargo = root / "Cargo.toml"
        if cargo.exists():
            text = _read_file(cargo)
            dep_match = re.search(r'\[dependencies\](.*?)(?=\[|\Z)', text, re.DOTALL)
            if dep_match:
                lines.append("## Rust `[dependencies]`\n")
                for line in dep_match.group(1).splitlines():
                    s = line.strip()
                    if s and not s.startswith("#") and not s.startswith("["):
                        lines.append(f"- `{s}`")
                lines.append("")

        if not lines:
            lines.append("_No dependency files detected (pyproject.toml / requirements.txt / package.json / Cargo.toml)._")

        return BrownfieldDocSection(
            name="external-deps",
            title="External Dependencies",
            body_markdown="\n".join(lines),
        )

    # ------------------------------------------------------------------
    # 6. testing-conventions.md
    # ------------------------------------------------------------------

    def _testing_conventions(self, root: Path) -> BrownfieldDocSection:
        lines: list[str] = []

        # pytest.ini / pyproject.toml [tool.pytest] / setup.cfg
        pytest_config: list[str] = []
        for cfg_name in ("pytest.ini", "setup.cfg"):
            cfg = root / cfg_name
            if cfg.exists():
                text = _read_file(cfg)
                m = re.search(r'\[pytest\](.*?)(?=\[|\Z)', text, re.DOTALL)
                if m:
                    pytest_config.append(f"**{cfg_name}** `[pytest]` section:")
                    pytest_config.extend(m.group(1).strip().splitlines()[:15])

        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            text = _read_file(pyproject)
            m = re.search(r'\[tool\.pytest\.ini_options\](.*?)(?=\[|\Z)', text, re.DOTALL)
            if m:
                pytest_config.append("**pyproject.toml** `[tool.pytest.ini_options]`:")
                pytest_config.extend(m.group(1).strip().splitlines()[:15])

        if pytest_config:
            lines.append("## Pytest Configuration\n")
            lines.extend(pytest_config)
            lines.append("")

        # Jest config
        jest_candidates = ["jest.config.js", "jest.config.ts", "jest.config.mjs"]
        for jc in jest_candidates:
            jest_file = root / jc
            if jest_file.exists():
                lines.append(f"## Jest (`{jc}`)\n")
                lines.append("```js")
                lines.extend(_read_file(jest_file).splitlines()[:20])
                lines.append("```\n")

        # Test directory layout
        test_dirs: list[str] = []
        for pattern in ("tests", "test", "spec", "__tests__"):
            td = root / pattern
            if td.is_dir():
                test_dirs.append(f"- `{pattern}/`")
                # list immediate sub-dirs
                for sub in sorted(td.iterdir()):
                    if sub.is_dir() and not sub.name.startswith("."):
                        test_dirs.append(f"  - `{pattern}/{sub.name}/`")

        if test_dirs:
            lines.append("## Test Directory Layout\n")
            lines.extend(test_dirs)
            lines.append("")

        # Fixture files
        fixture_hits: list[str] = []
        for py_file in _find_python_files(root, limit=200):
            text = _read_file(py_file)
            if "@pytest.fixture" in text:
                rel = str(py_file.relative_to(root))
                count = text.count("@pytest.fixture")
                fixture_hits.append(f"- `{rel}` — {count} fixture(s)")

        if fixture_hits:
            lines.append("## Fixture Files\n")
            lines.extend(fixture_hits[:20])
            lines.append("")

        if not lines:
            lines.append("_No testing configuration detected._")

        return BrownfieldDocSection(
            name="testing-conventions",
            title="Testing Conventions",
            body_markdown="\n".join(lines),
        )

    # ------------------------------------------------------------------
    # 7. commit-history-patterns.md
    # ------------------------------------------------------------------

    def _commit_history_patterns(self, root: Path, n: int = 50) -> BrownfieldDocSection:
        lines: list[str] = []

        git_log = _run_git(
            ["log", f"-{n}", "--pretty=format:%s", "--no-merges"],
            cwd=str(root),
        )
        if not git_log:
            lines.append("_No git history found or repository is not a git repo._")
            return BrownfieldDocSection(
                name="commit-history-patterns",
                title="Commit History Patterns",
                body_markdown="\n".join(lines),
            )

        commits = [c.strip() for c in git_log.splitlines() if c.strip()]

        # Classify by conventional commit prefixes
        categories: dict[str, list[str]] = {
            "feat": [],
            "fix": [],
            "refactor": [],
            "test": [],
            "docs": [],
            "chore": [],
            "build": [],
            "ci": [],
            "perf": [],
            "other": [],
        }

        conv_pattern = re.compile(r'^(feat|fix|refactor|test|docs|chore|build|ci|perf|style|revert)[\(:]')

        for commit in commits:
            m = conv_pattern.match(commit.lower())
            if m:
                cat = m.group(1)
                if cat in categories:
                    categories[cat].append(commit)
                else:
                    categories["other"].append(commit)
            else:
                categories["other"].append(commit)

        total = len(commits)
        conventional_count = sum(len(v) for k, v in categories.items() if k != "other")
        uses_conventional = conventional_count > total * 0.3

        lines.append(f"**Total commits analysed**: {total}")
        lines.append(f"**Conventional Commits style**: {'yes' if uses_conventional else 'no (or mixed)'}\n")

        for cat, msgs in categories.items():
            if msgs:
                lines.append(f"## {cat.capitalize()} ({len(msgs)})\n")
                for msg in msgs[:10]:
                    lines.append(f"- {msg}")
                lines.append("")

        return BrownfieldDocSection(
            name="commit-history-patterns",
            title="Commit History Patterns",
            body_markdown="\n".join(lines),
        )


# BMAD-17: register agent menu at module load time
from ..schemas import AgentMenuEntry  # noqa: E402
from ._menu import register_default_menu  # noqa: E402

register_default_menu("document_project", [
    AgentMenuEntry(code="DP", description="Document existing brownfield project", skill="document_project"),
    AgentMenuEntry(code="ES", description="Export section docs", skill="document_project"),
])
