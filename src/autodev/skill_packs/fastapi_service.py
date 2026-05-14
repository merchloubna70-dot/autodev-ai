"""Skill pack: FastAPI app with uvicorn, pytest, Docker dockerfile."""
from __future__ import annotations

from .base import SkillPack


class FastAPIServicePack(SkillPack):
    """Curated template for a FastAPI microservice project."""

    @property
    def name(self) -> str:
        return "fastapi-service"

    @property
    def description(self) -> str:
        return "FastAPI app with uvicorn, pytest, Docker dockerfile"

    @property
    def brief_template(self) -> str:
        return """\
# Project Brief: {{project_name}}

## Summary
{{project_name}} is a FastAPI HTTP service that {{summary}}.

## Goals
- Expose a REST API with OpenAPI/Swagger docs auto-generated
- Containerise with Docker for easy deployment
- Achieve ≥ 90 % pytest coverage

## Key Features
- {{feature_1}}
- {{feature_2}}

## Stack
- Language: Python ≥ 3.11
- Framework: FastAPI + uvicorn
- Validation: Pydantic v2
- Testing: pytest + httpx (AsyncClient)
- Container: Docker (multi-stage build)
- CI: GitHub Actions
"""

    @property
    def prd_template(self) -> str:
        return """\
# PRD: {{project_name}}

## 1. Overview
<!-- Product description and target consumers (other services, web clients, etc.). -->

## 2. Problem Statement
<!-- The integration gap or workflow this service addresses. -->

## 3. Functional Requirements
### 3.1 Endpoints
<!-- List each route, method, request schema, and response schema. -->

### 3.2 Authentication
<!-- API-key header, JWT, or public (state explicitly). -->

### 3.3 Background Tasks
<!-- Any celery/arq/fastapi BackgroundTask workers needed. -->

## 4. Non-Functional Requirements
- p99 latency target under expected load
- Horizontal scalability constraints
- Secret management strategy (env vars / secrets manager)

## 5. Architecture
- `app/main.py`: FastAPI application factory
- `app/routers/`: one file per resource group
- `app/models.py`: Pydantic schemas (request / response)
- `app/deps.py`: FastAPI dependency injection
- `tests/`: pytest suite with AsyncClient fixtures

## 6. Milestones
<!-- See milestones_template in FastAPIServicePack. -->

## 7. Acceptance Criteria
- `pytest` passes with ≥ 90 % coverage
- `docker build` succeeds and `docker run` serves requests
- OpenAPI schema rendered at `/docs`
- All endpoints return correct HTTP status codes
"""

    @property
    def milestones_template(self) -> list[str]:
        return [
            "scaffold",
            "models-and-routes",
            "core-impl",
            "tests",
            "dockerfile",
            "ci",
            "release",
        ]

    @property
    def recommended_executor(self) -> str:
        return "auto"

    @property
    def recommended_extras(self) -> list[str]:
        return ["fastapi", "uvicorn[standard]", "httpx"]
