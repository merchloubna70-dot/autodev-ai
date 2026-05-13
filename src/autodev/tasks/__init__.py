"""CrewAI Task wrappers. Each module exports a `build_*` factory that returns
a `crewai.Task` (or stub) bound to the matching agent.

These exist so a `crewai.Crew` can be assembled in flows/* using real CrewAI
constructs, in addition to the imperative orchestration the agents already
expose via their `.run(...)` / `.review(...)` methods.
"""
from .commit_tasks import build_commit_task  # noqa: F401
from .documentation_tasks import build_doc_task  # noqa: F401
from .implementation_tasks import build_implementation_task  # noqa: F401
from .input_tasks import build_input_classification_task  # noqa: F401
from .issue_tasks import build_issue_analysis_task  # noqa: F401
from .milestone_tasks import build_milestone_task  # noqa: F401
from .architecture_tasks import build_architecture_task  # noqa: F401
from .product_tasks import build_product_task  # noqa: F401
from .quality_tasks import build_quality_task  # noqa: F401
from .release_tasks import build_release_task  # noqa: F401
from .requirement_tasks import build_requirement_task  # noqa: F401
from .review_tasks import build_code_review_task, build_integration_review_task  # noqa: F401
from .security_tasks import build_security_task  # noqa: F401
from .test_tasks import build_test_design_task  # noqa: F401
from .verification_tasks import build_verification_task  # noqa: F401
