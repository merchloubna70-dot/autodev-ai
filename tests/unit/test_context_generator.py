"""Unit tests for ContextGeneratorAgent (BMAD-11).

All tests are pure filesystem / in-memory; no LLM calls.
FACTORY_FORCE_MOCK is not needed — the agent is deterministic by design.
"""
from __future__ import annotations

import json
from pathlib import Path

from autodev.agents.context_generator import ContextGeneratorAgent
from autodev.schemas import ContextRule, DiscoveryReport, ProjectContextDraft

# ---------------------------------------------------------------------------
# Step 1: discover
# ---------------------------------------------------------------------------


class TestDiscover:
    def test_discovers_pyproject_and_claude_md(self, tmp_path: Path) -> None:
        """discover() finds pyproject.toml (Python) and CLAUDE.md convention file."""
        (tmp_path / "pyproject.toml").write_text(
            "[tool.ruff]\nline-length = 88\n[tool.pytest.ini_options]\n",
            encoding="utf-8",
        )
        (tmp_path / "CLAUDE.md").write_text("# Agent rules\nAlways add types.\n", encoding="utf-8")

        agent = ContextGeneratorAgent()
        report = agent.discover(tmp_path)

        assert "python" in report.languages_detected
        assert "CLAUDE.md" in report.existing_conventions_files
        assert "ruff" in report.lint_tools
        assert "pytest" in report.test_frameworks

    def test_discovers_uv_lock(self, tmp_path: Path) -> None:
        """detect_package_manager returns 'uv' when uv.lock is present."""
        (tmp_path / "uv.lock").write_text("# lockfile\n", encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")

        agent = ContextGeneratorAgent()
        report = agent.discover(tmp_path)

        assert report.package_manager == "uv"

    def test_discovers_pre_commit_hooks(self, tmp_path: Path) -> None:
        """Pre-commit hooks are extracted from .pre-commit-config.yaml."""
        (tmp_path / ".pre-commit-config.yaml").write_text(
            "repos:\n- repo: https://github.com/pre-commit/pre-commit-hooks\n  hooks:\n  - id: trailing-whitespace\n  - id: end-of-file-fixer\n",
            encoding="utf-8",
        )
        agent = ContextGeneratorAgent()
        report = agent.discover(tmp_path)

        assert "trailing-whitespace" in report.pre_commit_hooks
        assert "end-of-file-fixer" in report.pre_commit_hooks

    def test_discovers_conventional_commits_via_commitlint(self, tmp_path: Path) -> None:
        """Conventional commit style is detected via .commitlintrc file."""
        (tmp_path / ".commitlintrc").write_text(
            "{'extends': ['@commitlint/config-conventional']}\n",
            encoding="utf-8",
        )
        agent = ContextGeneratorAgent()
        report = agent.discover(tmp_path)

        assert report.commit_style == "conventional"

    def test_empty_repo_returns_defaults(self, tmp_path: Path) -> None:
        """discover() on empty dir returns sensible defaults without crashing."""
        agent = ContextGeneratorAgent()
        report = agent.discover(tmp_path)

        assert isinstance(report.languages_detected, list)
        assert isinstance(report.lint_tools, list)
        assert isinstance(report.test_frameworks, list)
        assert report.existing_conventions_files == []


# ---------------------------------------------------------------------------
# Step 2: synthesize
# ---------------------------------------------------------------------------


class TestSynthesize:
    def _discovery(self, **kwargs) -> DiscoveryReport:
        defaults = dict(
            languages_detected=["python"],
            package_manager="uv",
            lint_tools=["ruff", "mypy"],
            test_frameworks=["pytest"],
            pre_commit_hooks=["trailing-whitespace"],
            commit_style="conventional",
            existing_conventions_files=["CLAUDE.md"],
            notes=[],
        )
        defaults.update(kwargs)
        return DiscoveryReport(**defaults)

    def test_synthesize_emits_at_least_three_rules(self) -> None:
        """synthesize() produces >= 3 rules from a typical Python project."""
        agent = ContextGeneratorAgent()
        discovery = self._discovery()
        draft = agent.synthesize(discovery)

        assert len(draft.rules) >= 3

    def test_synthesize_has_uv_rule(self) -> None:
        """A uv package manager triggers a 'use uv not pip' rule."""
        agent = ContextGeneratorAgent()
        discovery = self._discovery(package_manager="uv")
        draft = agent.synthesize(discovery)

        statements = [r.statement for r in draft.rules]
        assert any("uv" in s for s in statements)

    def test_synthesize_has_conventional_commit_rule(self) -> None:
        """Conventional commit style triggers a commit-style rule."""
        agent = ContextGeneratorAgent()
        discovery = self._discovery(commit_style="conventional")
        draft = agent.synthesize(discovery)

        cat_rules = [r for r in draft.rules if r.category == "commit-style"]
        assert len(cat_rules) >= 1
        assert any("Conventional" in r.statement for r in cat_rules)

    def test_synthesize_rule_ids_unique(self) -> None:
        """All generated rule_ids must be unique."""
        agent = ContextGeneratorAgent()
        discovery = self._discovery()
        draft = agent.synthesize(discovery)

        ids = [r.rule_id for r in draft.rules]
        assert len(ids) == len(set(ids))

    def test_synthesize_brief_adds_type_hint_rule(self) -> None:
        """Passing a brief mentioning type annotations adds a lang-idiom rule."""
        agent = ContextGeneratorAgent()
        discovery = self._discovery()
        draft = agent.synthesize(discovery, brief="All functions must have type annotations.")

        lang_rules = [r for r in draft.rules if r.category == "lang-idiom"]
        assert any("type" in r.statement.lower() for r in lang_rules)

    def test_synthesize_stores_discovery_on_draft(self) -> None:
        """The discovery report is preserved on the draft."""
        agent = ContextGeneratorAgent()
        discovery = self._discovery()
        draft = agent.synthesize(discovery)

        assert draft.discovery is discovery


# ---------------------------------------------------------------------------
# Step 3: commit_to_disk
# ---------------------------------------------------------------------------


class TestCommitToDisk:
    def _make_draft(self) -> ProjectContextDraft:
        rules = [
            ContextRule(
                rule_id="CTX-001",
                statement="Use uv not pip",
                rationale="uv.lock present",
                sources=["uv.lock"],
                category="build",
                severity_hint="must",
            ),
            ContextRule(
                rule_id="CTX-002",
                statement="Run ruff before commit",
                rationale="ruff config detected",
                sources=["pyproject.toml"],
                category="lint",
                severity_hint="must",
            ),
        ]
        discovery = DiscoveryReport(
            languages_detected=["python"],
            package_manager="uv",
            lint_tools=["ruff"],
        )
        return ProjectContextDraft(rules=rules, discovery=discovery)

    def test_commit_writes_md_file(self, tmp_path: Path) -> None:
        """commit_to_disk writes _autodev/project-context.md."""
        agent = ContextGeneratorAgent()
        draft = self._make_draft()
        agent.commit_to_disk(draft, tmp_path, product_name="TestApp")

        md_path = tmp_path / "_autodev" / "project-context.md"
        assert md_path.exists()
        content = md_path.read_text(encoding="utf-8")
        assert "TestApp" in content
        assert "CTX-001" in content
        assert "Use uv not pip" in content

    def test_commit_writes_json_file(self, tmp_path: Path) -> None:
        """commit_to_disk writes _autodev/project-context.json with valid JSON."""
        agent = ContextGeneratorAgent()
        draft = self._make_draft()
        agent.commit_to_disk(draft, tmp_path, product_name="TestApp")

        json_path = tmp_path / "_autodev" / "project-context.json"
        assert json_path.exists()
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["product_name"] == "TestApp"
        assert len(data["rules"]) == 2

    def test_commit_is_idempotent(self, tmp_path: Path) -> None:
        """Running commit_to_disk twice overwrites without error or duplication."""
        agent = ContextGeneratorAgent()
        draft = self._make_draft()
        agent.commit_to_disk(draft, tmp_path, product_name="TestApp")
        ctx2 = agent.commit_to_disk(draft, tmp_path, product_name="TestApp")

        # Only 2 rules — no duplication
        json_path = tmp_path / "_autodev" / "project-context.json"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert len(data["rules"]) == 2
        assert ctx2.file_path is not None

    def test_commit_sets_file_path_on_context(self, tmp_path: Path) -> None:
        """Returned ProjectContext has file_path pointing to the md file."""
        agent = ContextGeneratorAgent()
        draft = self._make_draft()
        ctx = agent.commit_to_disk(draft, tmp_path)

        assert ctx.file_path is not None
        assert ctx.file_path.endswith("project-context.md")


# ---------------------------------------------------------------------------
# Full .run() orchestration
# ---------------------------------------------------------------------------


class TestRun:
    def test_run_on_python_repo(self, tmp_path: Path) -> None:
        """Full .run() on a minimal Python repo writes both files and returns context."""
        (tmp_path / "pyproject.toml").write_text(
            "[tool.ruff]\n[tool.pytest.ini_options]\n",
            encoding="utf-8",
        )
        (tmp_path / "uv.lock").write_text("lock\n", encoding="utf-8")
        (tmp_path / "AGENTS.md").write_text("## Rules\nDo not foo.\n", encoding="utf-8")

        agent = ContextGeneratorAgent()
        ctx = agent.run(tmp_path, product_name="FullRunApp")

        assert ctx.product_name == "FullRunApp"
        assert len(ctx.rules) >= 1
        assert (tmp_path / "_autodev" / "project-context.md").exists()
        assert (tmp_path / "_autodev" / "project-context.json").exists()
