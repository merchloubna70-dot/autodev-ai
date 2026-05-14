"""Tests for the autodev skill_packs module.

Coverage
--------
- Registry loads all 5 packs
- Each pack has required attrs (name, description, brief_template,
  prd_template, milestones_template, recommended_executor)
- ``get_skill_pack`` returns the correct type
- ``get_skill_pack`` raises ValueError for unknown names
- ``--skill-pack`` flag appears in ``deliver-project --help``
- ``--skill-pack`` with an invalid name exits non-zero
- ``render_brief`` substitutes ``{{project_name}}`` and extra kwargs
"""
from __future__ import annotations

import re

import pytest
from typer.testing import CliRunner

from autodev.cli import app
from autodev.skill_packs import SKILL_PACKS, get_skill_pack
from autodev.skill_packs.base import SkillPack

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mK]")


def _strip(text: str) -> str:
    return _ANSI_RE.sub("", text)


runner = CliRunner()

_EXPECTED_SLUGS = {
    "rust-binary",
    "fastapi-service",
    "cli-tool",
    "nextjs-app",
    "python-package",
}

# ---------------------------------------------------------------------------
# 1. Registry loads all 5 packs
# ---------------------------------------------------------------------------


def test_registry_contains_all_five_packs() -> None:
    assert _EXPECTED_SLUGS == set(SKILL_PACKS.keys()), (
        f"Expected slugs {_EXPECTED_SLUGS!r}; got {set(SKILL_PACKS.keys())!r}"
    )


# ---------------------------------------------------------------------------
# 2. Each pack instantiates and has all required attributes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("slug", sorted(_EXPECTED_SLUGS))
def test_each_pack_has_required_attrs(slug: str) -> None:
    pack = get_skill_pack(slug)
    assert isinstance(pack, SkillPack), f"{slug}: instance is not a SkillPack"
    # name
    assert isinstance(pack.name, str) and pack.name, f"{slug}: name must be a non-empty str"
    assert pack.name == slug, f"{slug}: pack.name {pack.name!r} != slug {slug!r}"
    # description
    assert isinstance(pack.description, str) and pack.description, \
        f"{slug}: description must be a non-empty str"
    # brief_template
    assert isinstance(pack.brief_template, str) and pack.brief_template, \
        f"{slug}: brief_template must be a non-empty str"
    # prd_template
    assert isinstance(pack.prd_template, str) and pack.prd_template, \
        f"{slug}: prd_template must be a non-empty str"
    # milestones_template
    assert isinstance(pack.milestones_template, list), \
        f"{slug}: milestones_template must be a list"
    assert len(pack.milestones_template) >= 1, \
        f"{slug}: milestones_template must have at least one entry"
    for m in pack.milestones_template:
        assert isinstance(m, str) and m, f"{slug}: milestone entry must be non-empty str"
    # recommended_executor
    assert isinstance(pack.recommended_executor, str) and pack.recommended_executor, \
        f"{slug}: recommended_executor must be a non-empty str"
    # recommended_extras (optional but must be list)
    assert isinstance(pack.recommended_extras, list), \
        f"{slug}: recommended_extras must be a list"


# ---------------------------------------------------------------------------
# 3. get_skill_pack returns fresh instances
# ---------------------------------------------------------------------------


def test_get_skill_pack_returns_correct_type() -> None:
    from autodev.skill_packs.rust_binary import RustBinaryPack

    pack = get_skill_pack("rust-binary")
    assert isinstance(pack, RustBinaryPack)


def test_get_skill_pack_different_calls_return_independent_instances() -> None:
    a = get_skill_pack("fastapi-service")
    b = get_skill_pack("fastapi-service")
    assert a is not b  # separate instances, not singletons


# ---------------------------------------------------------------------------
# 4. get_skill_pack raises ValueError for unknown name
# ---------------------------------------------------------------------------


def test_get_skill_pack_invalid_name_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown skill pack"):
        get_skill_pack("does-not-exist")


def test_get_skill_pack_invalid_name_error_message_lists_valid_packs() -> None:
    with pytest.raises(ValueError) as exc_info:
        get_skill_pack("nonexistent-pack")
    msg = str(exc_info.value)
    for slug in _EXPECTED_SLUGS:
        assert slug in msg, f"Expected slug {slug!r} in error message; got: {msg!r}"


# ---------------------------------------------------------------------------
# 5. --skill-pack flag appears in deliver-project --help
# ---------------------------------------------------------------------------


def test_deliver_project_help_shows_skill_pack_flag() -> None:
    result = runner.invoke(app, ["deliver-project", "--help"])
    out = _strip(result.output)
    assert result.exit_code == 0, f"deliver-project --help exited {result.exit_code}:\n{out}"
    assert "--skill-pack" in out, (
        f"--skill-pack not found in deliver-project --help output:\n{out}"
    )


# ---------------------------------------------------------------------------
# 6. --skill-pack with invalid name exits 1
# ---------------------------------------------------------------------------


def test_deliver_project_invalid_skill_pack_exits_nonzero() -> None:
    result = runner.invoke(
        app,
        ["deliver-project", "--skill-pack", "no-such-pack"],
    )
    assert result.exit_code != 0, (
        "Expected non-zero exit for invalid --skill-pack; got 0"
    )
    out = _strip(result.output + (result.stderr if hasattr(result, "stderr") and result.stderr else ""))
    # The error message should mention the invalid pack name
    assert "no-such-pack" in out or result.exit_code == 1


# ---------------------------------------------------------------------------
# 7. render_brief substitutes project_name
# ---------------------------------------------------------------------------


def test_render_brief_substitutes_project_name() -> None:
    pack = get_skill_pack("python-package")
    rendered = pack.render_brief(project_name="mylib")
    assert "mylib" in rendered
    assert "{{project_name}}" not in rendered


def test_render_brief_substitutes_extra_kwargs() -> None:
    pack = get_skill_pack("rust-binary")
    rendered = pack.render_brief(project_name="mycli", summary="parses log files")
    assert "mycli" in rendered
    assert "parses log files" in rendered


def test_render_brief_leaves_unknown_placeholders() -> None:
    pack = get_skill_pack("cli-tool")
    rendered = pack.render_brief(project_name="mytool")
    # {{feature_1}} etc. should remain for the user to fill
    assert "{{feature_1}}" in rendered
