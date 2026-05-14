"""Integration gate — checks cross-language consistency and contract drift."""
from __future__ import annotations

from ..schemas import (
    ApiContract,
    ContractDiffReport,
    DependencyGraph,
    GateStatus,
    IntegrationReviewReport,
)
from .contract_diff import diff_openapi_specs


class IntegrationGate:
    def review(
        self,
        *,
        api_contract: ApiContract | None,
        dependency_graph: DependencyGraph | None,
        languages: list[str],
        previous_api_contract: dict | None = None,
        current_api_contract: dict | None = None,
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
        if len({lang for lang in languages if lang not in ("unknown", "mixed")}) >= 2:
            findings.append("cross-language project: ensure schemas/contracts align via Claude Code review")

        # OpenAPI contract diff
        contract_diff_report: ContractDiffReport | None = None
        if previous_api_contract is not None and current_api_contract is not None:
            raw = diff_openapi_specs(previous_api_contract, current_api_contract)
            summary_parts: list[str] = []
            if raw["added_endpoints"]:
                summary_parts.append(f"added: {', '.join(raw['added_endpoints'])}")
            if raw["removed_endpoints"]:
                summary_parts.append(f"removed: {', '.join(raw['removed_endpoints'])}")
            if raw["changed_endpoints"]:
                changed_keys = [
                    f"{e['method']} {e['path']}" for e in raw["changed_endpoints"]
                ]
                summary_parts.append(f"changed: {', '.join(changed_keys)}")
            summary = "; ".join(summary_parts) if summary_parts else "no changes"
            contract_diff_report = ContractDiffReport(
                added_endpoints=raw["added_endpoints"],
                removed_endpoints=raw["removed_endpoints"],
                changed_endpoints=raw["changed_endpoints"],
                summary=summary,
            )
            if contract_diff_report.breaking_change:
                drift = True
                findings.append(
                    f"[ContractDiff] BREAKING CHANGE detected: {summary}"
                )
            else:
                findings.append(f"[ContractDiff] {summary}")

        status = GateStatus.FAILED if (not contract_consistent or drift) else GateStatus.PASSED
        return IntegrationReviewReport(
            cross_language_consistency=cross_consistency,
            api_contract_consistent=contract_consistent,
            schema_drift_detected=drift,
            findings=findings,
            status=status,
        )
