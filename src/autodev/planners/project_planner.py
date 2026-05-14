"""High-level project planner: PRD + scan -> architecture + milestone targets."""
from __future__ import annotations

from ..schemas import (
    PRD,
    ApiContract,
    ArchitectureSpec,
    DataModel,
    DependencyGraph,
    Language,
    ModuleSpec,
    RepoScanResult,
)


class ProjectPlanner:
    def plan_architecture(
        self,
        *,
        prd: PRD,
        scan: RepoScanResult,
        languages: list[Language],
    ) -> ArchitectureSpec:
        modules: list[ModuleSpec] = []
        # Always include a core domain module per language
        for lang in languages:
            mod_name = f"core_{lang.value}"
            modules.append(ModuleSpec(
                name=mod_name,
                purpose=f"Core domain for {lang.value}",
                language=lang,
                paths=[],
                depends_on=[],
                public_interfaces=[],
            ))
        # Cross-language integration module if multi-language
        if len([lang for lang in languages if lang != Language.UNKNOWN]) >= 2:
            modules.append(ModuleSpec(
                name="integration",
                purpose="Cross-language contracts, codegen, shared schemas",
                language=Language.MIXED,
                paths=["integration/"],
                depends_on=[m.name for m in modules],
                public_interfaces=[],
            ))
        api = ApiContract(version="0.1.0", endpoints=[], notes=["derived from PRD functional requirements"])
        data = DataModel(entities=[], notes=[f"Functional requirements: {len(prd.functional_requirements)}"])
        graph = DependencyGraph(
            nodes=[m.name for m in modules],
            edges=[(d, m.name) for m in modules for d in m.depends_on],
        )
        overview = (
            f"Architecture for {prd.product_name} targeting languages: "
            f"{', '.join(lang.value for lang in languages)}."
        )
        return ArchitectureSpec(
            title=f"Architecture: {prd.product_name}",
            overview=overview,
            modules=modules,
            api_contract=api,
            data_model=data,
            dependency_graph=graph,
            decisions=[
                "Use multi-language layout per detected language; integration module bridges them.",
                "All cross-language schema work routes to Claude Code; small patches to Codex.",
            ],
        )
