"""ContextGeneratorAgent — BMAD-11 generate-project-context.

Scans a repo for conventions/hints and produces _autodev/project-context.md
(and .json) without making any LLM calls in the default path.

Three steps mirror the BMAD skill:
  1. discover(repo_path) -> DiscoveryReport
  2. synthesize(discovery, prd, brief) -> ProjectContextDraft
  3. commit_to_disk(draft, repo_path) -> ProjectContext
  .run(...) orchestrates all three.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..schemas import (
    PRD,
    ContextRule,
    DiscoveryReport,
    ProjectContext,
    ProjectContextDraft,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_CONVENTION_FILE_NAMES = [
    "AGENTS.md",
    "CLAUDE.md",
    ".cursorrules",
    "CONTRIBUTING.md",
    "DEVELOPMENT.md",
    "HACKING.md",
]

_CURSOR_RULES_GLOB = ".cursor/rules"


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return ""


# ---------------------------------------------------------------------------
# ContextGeneratorAgent
# ---------------------------------------------------------------------------


class ContextGeneratorAgent:
    """Pure-Python agent; no LLM calls in default path."""

    # ------------------------------------------------------------------
    # Step 1: Discover
    # ------------------------------------------------------------------

    def discover(self, repo_path: str | Path) -> DiscoveryReport:
        """Scan repo for hints and populate a DiscoveryReport."""
        root = Path(repo_path)
        report = DiscoveryReport()

        # --- Convention files ---
        conv_files: list[str] = []
        for name in _CONVENTION_FILE_NAMES:
            if (root / name).is_file():
                conv_files.append(name)
        cursor_rules_dir = root / _CURSOR_RULES_GLOB
        if cursor_rules_dir.is_dir():
            for f in sorted(cursor_rules_dir.iterdir()):
                if f.suffix in {".md", ".mdc"}:
                    conv_files.append(str(f.relative_to(root)))
        report.existing_conventions_files = conv_files

        # --- Language detection ---
        langs: list[str] = []
        if (root / "pyproject.toml").is_file() or (root / "setup.py").is_file() or (root / "requirements.txt").is_file():
            langs.append("python")
        if (root / "package.json").is_file():
            langs.append("typescript" if (root / "tsconfig.json").is_file() else "javascript")
        if (root / "Cargo.toml").is_file():
            langs.append("rust")
        if (root / "go.mod").is_file():
            langs.append("go")
        report.languages_detected = langs or ["unknown"]

        # --- Package manager ---
        report.package_manager = self._detect_package_manager(root)

        # --- Lint tools ---
        report.lint_tools = self._detect_lint_tools(root)

        # --- Test frameworks ---
        report.test_frameworks = self._detect_test_frameworks(root)

        # --- Pre-commit hooks ---
        report.pre_commit_hooks = self._detect_pre_commit(root)

        # --- Commit style ---
        report.commit_style = self._detect_commit_style(root)

        # --- Notes from existing convention files ---
        notes: list[str] = []
        for rel in conv_files:
            text = _safe_read(root / rel)
            if text:
                notes.append(f"found {rel} ({len(text)} chars)")
        report.notes = notes

        return report

    def _detect_package_manager(self, root: Path) -> str | None:
        if (root / "uv.lock").is_file():
            return "uv"
        if (root / "poetry.lock").is_file():
            return "poetry"
        if (root / "Pipfile").is_file():
            return "pipenv"
        if (root / "pyproject.toml").is_file():
            txt = _safe_read(root / "pyproject.toml")
            if "[tool.poetry]" in txt:
                return "poetry"
            if "[build-system]" in txt and "hatch" in txt:
                return "hatch"
            return "pip"
        if (root / "requirements.txt").is_file():
            return "pip"
        if (root / "yarn.lock").is_file():
            return "yarn"
        if (root / "pnpm-lock.yaml").is_file():
            return "pnpm"
        if (root / "package-lock.json").is_file():
            return "npm"
        return None

    def _detect_lint_tools(self, root: Path) -> list[str]:
        tools: list[str] = []
        pyproject = _safe_read(root / "pyproject.toml") if (root / "pyproject.toml").is_file() else ""
        if "[tool.ruff]" in pyproject or (root / "ruff.toml").is_file() or (root / ".ruff.toml").is_file():
            tools.append("ruff")
        if "[tool.black]" in pyproject or (root / ".black").is_file():
            tools.append("black")
        if "[tool.mypy]" in pyproject or (root / "mypy.ini").is_file() or (root / ".mypy.ini").is_file():
            tools.append("mypy")
        if (root / ".flake8").is_file() or (root / "setup.cfg").is_file():
            txt = _safe_read(root / "setup.cfg")
            if "[flake8]" in txt:
                tools.append("flake8")
        if (root / ".eslintrc").is_file() or (root / ".eslintrc.js").is_file() or (root / ".eslintrc.json").is_file():
            tools.append("eslint")
        if (root / ".prettierrc").is_file() or (root / ".prettierrc.json").is_file() or (root / ".prettierrc.js").is_file():
            tools.append("prettier")
        if (root / "clippy.toml").is_file() or (root / ".clippy.toml").is_file():
            tools.append("clippy")
        return tools

    def _detect_test_frameworks(self, root: Path) -> list[str]:
        frameworks: list[str] = []
        pyproject = _safe_read(root / "pyproject.toml") if (root / "pyproject.toml").is_file() else ""
        if "pytest" in pyproject or (root / "pytest.ini").is_file() or (root / "conftest.py").is_file():
            frameworks.append("pytest")
        if "unittest" in pyproject:
            frameworks.append("unittest")
        pkg_json = _safe_read(root / "package.json") if (root / "package.json").is_file() else ""
        if "jest" in pkg_json:
            frameworks.append("jest")
        if "vitest" in pkg_json:
            frameworks.append("vitest")
        if "mocha" in pkg_json:
            frameworks.append("mocha")
        if (root / "Cargo.toml").is_file():
            frameworks.append("cargo-test")
        return frameworks

    def _detect_pre_commit(self, root: Path) -> list[str]:
        pre_commit_cfg = root / ".pre-commit-config.yaml"
        if not pre_commit_cfg.is_file():
            return []
        text = _safe_read(pre_commit_cfg)
        hooks: list[str] = []
        for line in text.splitlines():
            m = re.search(r"\bid:\s*([^\s]+)", line)
            if m:
                hooks.append(m.group(1))
        return hooks[:10]  # cap at 10

    def _detect_commit_style(self, root: Path) -> str | None:
        # Check .commitlintrc*, commitlint.config.js, or conventional-changelog in package.json
        for name in (".commitlintrc", ".commitlintrc.json", ".commitlintrc.yaml", ".commitlintrc.yml", "commitlint.config.js"):
            if (root / name).is_file():
                return "conventional"
        pkg_json = _safe_read(root / "package.json") if (root / "package.json").is_file() else ""
        if "conventional" in pkg_json.lower() or "commitlint" in pkg_json.lower():
            return "conventional"
        # Check CONTRIBUTING.md for clues
        contrib = _safe_read(root / "CONTRIBUTING.md") if (root / "CONTRIBUTING.md").is_file() else ""
        if "conventional commit" in contrib.lower() or "feat:" in contrib or "fix:" in contrib:
            return "conventional"
        # Check recent git log if available
        git_log_file = root / ".git" / "COMMIT_EDITMSG"
        if git_log_file.is_file():
            msg = _safe_read(git_log_file).strip()
            if re.match(r"^(feat|fix|chore|docs|refactor|test|style|perf|ci|build|revert)(\(.+\))?!?:", msg):
                return "conventional"
        if (root / ".git").is_dir():
            return "unknown"
        return None

    # ------------------------------------------------------------------
    # Step 2: Synthesize
    # ------------------------------------------------------------------

    def synthesize(
        self,
        discovery: DiscoveryReport,
        prd: PRD | None = None,
        brief: str | None = None,
    ) -> ProjectContextDraft:
        """Turn raw discovery findings into RULE statements."""
        rules: list[ContextRule] = []
        rule_idx = 1

        def add(
            statement: str,
            rationale: str,
            sources: list[str],
            category: str = "general",
            severity: str = "must",
        ) -> None:
            nonlocal rule_idx
            rules.append(
                ContextRule(
                    rule_id=f"CTX-{rule_idx:03d}",
                    statement=statement,
                    rationale=rationale,
                    sources=sources,
                    category=category,
                    severity_hint=severity,
                )
            )
            rule_idx += 1

        # Package manager
        pm = discovery.package_manager
        if pm == "uv":
            add(
                "Use `uv` not `pip` for dependency management",
                "uv.lock detected; pip installs may bypass lockfile pinning",
                ["uv.lock"],
                category="build",
            )
        elif pm == "poetry":
            add(
                "Use `poetry` for dependency management; do not edit requirements.txt directly",
                "poetry.lock / [tool.poetry] detected",
                ["pyproject.toml"],
                category="build",
            )
        elif pm == "pip" and "python" in discovery.languages_detected:
            add(
                "Use `pip` / requirements.txt for dependency management",
                "requirements.txt or pyproject.toml without lockfile found",
                ["requirements.txt"],
                category="build",
                severity="should",
            )

        # Lint tools
        if "ruff" in discovery.lint_tools:
            add(
                "Run `ruff check` and `ruff format` before committing; do not use black+isort separately",
                "ruff config detected — it replaces black/isort/flake8",
                ["pyproject.toml"],
                category="lint",
            )
        elif "black" in discovery.lint_tools:
            add(
                "Run `black` for formatting before committing",
                "[tool.black] config detected",
                ["pyproject.toml"],
                category="lint",
            )
        if "mypy" in discovery.lint_tools:
            add(
                "Maintain mypy type-check compliance; do not suppress errors with `# type: ignore` without a comment",
                "mypy config detected in project",
                ["pyproject.toml", "mypy.ini"],
                category="lint",
            )
        if "eslint" in discovery.lint_tools:
            add(
                "Run `eslint` before committing JavaScript/TypeScript files",
                ".eslintrc config detected",
                [".eslintrc"],
                category="lint",
            )
        if "clippy" in discovery.lint_tools:
            add(
                "Run `cargo clippy -- -D warnings` before committing Rust code",
                "clippy.toml detected",
                ["clippy.toml"],
                category="lint",
            )

        # Test frameworks
        if "pytest" in discovery.test_frameworks:
            add(
                "Use pytest for all Python tests; place tests under tests/ directory",
                "pytest detected as test runner",
                ["pyproject.toml", "conftest.py"],
                category="test",
            )
        if "cargo-test" in discovery.test_frameworks:
            add(
                "Use `cargo test` for Rust tests; unit tests in the same file, integration under tests/",
                "Cargo.toml detected",
                ["Cargo.toml"],
                category="test",
            )

        # Pre-commit hooks
        if discovery.pre_commit_hooks:
            hook_names = ", ".join(discovery.pre_commit_hooks[:5])
            add(
                f"Pre-commit hooks are enforced: {hook_names}; run `pre-commit run --all-files` before push",
                ".pre-commit-config.yaml present; hooks will fail CI if skipped",
                [".pre-commit-config.yaml"],
                category="build",
            )

        # Commit style
        if discovery.commit_style == "conventional":
            add(
                "Commit messages MUST follow Conventional Commits format: `type(scope): description`",
                "commitlint or conventional-changelog tooling detected; non-conforming messages will fail CI",
                [".commitlintrc", "commitlint.config.js"],
                category="commit-style",
            )

        # Language-specific idioms
        if "python" in discovery.languages_detected:
            add(
                "Python 3.10+ syntax is allowed (match-case, X | Y union types, etc.)",
                "Project targets Python 3.10+ based on pyproject/schemas usage",
                ["pyproject.toml"],
                category="lang-idiom",
                severity="should",
            )
        if "typescript" in discovery.languages_detected:
            add(
                "Use ESM imports (import/export); do not use require()",
                "tsconfig.json detected; project likely uses ESM module system",
                ["tsconfig.json"],
                category="lang-idiom",
            )

        # Existing convention files hint
        if discovery.existing_conventions_files:
            files_str = ", ".join(discovery.existing_conventions_files[:3])
            add(
                f"Read {files_str} before implementing — they contain project-specific agent rules",
                "Convention files exist in the repo root; LLM agents must load them for context",
                discovery.existing_conventions_files[:3],
                category="domain",
            )

        # Brief-derived rules
        if brief:
            # Pull any explicit constraints mentioned
            brief_lower = brief.lower()
            if "no mock" in brief_lower or "no mocking" in brief_lower:
                add(
                    "Do not use mock objects in production code paths",
                    "Project brief explicitly disallows mocking outside tests",
                    ["project_brief"],
                    category="test",
                )
            if "type hint" in brief_lower or "type annotation" in brief_lower:
                add(
                    "All Python functions must have full type annotations",
                    "Project brief requires type hints throughout",
                    ["project_brief"],
                    category="lang-idiom",
                )

        return ProjectContextDraft(rules=rules, discovery=discovery)

    # ------------------------------------------------------------------
    # Step 3: Commit to disk
    # ------------------------------------------------------------------

    def commit_to_disk(
        self,
        draft: ProjectContextDraft,
        repo_path: str | Path,
        product_name: str = "",
    ) -> ProjectContext:
        """Write _autodev/project-context.md and .json.  Idempotent (overwrite)."""
        root = Path(repo_path)
        out_dir = root / "_autodev"
        out_dir.mkdir(parents=True, exist_ok=True)

        md_path = out_dir / "project-context.md"
        json_path = out_dir / "project-context.json"

        from datetime import datetime, timezone
        generated_at = datetime.now(timezone.utc).isoformat()

        ctx = ProjectContext(
            product_name=product_name or root.name,
            generated_at=generated_at,
            rules=draft.rules,
            discovery=draft.discovery,
            file_path=str(md_path),
        )

        # Write markdown
        md_lines: list[str] = [
            f"# Project Context — {ctx.product_name}",
            "",
            f"_Generated: {ctx.generated_at}_",
            "",
            "## Purpose",
            "",
            "This file captures non-obvious rules, conventions, pitfalls, and domain constants",
            "that LLM agents MUST follow during implementation. It is machine-generated by",
            "`autodev generate-context` and safe to re-generate (idempotent).",
            "",
        ]

        if draft.discovery:
            d = draft.discovery
            md_lines += [
                "## Discovery Summary",
                "",
                f"- **Languages**: {', '.join(d.languages_detected)}",
                f"- **Package manager**: {d.package_manager or 'unknown'}",
                f"- **Lint tools**: {', '.join(d.lint_tools) or 'none detected'}",
                f"- **Test frameworks**: {', '.join(d.test_frameworks) or 'none detected'}",
                f"- **Commit style**: {d.commit_style or 'unknown'}",
            ]
            if d.existing_conventions_files:
                md_lines.append(f"- **Convention files**: {', '.join(d.existing_conventions_files)}")
            if d.pre_commit_hooks:
                md_lines.append(f"- **Pre-commit hooks**: {', '.join(d.pre_commit_hooks)}")
            md_lines.append("")

        # Group rules by category
        if draft.rules:
            from collections import defaultdict
            by_cat: dict[str, list[ContextRule]] = defaultdict(list)
            for r in draft.rules:
                by_cat[r.category].append(r)

            md_lines += ["## Rules", ""]
            for cat, cat_rules in sorted(by_cat.items()):
                md_lines.append(f"### {cat.title()}")
                md_lines.append("")
                for r in cat_rules:
                    badge = r.severity_hint.upper()
                    md_lines.append(f"**[{r.rule_id}]** `[{badge}]` {r.statement}")
                    if r.rationale:
                        md_lines.append(f"> {r.rationale}")
                    if r.sources:
                        md_lines.append(f"> _Sources: {', '.join(r.sources)}_")
                    md_lines.append("")

        md_path.write_text("\n".join(md_lines), encoding="utf-8")

        # Write JSON (machine-parseable)
        json_path.write_text(
            ctx.model_dump_json(indent=2),
            encoding="utf-8",
        )

        return ctx

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------

    def run(
        self,
        repo_path: str | Path = ".",
        prd: PRD | None = None,
        brief: str | None = None,
        product_name: str = "",
    ) -> ProjectContext:
        """Discover → synthesize → commit.  Returns the committed ProjectContext."""
        discovery = self.discover(repo_path)
        draft = self.synthesize(discovery, prd=prd, brief=brief)
        return self.commit_to_disk(draft, repo_path, product_name=product_name)


# BMAD-17: register agent menu at module load time
from ..schemas import AgentMenuEntry  # noqa: E402
from ._menu import register_default_menu  # noqa: E402

register_default_menu("context_generator", [
    AgentMenuEntry(code="GC", description="Generate project context file", skill="context_generator"),
    AgentMenuEntry(code="DI", description="Discover repo conventions", skill="context_generator"),
])
