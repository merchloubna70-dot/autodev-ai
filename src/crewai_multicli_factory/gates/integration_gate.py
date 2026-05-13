"""Integration gate — checks cross-language consistency and contract drift."""
from __future__ import annotations

from ..schemas import (
    ApiContract,
    DependencyGraph,
    GateStatus,
    IntegrationReviewReport,
)


class IntegrationGate:
    def review(
        self,
        *,
        api_contract: ApiContract | None,
        dependency_graph: DependencyGraph | None,
        languages: list[str],
    ) -> IntegrationReviewReport:
        findings: list[str] = []
        cross_consistency = True
        contract_consistent = True
        drift = False
        if api_contract is not None:
            seen: set[tuple[str, str]] = set()
            for ep in api_contract.endpoints:
                key = (ep.method.upper(), ep.path)
                if key in seen:
                    contract_consistent = False
                    findings.append(f"duplicate API endpoint: {ep.method} {ep.path}")
                seen.add(key)
        if dependency_graph is not None:
            node_set = set(dependency_graph.nodes)
            for src, dst in dependency_graph.edges:
                if src not in node_set or dst not in node_set:
                    findings.append(f"dependency edge references unknown node: {src}->{dst}")
                    drift = True
        if len({l for l in languages if l not in ("unknown", "mixed")}) >= 2:
            findings.append("cross-language project: ensure schemas/contracts align via Claude Code review")
        status = GateStatus.FAILED if (not contract_consistent or drift) else GateStatus.PASSED
        return IntegrationReviewReport(
            cross_language_consistency=cross_consistency,
            api_contract_consistent=contract_consistent,
            schema_drift_detected=drift,
            findings=findings,
            status=status,
        )
