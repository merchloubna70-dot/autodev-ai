"""ExecutorRouter — routes ExecutionRequests to Codex / Claude / mocks
with explicit, audited selection reasons.

The selection policy is the heart of the multi-CLI factory:

  - small patches, scaffolds, tests, lint fixes -> Codex CLI
  - architecture, refactor, cross-language, security, release, docs -> Claude Code CLI
  - mocks only when allow_mock=True (or as fallback when both real CLIs missing)
  - fail-closed when no real CLI is available AND mocks are disallowed
"""
from __future__ import annotations

from dataclasses import dataclass

from ..config import FactoryConfig
from ..schemas import (
    ExecutionBackend,
    ExecutionRequest,
    ExecutionResult,
    ExecutorSelectionPolicy,
    Language,
    RiskLevel,
    TaskType,
)
from .base_executor import BaseExecutor
from .claude_code_executor import ClaudeCodeExecutor
from .codex_cli_executor import CodexCliExecutor
from .mock_claude_executor import MockClaudeExecutor
from .mock_codex_executor import MockCodexExecutor


@dataclass
class RouterDecision:
    selected_backend: ExecutionBackend
    candidate_backends: list[ExecutionBackend]
    reason: str
    fallback_used: bool
    mock_used: bool

    def to_json(self) -> dict:
        return {
            "selected_backend": self.selected_backend.value,
            "candidate_backends": [b.value for b in self.candidate_backends],
            "reason": self.reason,
            "fallback_used": self.fallback_used,
            "mock_used": self.mock_used,
        }


_RISK_RANK = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2, RiskLevel.CRITICAL: 3}


