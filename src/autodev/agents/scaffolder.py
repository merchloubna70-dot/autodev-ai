"""Scaffolder — generate language-appropriate project skeletons."""
from __future__ import annotations

from pathlib import Path

from ..executors.patch_executor import FilePatch, PatchExecutor
from ..schemas import Language, PipelineMode, ScaffoldPlan
from ._crewai_bridge import make_agent
from ._scaffold_verification import ScaffoldVerification


PY_PYPROJECT_TEMPLATE = """[build-system]
requires = ["hatchling>=1.21"]
build-backend = "hatchling.build"

[project]
name = "{name}"
version = "0.1.0"
description = "{name} scaffolded by autodev"
requires-python = ">=3.10"
dependencies = []

[project.scripts]
{pkg} = "{pkg}.cli:main"

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.hatch.build.targets.wheel]
packages = ["src/{pkg}"]

[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["tests"]
pythonpath = ["src"]
"""

PY_INIT_TEMPLATE = '''\
"""{pkg} package."""
from .cli import main

__all__ = ["main"]
'''

PY_CLI_TEMPLATE = '''\
"""{pkg} CLI entrypoint."""
from __future__ import annotations
import sys


def main(argv: list[str] | None = None) -> int:
    """Entry point. Implement me."""
    raise NotImplementedError("{pkg} CLI is not yet implemented")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
'''

PY_CORE_TEMPLATE = '''\
"""{pkg} core logic — implement here, not in __init__.py."""
from __future__ import annotations
'''

PY_SMOKE_TEST_TEMPLATE = '''\
"""Smoke import test for {pkg}."""
from __future__ import annotations


def test_cli_importable() -> None:
    from {pkg}.cli import main  # noqa: F401
    assert callable(main)
'''


class ScaffolderAgent:
    def __init__(self) -> None:
        self.agent = make_agent(
            role="Scaffolder",
            goal="Generate idiomatic language scaffolds for the target project.",
            backstory="An ex-toolsmith who knows pyproject, Cargo, and tsconfig by heart.",
        )

    def plan(self, *, project_name: str, languages: list[Language]) -> ScaffoldPlan:
        files: list[str] = []
        dirs: list[str] = []
        for lang in languages:
            if lang == Language.PYTHON:
                pkg = project_name.replace("-", "_").replace(".", "_")
                files += [
                    "pyproject.toml",
                    "README.md",
                    f"src/{pkg}/__init__.py",
                    f"src/{pkg}/cli.py",
                    f"src/{pkg}/core.py",
                    "tests/__init__.py",
                    "tests/test_smoke.py",
                ]
                dirs += [f"src/{pkg}", "tests"]
            elif lang == Language.RUST:
                files += ["Cargo.toml", "src/lib.rs"]
                dirs += ["src", "tests"]
            elif lang == Language.TYPESCRIPT:
                files += ["package.json", "tsconfig.json", "src/index.ts"]
                dirs += ["src", "tests"]
        return ScaffoldPlan(project_name=project_name, languages=languages, files_to_create=files, directories_to_create=dirs)

    def apply(self, *, plan: ScaffoldPlan, repo_path: str, mode: PipelineMode) -> list[str]:
        patches: list[FilePatch] = []
        name = plan.project_name
        pkg = name.replace("-", "_").replace(".", "_")
        for f in plan.files_to_create:
            if f == "pyproject.toml":
                patches.append(FilePatch(path=f, new_content=PY_PYPROJECT_TEMPLATE.format(name=name, pkg=pkg), create_only=True))
            elif f == "README.md":
                patches.append(FilePatch(path=f, new_content=f"# {name}\n\nScaffolded by autodev.\n", create_only=True))
            elif f == f"src/{pkg}/__init__.py":
                patches.append(FilePatch(path=f, new_content=PY_INIT_TEMPLATE.format(pkg=pkg), create_only=True))
            elif f.endswith("__init__.py"):
                patches.append(FilePatch(path=f, new_content="", create_only=True))
            elif f == f"src/{pkg}/cli.py":
                patches.append(FilePatch(path=f, new_content=PY_CLI_TEMPLATE.format(pkg=pkg), create_only=True))
            elif f == f"src/{pkg}/core.py":
                patches.append(FilePatch(path=f, new_content=PY_CORE_TEMPLATE.format(pkg=pkg), create_only=True))
            elif f == "tests/test_smoke.py":
                patches.append(FilePatch(path=f, new_content=PY_SMOKE_TEST_TEMPLATE.format(pkg=pkg), create_only=True))
            elif f == "Cargo.toml":
                content = (
                    f'[package]\nname = "{name}"\nversion = "0.1.0"\nedition = "2021"\n'
                    f"\n[lib]\npath = \"src/lib.rs\"\n"
                )
                patches.append(FilePatch(path=f, new_content=content, create_only=True))
            elif f == "src/lib.rs":
                patches.append(FilePatch(path=f, new_content="pub fn version() -> &'static str { \"0.1.0\" }\n", create_only=True))
            elif f == "package.json":
                content = (
                    "{\n"
                    f'  "name": "{name}",\n'
                    '  "version": "0.1.0",\n'
                    '  "type": "module",\n'
                    '  "scripts": {\n'
                    '    "lint": "echo lint",\n'
                    '    "typecheck": "echo typecheck",\n'
                    '    "test": "echo test",\n'
                    '    "build": "echo build"\n'
                    "  }\n"
                    "}\n"
                )
                patches.append(FilePatch(path=f, new_content=content, create_only=True))
            elif f == "tsconfig.json":
                patches.append(FilePatch(path=f, new_content='{ "compilerOptions": { "target": "ES2022", "module": "ESNext", "strict": true, "outDir": "dist" }, "include": ["src"] }\n', create_only=True))
            elif f == "src/index.ts":
                patches.append(FilePatch(path=f, new_content="export const version = '0.1.0';\n", create_only=True))
            else:
                patches.append(FilePatch(path=f, new_content="", create_only=True))
        applier = PatchExecutor(repo_path, mode=mode)
        # ensure directories
        if mode == PipelineMode.APPLY:
            for d in plan.directories_to_create:
                Path(repo_path, d).mkdir(parents=True, exist_ok=True)
        return applier.apply(patches)

    def verify(self, repo_path: str, plan: ScaffoldPlan) -> ScaffoldVerification:
        """Check which files from the scaffold plan are already present in *repo_path*.

        Returns a :class:`ScaffoldVerification` with present/missing breakdowns.
        The ``dropped_task_ids`` / ``survived_task_ids`` lists are intentionally
        left empty here — they are filled in by
        :meth:`~autodev.flows.project_delivery_flow.ProjectDeliveryFlow.run`
        after correlating scaffold files with actual M1 tasks.
        """
        root = Path(repo_path)
        present: list[str] = []
        missing: list[str] = []
        for f in plan.files_to_create:
            if (root / f).exists():
                present.append(f)
            else:
                missing.append(f)
        return ScaffoldVerification(
            present_files=present,
            missing_files=missing,
            dropped_task_ids=[],
            survived_task_ids=[],
        )
