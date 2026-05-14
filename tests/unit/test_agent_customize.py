"""BMAD-18: Tests for AgentCustomizeLoader (4-layer customize.toml merge)."""
from __future__ import annotations

from pathlib import Path

import pytest

from autodev.agents._activation import AgentCustomizeLoader
from autodev.schemas import AgentCustomizeSnapshot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_toml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_customize_files_returns_empty(tmp_path: Path) -> None:
    """When no customize.toml files exist, merged dict should be empty."""
    loader = AgentCustomizeLoader("no_such_agent", repo_path=tmp_path)
    data, paths = loader.load()
    assert data == {}
    assert paths == []


def test_project_team_override(tmp_path: Path) -> None:
    """Project team layer should populate merged dict."""
    team_toml = tmp_path / ".autodev" / "agents" / "my_agent.toml"
    _write_toml(team_toml, 'temperature = 0.3\n[model]\nname = "gpt-4"\n')

    loader = AgentCustomizeLoader("my_agent", repo_path=tmp_path)
    data, paths = loader.load()

    assert data["temperature"] == pytest.approx(0.3)
    assert data["model"]["name"] == "gpt-4"
    assert str(team_toml) in paths


def test_user_override_wins_over_team(tmp_path: Path) -> None:
    """User project layer (layer d) should override team layer (layer c)."""
    team_toml = tmp_path / ".autodev" / "agents" / "agent_x.toml"
    _write_toml(team_toml, 'temperature = 0.5\n')

    user_toml = tmp_path / ".autodev" / "agents" / "agent_x.user.toml"
    _write_toml(user_toml, 'temperature = 0.1\n')

    loader = AgentCustomizeLoader("agent_x", repo_path=tmp_path)
    data, paths = loader.load()

    # user override (layer d) takes precedence
    assert data["temperature"] == pytest.approx(0.1)
    assert str(team_toml) in paths
    assert str(user_toml) in paths


def test_four_layer_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """All 4 layers should be merged in correct order (later wins)."""
    # (b) user-global: simulate by patching home
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    ug = fake_home / ".config" / "autodev" / "agents" / "layered.toml"
    _write_toml(ug, 'level = "user-global"\nbase_key = "from-ug"\n')

    # (c) project team
    pt = tmp_path / ".autodev" / "agents" / "layered.toml"
    _write_toml(pt, 'level = "project-team"\nteam_key = "team-val"\n')

    # (d) project user
    pu = tmp_path / ".autodev" / "agents" / "layered.user.toml"
    _write_toml(pu, 'level = "project-user"\nuser_key = "user-val"\n')

    loader = AgentCustomizeLoader("layered", repo_path=tmp_path)
    data, paths = loader.load()

    # layer d (project-user) is highest priority — level should be "project-user"
    assert data["level"] == "project-user"
    # lower layers contribute unique keys
    assert data["base_key"] == "from-ug"
    assert data["team_key"] == "team-val"
    assert data["user_key"] == "user-val"
    assert len(paths) == 3  # ug + team + user


def test_malformed_toml_gracefully_empty(tmp_path: Path) -> None:
    """A malformed TOML file should not raise; that layer should be silently skipped."""
    bad_toml = tmp_path / ".autodev" / "agents" / "bad_agent.toml"
    _write_toml(bad_toml, "this is not valid toml [\x00")

    loader = AgentCustomizeLoader("bad_agent", repo_path=tmp_path)
    # Should not raise
    data, paths = loader.load()
    # Malformed file is skipped → empty merge from that layer
    assert isinstance(data, dict)
    # The path should NOT be in loaded list (since load returned {})
    assert str(bad_toml) not in paths


def test_snapshot_method_returns_correct_type(tmp_path: Path) -> None:
    """snapshot() should return an AgentCustomizeSnapshot with correct agent_name."""
    loader = AgentCustomizeLoader("snap_test", repo_path=tmp_path)
    snap = loader.snapshot()
    assert isinstance(snap, AgentCustomizeSnapshot)
    assert snap.agent_name == "snap_test"
    assert snap.layers_loaded == []
    assert snap.effective_keys == []


def test_principles_and_facts_extracted(tmp_path: Path) -> None:
    """persistent_facts and principles keys should surface in snapshot."""
    toml_content = (
        'persistent_facts = ["fact one", "fact two"]\n'
        'principles = ["keep it simple"]\n'
    )
    team_toml = tmp_path / ".autodev" / "agents" / "factual.toml"
    _write_toml(team_toml, toml_content)

    loader = AgentCustomizeLoader("factual", repo_path=tmp_path)
    snap = loader.snapshot()
    assert snap.persistent_facts == ["fact one", "fact two"]
    assert snap.principles == ["keep it simple"]
