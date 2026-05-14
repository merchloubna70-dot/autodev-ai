"""Skill pack: Next.js 14 app with TypeScript, Tailwind, App Router."""
from __future__ import annotations

from .base import SkillPack


class NextjsAppPack(SkillPack):
    """Curated template for a Next.js 14 application project."""

    @property
    def name(self) -> str:
        return "nextjs-app"

    @property
    def description(self) -> str:
        return "Next.js 14 app with TypeScript, Tailwind, App Router"

    @property
    def brief_template(self) -> str:
        return """\
# Project Brief: {{project_name}}

## Summary
{{project_name}} is a Next.js 14 web application that {{summary}}.

## Goals
- Ship a production-ready web app using the App Router
- Achieve good Core Web Vitals (LCP < 2.5 s)
- Maintain full TypeScript strict-mode compliance

## Key Features
- {{feature_1}}
- {{feature_2}}

## Stack
- Framework: Next.js 14 (App Router)
- Language: TypeScript (strict)
- Styling: Tailwind CSS v3
- State / data: React Server Components + fetch
- Testing: Vitest + Testing Library (unit) + Playwright (E2E)
- Deployment: Vercel / Docker
"""

    @property
    def prd_template(self) -> str:
        return """\
# PRD: {{project_name}}

## 1. Overview
<!-- Web application purpose, target audience, and success metrics. -->

## 2. Problem Statement
<!-- The user workflow gap this app fills. -->

## 3. Functional Requirements
### 3.1 Pages & Routes
<!-- List each App Router route, its layout, and main functionality. -->

### 3.2 Server Components vs Client Components
<!-- Which routes/components are RSC vs "use client". -->

### 3.3 API Routes
<!-- Next.js Route Handlers at `app/api/…` and their contracts. -->

### 3.4 Authentication
<!-- NextAuth.js, Clerk, or custom auth strategy. -->

## 4. Non-Functional Requirements
- Core Web Vitals targets (LCP / INP / CLS)
- SEO requirements (metadata API, sitemap)
- Accessibility standard (WCAG 2.1 AA)

## 5. Architecture
- `app/`: App Router layout tree
- `components/`: Shared UI (shadcn/ui or custom)
- `lib/`: Utility functions and server-only code
- `public/`: Static assets
- TypeScript path aliases configured in `tsconfig.json`

## 6. Milestones
<!-- See milestones_template in NextjsAppPack. -->

## 7. Acceptance Criteria
- `next build` succeeds with zero TypeScript errors
- Lighthouse score ≥ 90 on all four categories
- All Vitest and Playwright tests pass
- Deployed preview URL works end-to-end
"""

    @property
    def milestones_template(self) -> list[str]:
        return [
            "scaffold",
            "layout-and-routing",
            "core-pages",
            "api-routes",
            "tests",
            "ci",
            "release",
        ]

    @property
    def recommended_executor(self) -> str:
        return "auto"

    @property
    def recommended_extras(self) -> list[str]:
        return []
