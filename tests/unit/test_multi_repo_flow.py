"""Unit tests for MultiRepoFlow.

Tests cover:
1. YAML parsing — happy path (group_name + repos with languages, brief_file)
2. Missing required 'path' field raises a clean ValueError
3. Non-existent config file raises FileNotFoundError from parse_multi_repo_config
4. 2-repo dry-run completes (both succeed / both produce manifest.json)
5. Per-repo artifact dirs are created under group_root
6. Aggregate summary.json is written with correct counts
7. Missing repo path raises clean error (not a Python traceback crash) and marks status=error
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from autodev.config import FactoryConfig
from autodev.flows.multi_repo_flow import (
    MultiRepoConfig,
    MultiRepoFlow,
    RepoSpec,
    _parse_languages,
    _slugify,
    parse_multi_repo_config,
)
from autodev.schemas import Language, PipelineMode

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_yaml(tmp_path: Path, content: str, name: str = "multi.yaml") -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def _make_repo(tmp_path: Path, name: str) -> Path:
    """Create a minimal repo directory."""
    repo = tmp_path / name
    repo.mkdir(parents=True, exist_ok=True)
    return repo


def _make_brief(tmp_path: Path, name: str, text: str = "Build a thing.") -> Path:
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _dry_run_config() -> FactoryConfig:
    cfg = FactoryConfig()
    cfg.allow_mock_executor = True
    return cfg


# ---------------------------------------------------------------------------
# 1. YAML parsing — happy path
# ---------------------------------------------------------------------------


class TestYamlParsing:
    def test_parses_group_name_and_repos(self, tmp_path):
        """parse_multi_repo_config reads group_name and builds RepoSpec list."""
        repo_a = _make_repo(tmp_path, "api-service")
        brief_a = _make_brief(tmp_path, "briefs/api.md", "API brief.")
        repo_b = _make_repo(tmp_path, "web-frontend")
        brief_b = _make_brief(tmp_path, "briefs/web.md", "Web brief.")

        yaml_content = f"""
group_name: test-group
repos:
  - path: {repo_a}
    brief_file: {brief_a}
    languages: [python]
  - path: {repo_b}
    brief_file: {brief_b}
    languages: [typescript]
"""
        cfg_file = _write_yaml(tmp_path, yaml_content)
        result = parse_multi_repo_config(cfg_file)

        assert result.group_name == "test-group"
        assert len(result.repos) == 2
        assert result.repos[0].languages == [Language.PYTHON]
        assert result.repos[1].languages == [Language.TYPESCRIPT]
        assert result.repos[0].brief_text == "API brief."
        assert result.repos[1].brief_text == "Web brief."

    def test_parses_relative_paths(self, tmp_path):
        """Relative paths in YAML are resolved relative to the config file."""
        repo_dir = _make_repo(tmp_path, "myrepo")
        _make_brief(tmp_path, "brief.md", "A brief.")

        yaml_content = """
group_name: rel-test
repos:
  - path: myrepo
    brief_file: brief.md
    languages: [python]
"""
        cfg_file = _write_yaml(tmp_path, yaml_content)
        result = parse_multi_repo_config(cfg_file)

        assert len(result.repos) == 1
        assert Path(result.repos[0].path) == repo_dir.resolve()
        assert result.repos[0].brief_text == "A brief."

    def test_defaults_language_to_python_when_omitted(self, tmp_path):
        """When 'languages' is absent, Language.PYTHON is used."""
        repo = _make_repo(tmp_path, "no-lang-repo")
        yaml_content = f"""
group_name: defaultlang
repos:
  - path: {repo}
"""
        cfg_file = _write_yaml(tmp_path, yaml_content)
        result = parse_multi_repo_config(cfg_file)

        assert result.repos[0].languages == [Language.PYTHON]

    def test_no_brief_file_is_ok(self, tmp_path):
        """Repos without brief_file are accepted (brief_text stays None)."""
        repo = _make_repo(tmp_path, "nobrief")
        yaml_content = f"""
group_name: nobrief-group
repos:
  - path: {repo}
    languages: [python]
"""
        cfg_file = _write_yaml(tmp_path, yaml_content)
        result = parse_multi_repo_config(cfg_file)

        assert result.repos[0].brief_text is None
        assert result.repos[0].brief_file is None


# ---------------------------------------------------------------------------
# 2. Missing 'path' field raises clean ValueError
# ---------------------------------------------------------------------------


class TestMissingPathRaisesError:
    def test_missing_path_raises_value_error(self, tmp_path):
        """A repo entry without 'path' raises ValueError with a helpful message."""
        yaml_content = """
group_name: bad-group
repos:
  - brief_file: some_file.md
    languages: [python]
