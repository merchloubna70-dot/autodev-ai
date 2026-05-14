"""BaseA2ATransport — abstract base for A2A transport implementations."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ....schemas import A2ATask, AgentCard


class BaseA2ATransport(ABC):
    """Abstract transport that sends a task to an agent and returns the completed task.

    Implementations MUST NOT raise exceptions — errors are expressed as
    ``task.status = A2ATaskStatus.FAILED`` with an error artifact.
    """

    @abstractmethod
    def send_task(self, card: AgentCard, task: A2ATask) -> A2ATask:
        """Send *task* to the agent described by *card*.

        Returns the mutated task with status set to COMPLETED (or FAILED on
        error) and the agent response appended to task.history and task.artifacts.
        """
        ...