class ExecutorRouter:
    """Routes ExecutionRequests to the appropriate concrete executor."""

    def __init__(
        self,
        config: FactoryConfig | None = None,
        *,
        codex: BaseExecutor | None = None,
        claude: BaseExecutor | None = None,
        mock_codex: BaseExecutor | None = None,
        mock_claude: BaseExecutor | None = None,
        allow_mock: bool | None = None,
    ):
        self.config = config or FactoryConfig()
        self.policy: ExecutorSelectionPolicy = self.config.executor_policy
        self.codex = codex or CodexCliExecutor(self.config.codex)
        self.claude = claude or ClaudeCodeExecutor(self.config.claude_code)
        self.mock_codex = mock_codex or MockCodexExecutor()
        self.mock_claude = mock_claude or MockClaudeExecutor()
        self.allow_mock = self.config.allow_mock_executor if allow_mock is None else allow_mock

    # ------------------------------------------------------------------
    # Decision
    # ------------------------------------------------------------------

    def decide(self, request: ExecutionRequest, *, cross_language: bool = False) -> RouterDecision:
        # 1) Explicit user backend wins
        if request.backend == ExecutionBackend.CODEX:
            return self._maybe_mock(
                preferred=ExecutionBackend.CODEX,
                reason="user-selected: --executor codex",
            )
        if request.backend == ExecutionBackend.CLAUDE_CODE:
            return self._maybe_mock(
                preferred=ExecutionBackend.CLAUDE_CODE,
                reason="user-selected: --executor claude-code",
            )
        if request.backend == ExecutionBackend.MOCK_CODEX:
            return RouterDecision(
                ExecutionBackend.MOCK_CODEX,
                [ExecutionBackend.MOCK_CODEX],
                "user-selected mock codex",
                False,
                True,
            )
        if request.backend == ExecutionBackend.MOCK_CLAUDE:
            return RouterDecision(
                ExecutionBackend.MOCK_CLAUDE,
                [ExecutionBackend.MOCK_CLAUDE],
                "user-selected mock claude",
                False,
                True,
            )

        # 2) Auto-route based on task_type / risk / language / files
        preferred = self._auto_route(request, cross_language=cross_language)
        reason_parts: list[str] = []
        reason_parts.append(f"auto: task_type={request.task_type.value}")
        reason_parts.append(f"risk={request.risk_level.value}")
        reason_parts.append(f"language={request.language.value}")
        reason_parts.append(f"files={len(request.target_files) if hasattr(request,'target_files') else len(request.allowed_files)}")
        if cross_language:
            reason_parts.append("cross_language=true")
        return self._maybe_mock(preferred=preferred, reason="; ".join(reason_parts))

    def _auto_route(self, request: ExecutionRequest, *, cross_language: bool) -> ExecutionBackend:
        ttype = request.task_type

        # Policy override by task_type
        if ttype.value in self.policy.preferred_backend_by_task_type:
            backend = self.policy.preferred_backend_by_task_type[ttype.value]
            if backend in (ExecutionBackend.CODEX, ExecutionBackend.CLAUDE_CODE):
                return backend

        # Fixed mappings per spec
        if ttype in (TaskType.ARCHITECTURE, TaskType.REFACTOR, TaskType.SECURITY,
                     TaskType.RELEASE, TaskType.DOCS):
            return ExecutionBackend.CLAUDE_CODE

        if ttype == TaskType.SCAFFOLD:
            return ExecutionBackend.CODEX

        if ttype == TaskType.TEST:
            return ExecutionBackend.CODEX

        if ttype == TaskType.INTEGRATION:
            return ExecutionBackend.CLAUDE_CODE if cross_language else ExecutionBackend.CODEX

        if ttype in (TaskType.FEATURE, TaskType.BUGFIX):
            many_files = len(request.allowed_files or []) > self.policy.max_files_for_codex
            high_risk = _RISK_RANK[request.risk_level] > _RISK_RANK[self.policy.max_risk_for_codex]
            many_context = len(request.context_files or []) > self.policy.max_files_for_codex
            if many_files or high_risk or many_context or cross_language:
                return ExecutionBackend.CLAUDE_CODE
            return ExecutionBackend.CODEX

        # Default: codex for small/cheap, claude for everything else
        return ExecutionBackend.CODEX

    def _maybe_mock(self, *, preferred: ExecutionBackend, reason: str) -> RouterDecision:
        """Substitute a mock executor if the preferred CLI is unavailable."""
        candidates = [preferred]
        if preferred == ExecutionBackend.CODEX:
            if self.codex.is_available():
                return RouterDecision(preferred, candidates, reason, False, False)
            if not self.allow_mock:
                return RouterDecision(
                    preferred,
                    candidates,
                    reason + "; codex CLI missing AND allow_mock=false -> fail-closed",
                    False,
                    False,
                )
            return RouterDecision(
                ExecutionBackend.MOCK_CODEX,
                [preferred, ExecutionBackend.MOCK_CODEX],
                reason + "; codex CLI missing -> fallback to MOCK_CODEX",
                True,
                True,
            )
        if preferred == ExecutionBackend.CLAUDE_CODE:
            if self.claude.is_available():
                return RouterDecision(preferred, candidates, reason, False, False)
            if not self.allow_mock:
                return RouterDecision(
                    preferred,
                    candidates,
                    reason + "; claude CLI missing AND allow_mock=false -> fail-closed",
                    False,
                    False,
                )
            return RouterDecision(
                ExecutionBackend.MOCK_CLAUDE,
                [preferred, ExecutionBackend.MOCK_CLAUDE],
                reason + "; claude CLI missing -> fallback to MOCK_CLAUDE",
                True,
                True,
            )
        return RouterDecision(preferred, candidates, reason, False, preferred in (ExecutionBackend.MOCK_CODEX, ExecutionBackend.MOCK_CLAUDE))

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def execute(self, request: ExecutionRequest, *, cross_language: bool = False) -> tuple[ExecutionResult, RouterDecision]:
        decision = self.decide(request, cross_language=cross_language)

        # Fail-closed: real CLI requested but missing and mock disallowed
        if decision.selected_backend in (ExecutionBackend.CODEX, ExecutionBackend.CLAUDE_CODE):
            executor = self.codex if decision.selected_backend == ExecutionBackend.CODEX else self.claude
            if not executor.is_available():
                return (
                    ExecutionResult(
                        task_id=request.task_id,
                        milestone_id=request.milestone_id,
                        backend=decision.selected_backend,
                        language=request.language,
                        command="",
                        exit_code=127,
                        stdout="",
                        stderr=f"{decision.selected_backend.value} CLI missing and mock disallowed",
                        success=False,
                        error_type="cli_missing_fail_closed",
                        mock_used=False,
                        fallback_used=False,
                        mode=request.mode,
                        selected_backend_reason=decision.reason,
                    ),
                    decision,
                )

        executor = self._executor_for(decision.selected_backend)
        result = executor.execute(request)
        # Annotate the result with the routing reason
        result.selected_backend_reason = decision.reason
        result.fallback_used = decision.fallback_used
        result.mock_used = decision.mock_used or result.mock_used
        return result, decision

    def _executor_for(self, backend: ExecutionBackend) -> BaseExecutor:
        if backend == ExecutionBackend.CODEX:
            return self.codex
        if backend == ExecutionBackend.CLAUDE_CODE:
            return self.claude
        if backend == ExecutionBackend.MOCK_CODEX:
            return self.mock_codex
        if backend == ExecutionBackend.MOCK_CLAUDE:
            return self.mock_claude
        # AUTO should never reach here after decide()
        raise ValueError(f"no concrete executor for backend {backend}")


# Convenience: detect cross-language tasks from a list of languages
def is_cross_language(languages: list[Language]) -> bool:
    distinct = {l for l in languages if l not in (Language.UNKNOWN, Language.MIXED)}
    return len(distinct) >= 2
