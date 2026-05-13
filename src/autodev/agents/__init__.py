"""CrewAI-backed agents.

All agents expose a `.crewai_agent()` factory that returns a real `crewai.Agent`
instance when CrewAI is installed, and falls back to a structural stub
otherwise so that tests / dry-run pipelines still execute deterministically.

The actual orchestration logic for each agent lives in the `.run(...)` method
so the system stays usable without a network-bound LLM in CI.
"""
from .code_reviewer import CodeReviewerAgent  # noqa: F401
from .commit_agent import CommitAgent  # noqa: F401
from .doc_writer import DocWriterAgent  # noqa: F401
from .implementer import ImplementerAgent  # noqa: F401
from .input_classifier import InputClassifierAgent  # noqa: F401
from .integration_reviewer import IntegrationReviewerAgent  # noqa: F401
from .issue_analyst import IssueAnalystAgent  # noqa: F401
from .milestone_planner import MilestonePlannerAgent  # noqa: F401
from .prd_writer import PRDWriterAgent  # noqa: F401
from .product_manager import ProductManagerAgent  # noqa: F401
from .release_manager import ReleaseManagerAgent  # noqa: F401
from .repo_explorer import RepoExplorerAgent  # noqa: F401
from .requirement_analyst import RequirementAnalystAgent  # noqa: F401
from .scaffolder import ScaffolderAgent  # noqa: F401
from .security_reviewer import SecurityReviewerAgent  # noqa: F401
from .system_architect import SystemArchitectAgent  # noqa: F401
from .task_decomposer import TaskDecomposerAgent  # noqa: F401
from .test_designer import TestDesignerAgent  # noqa: F401
from .verifier import VerifierAgent  # noqa: F401
from .quality_gate import QualityGateAgent  # noqa: F401
from .critic import CriticAgent  # noqa: F401
from .navigator import NavigatorAgent  # noqa: F401
from .parallel_section_reviewer import ParallelSectionReviewer  # noqa: F401
from .human_review_gate import HumanReviewGate  # noqa: F401
from .clarification_gate import ClarificationGate  # noqa: F401
from .property_test_designer import PropertyTestDesigner  # noqa: F401
from .roundtable import RoundtableAgent  # noqa: F401
from .next_step_advisor import NextStepAdvisor  # noqa: F401
from .adversarial_reviewer import AdversarialReviewer  # noqa: F401
from .edge_case_hunter import EdgeCaseHunter  # noqa: F401
from .editorial_reviewer import EditorialReviewer  # noqa: F401