"""
        cfg_file = _write_yaml(tmp_path, yaml_content)
        with pytest.raises(ValueError, match="missing required 'path'"):
            parse_multi_repo_config(cfg_file)

    def test_missing_repos_list_raises_value_error(self, tmp_path):
        """A config with no repos list raises ValueError."""
        yaml_content = "group_name: empty\n"
        cfg_file = _write_yaml(tmp_path, yaml_content)
        with pytest.raises(ValueError, match="'repos' list"):
            parse_multi_repo_config(cfg_file)

    def test_nonexistent_config_raises_file_not_found(self, tmp_path):
        """parse_multi_repo_config raises FileNotFoundError for missing config."""
        with pytest.raises(FileNotFoundError):
            parse_multi_repo_config(tmp_path / "does_not_exist.yaml")


# ---------------------------------------------------------------------------
# 3. 2-repo dry-run completes
# ---------------------------------------------------------------------------


class TestTwoRepoDryRun:
    def test_two_repo_dry_run_completes(self, tmp_path):
        """MultiRepoFlow runs two repos and returns a summary with 2 results."""
        repo_a = _make_repo(tmp_path, "repo-a")
        repo_b = _make_repo(tmp_path, "repo-b")

        multi_cfg = MultiRepoConfig(
            group_name="two-repo-test",
            repos=[
                RepoSpec(path=str(repo_a), brief_text="Service A brief.", languages=[Language.PYTHON]),
                RepoSpec(path=str(repo_b), brief_text="Service B brief.", languages=[Language.PYTHON]),
            ],
        )

        output_base = tmp_path / "multi-runs"
        flow = MultiRepoFlow(
            config=_dry_run_config(),
            mode=PipelineMode.DRY_RUN,
            output_base=output_base,
        )
        summary = flow.run(multi_cfg)

        assert summary.total == 2
        assert len(summary.results) == 2
        # Both repos ran without a hard crash
        for r in summary.results:
            assert r["status"] in ("success", "failed")

    def test_both_repos_produce_manifest_json(self, tmp_path):
        """Each repo produces a manifest.json inside its artifact subdirectory."""
        repo_a = _make_repo(tmp_path, "svc-a")
        repo_b = _make_repo(tmp_path, "svc-b")

        multi_cfg = MultiRepoConfig(
            group_name="manifest-test",
            repos=[
                RepoSpec(path=str(repo_a), brief_text="A.", languages=[Language.PYTHON]),
                RepoSpec(path=str(repo_b), brief_text="B.", languages=[Language.PYTHON]),
            ],
        )

        output_base = tmp_path / "multi-runs"
        flow = MultiRepoFlow(
            config=_dry_run_config(),
            mode=PipelineMode.DRY_RUN,
            output_base=output_base,
        )
        summary = flow.run(multi_cfg)

        group_root = Path(summary.artifact_root)
        manifests = list(group_root.rglob("manifest.json"))
        assert len(manifests) == 2, (
            f"Expected 2 manifest.json files, found {len(manifests)}: {manifests}"
        )


# ---------------------------------------------------------------------------
# 4. Per-repo artifact dirs created
# ---------------------------------------------------------------------------


class TestPerRepoArtifactDirs:
    def test_per_repo_subdirs_created(self, tmp_path):
        """Each repo gets its own subdir under the group_id directory."""
        repo_a = _make_repo(tmp_path, "alpha")
        repo_b = _make_repo(tmp_path, "beta")

        multi_cfg = MultiRepoConfig(
            group_name="artifact-dir-test",
            repos=[
                RepoSpec(path=str(repo_a), brief_text="Alpha.", languages=[Language.PYTHON]),
                RepoSpec(path=str(repo_b), brief_text="Beta.", languages=[Language.PYTHON]),
            ],
        )

        output_base = tmp_path / "multi-runs"
        flow = MultiRepoFlow(
            config=_dry_run_config(),
            mode=PipelineMode.DRY_RUN,
            output_base=output_base,
        )
        summary = flow.run(multi_cfg)

        group_root = Path(summary.artifact_root)
        subdirs = [d for d in group_root.iterdir() if d.is_dir()]
        # One subdir per repo
        assert len(subdirs) == 2, f"Expected 2 subdirs, got: {subdirs}"

    def test_artifact_dir_paths_in_results(self, tmp_path):
        """Each result dict has an 'artifact_dir' key pointing to an existing dir."""
        repo = _make_repo(tmp_path, "single-repo")

        multi_cfg = MultiRepoConfig(
            group_name="single-test",
            repos=[
                RepoSpec(path=str(repo), brief_text="X.", languages=[Language.PYTHON]),
            ],
        )

        output_base = tmp_path / "multi-runs"
        flow = MultiRepoFlow(
            config=_dry_run_config(),
            mode=PipelineMode.DRY_RUN,
            output_base=output_base,
        )
        summary = flow.run(multi_cfg)

        for r in summary.results:
            artifact_dir = Path(r["artifact_dir"])
            assert artifact_dir.exists(), f"artifact_dir missing: {artifact_dir}"
            assert artifact_dir.is_dir()


# ---------------------------------------------------------------------------
# 5. Aggregate summary.json written
# ---------------------------------------------------------------------------


class TestAggregateSummaryWritten:
    def test_summary_json_written(self, tmp_path):
        """summary.json is created in the group root after run()."""
        repo = _make_repo(tmp_path, "summary-repo")
        multi_cfg = MultiRepoConfig(
            group_name="summary-test",
            repos=[
                RepoSpec(path=str(repo), brief_text="Summary brief.", languages=[Language.PYTHON]),
            ],
        )

        output_base = tmp_path / "multi-runs"
        flow = MultiRepoFlow(
            config=_dry_run_config(),
            mode=PipelineMode.DRY_RUN,
            output_base=output_base,
        )
        summary = flow.run(multi_cfg)

        summary_file = Path(summary.artifact_root) / "summary.json"
        assert summary_file.exists(), "summary.json was not created"

        data = json.loads(summary_file.read_text(encoding="utf-8"))
        assert data["group_name"] == "summary-test"
        assert data["total"] == 1
        assert "group_id" in data
        assert "started_at" in data
        assert "finished_at" in data
        assert isinstance(data["results"], list)

    def test_summary_counts_match(self, tmp_path):
        """succeeded + failed == total in summary."""
        repos = [_make_repo(tmp_path, f"r{i}") for i in range(3)]
        multi_cfg = MultiRepoConfig(
            group_name="count-test",
            repos=[
                RepoSpec(path=str(r), brief_text="Brief.", languages=[Language.PYTHON])
                for r in repos
            ],
        )

        output_base = tmp_path / "multi-runs"
        flow = MultiRepoFlow(
            config=_dry_run_config(),
            mode=PipelineMode.DRY_RUN,
            output_base=output_base,
        )
        summary = flow.run(multi_cfg)

        assert summary.total == 3
        assert summary.succeeded + summary.failed == summary.total


# ---------------------------------------------------------------------------
# 6. Missing repo path is handled gracefully (status=error, no crash)
# ---------------------------------------------------------------------------


class TestMissingRepoPathHandled:
    def test_missing_repo_path_marks_status_error(self, tmp_path):
        """If a repo path does not exist, the result is status='error' (no Python crash)."""
        multi_cfg = MultiRepoConfig(
            group_name="error-test",
            repos=[
                RepoSpec(
                    path=str(tmp_path / "does-not-exist"),
                    brief_text="Brief.",
                    languages=[Language.PYTHON],
                ),
            ],
        )

        output_base = tmp_path / "multi-runs"
        flow = MultiRepoFlow(
            config=_dry_run_config(),
            mode=PipelineMode.DRY_RUN,
            output_base=output_base,
        )
        summary = flow.run(multi_cfg)

        assert summary.total == 1
        assert summary.succeeded == 0
        assert summary.failed == 1
        result = summary.results[0]
        assert result["status"] == "error"
        assert len(result["errors"]) > 0


# ---------------------------------------------------------------------------
# 7. Utility helpers
# ---------------------------------------------------------------------------


class TestUtilityHelpers:
    def test_parse_languages_list(self):
        langs = _parse_languages(["python", "typescript"])
        assert langs == [Language.PYTHON, Language.TYPESCRIPT]

    def test_parse_languages_string(self):
        langs = _parse_languages("rust")
        assert langs == [Language.RUST]

    def test_parse_languages_none_defaults_python(self):
        langs = _parse_languages(None)
        assert langs == [Language.PYTHON]

    def test_parse_languages_unknown_value(self):
        langs = _parse_languages(["unknownlang"])
        assert langs == [Language.UNKNOWN]

    def test_slugify_basic(self):
        assert _slugify("API Service") == "api-service"

    def test_slugify_special_chars(self):
        assert _slugify("my/repo.name") == "my-repo-name"


# ---------------------------------------------------------------------------
# 8. CLI surface — deliver-multi --help
# ---------------------------------------------------------------------------


class TestDeliverMultiCliHelp:
    def test_deliver_multi_help(self):
        """deliver-multi subcommand is registered and --help works."""
        import re

        from typer.testing import CliRunner

        from autodev.cli import app

        _ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mK]")
        runner = CliRunner()
        result = runner.invoke(app, ["deliver-multi", "--help"])
        out = _ANSI_RE.sub("", result.output)
        assert result.exit_code == 0, f"deliver-multi --help exited {result.exit_code}\n{out}"
        assert "Usage:" in out
