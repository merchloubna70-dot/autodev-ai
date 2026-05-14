"""Skill pack registry for autodev-x.

Usage
-----
    from autodev.skill_packs import SKILL_PACKS, get_skill_pack

    pack = get_skill_pack("rust-binary")
    brief = pack.render_brief(project_name="my-tool", summary="parses logs")
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .base import SkillPack
from .cli_tool import CliToolPack
from .fastapi_service import FastAPIServicePack
from .nextjs_app import NextjsAppPack
from .python_package import PythonPackagePack
from .rust_binary import RustBinaryPack

if TYPE_CHECKING:
    pass

# Registry mapping slug → pack class (not instance; instantiate on demand).
SKILL_PACKS: dict[str, type[SkillPack]] = {
    "rust-binary": RustBinaryPack,
    "fastapi-service": FastAPIServicePack,
    "cli-tool": CliToolPack,
    "nextjs-app": NextjsAppPack,
    "python-package": PythonPackagePack,
}


def get_skill_pack(name: str) -> SkillPack:
    """Return an instantiated :class:`SkillPack` for *name*.

    Raises ``ValueError`` with a helpful message if *name* is not a
    registered pack slug.
    """
    cls = SKILL_PACKS.get(name)
    if cls is None:
        valid = ", ".join(sorted(SKILL_PACKS))
        raise ValueError(
            f"Unknown skill pack {name!r}.  Valid packs: {valid}"
        )
    return cls()


__all__ = [
    "SKILL_PACKS",
    "CliToolPack",
    "FastAPIServicePack",
    "NextjsAppPack",
    "PythonPackagePack",
    "RustBinaryPack",
    "SkillPack",
    "get_skill_pack",
]
