"""Bridge to CrewAI. Real Agent if installed, structural stub otherwise."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:  # pragma: no cover - import side effect varies by env
    from crewai import Agent as _CrewAgent  # type: ignore
    from crewai import Task as _CrewTask  # type: ignore
    from crewai import Crew as _CrewCrew  # type: ignore
    CREWAI_AVAILABLE = True
except Exception:
    _CrewAgent = None  # type: ignore
    _CrewTask = None  # type: ignore
    _CrewCrew = None  # type: ignore
    CREWAI_AVAILABLE = False


@dataclass
class StubCrewAgent:
    role: str
    goal: str
    backstory: str
    allow_delegation: bool = False
    verbose: bool = False

    def __post_init__(self) -> None:
        # mark this clearly so callers can tell it's a stub
        self.is_stub = True


@dataclass
class StubCrewTask:
    description: str
    agent: Any
    expected_output: str = ""

    def __post_init__(self) -> None:
        self.is_stub = True


@dataclass
class StubCrew:
    agents: list[Any]
    tasks: list[Any]
    verbose: bool = False

    def kickoff(self) -> str:  # pragma: no cover
        return "<crewai-not-installed: stub kickoff>"


def make_agent(*, role: str, goal: str, backstory: str, **kwargs: Any) -> Any:
    if CREWAI_AVAILABLE and _CrewAgent is not None:
        return _CrewAgent(role=role, goal=goal, backstory=backstory, **kwargs)
    return StubCrewAgent(role=role, goal=goal, backstory=backstory, **kwargs)


def make_task(*, description: str, agent: Any, expected_output: str = "") -> Any:
    if CREWAI_AVAILABLE and _CrewTask is not None:
        return _CrewTask(description=description, agent=agent, expected_output=expected_output)
    return StubCrewTask(description=description, agent=agent, expected_output=expected_output)


def make_crew(*, agents: list[Any], tasks: list[Any], verbose: bool = False) -> Any:
    if CREWAI_AVAILABLE and _CrewCrew is not None:
        return _CrewCrew(agents=agents, tasks=tasks, verbose=verbose)
    return StubCrew(agents=agents, tasks=tasks, verbose=verbose)
