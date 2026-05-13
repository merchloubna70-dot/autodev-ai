"""Scaffolder — generate language-appropriate project skeletons."""
from __future__ import annotations

from pathlib import Path

from ..executors.patch_executor import FilePatch, PatchExecutor
from ..schemas import Language, PipelineMode, ScaffoldPlan
from ._crewai_bridge import make_agent


PY_PYPROJECT_TEMPLATE = """[build-system]
requires = ["hatchling>=1.21"]
build-backend = "hatchling.build"

[project]
name = "{name}"
version = "0.1.0"
description = "{name} scaffolded by crewai-multicli-software-factory"
requires-python = ">=3.10"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.hatch.build.targets.wheel]
packages = ["src/{pkg}"]

[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["tests"]
pythonpath = ["src"]
"""


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
                pkg = project_name.replace("-", "_")
                files += ["pyproject.toml", "README.md", f"src/{pkg}/__init__.py", "tests/__init__.py"]
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
        pkg = name.replace("-", "_")
        for f in plan.files_to_create:
            if f == "pyproject.toml":
                patches.append(FilePatch(path=f, new_content=PY_PYPROJECT_TEMPLATE.format(name=name, pkg=pkg), create_only=True))
            elif f == "README.md":
                patches.append(FilePatch(path=f, new_content=f"# {name}\n\nScaffolded by crewai-multicli-software-factory.\n", create_only=True))
            elif f.endswith("__init__.py"):
                patches.append(FilePatch(path=f, new_content="", create_only=True))
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
