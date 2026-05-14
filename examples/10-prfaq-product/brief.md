# Project Brief: prfaq-product — Developer Telemetry SaaS (PRFAQ Demo)

A PRFAQ-style product brief for a developer-facing telemetry SaaS that captures
CLI tool usage metrics, surfaces adoption trends, and helps open-source
maintainers understand how their tools are actually used in production.

This brief is intentionally code-free and is intended to exercise autodev's
`--style prfaq` (BMAD-6) documentation pipeline.

## Goals
- Produce a press-release-style narrative describing the product from the
  customer's perspective before any code is written.
- Surface the FAQ section that anticipates the hardest objections (privacy,
  opt-in vs. opt-out, data retention).
- Serve as the input document for a subsequent autodev technical-spec run.

## Users
- Open-source maintainers of CLI tools (primary).
- Developer-relations teams at companies shipping internal CLIs (secondary).

## Use Cases
- A maintainer adds a one-line SDK call to their CLI; after 30 days they log in
  to a dashboard and see geographic distribution, command usage, and version
  adoption.
- A DevRel team creates a funnel report: downloads → first run → weekly active
  users, all broken down by company size from anonymous firmographic inference.

## MVP Scope (PRFAQ deliverables)
- Press release (400–600 words) written from the perspective of a launch-day
  announcement.
- FAQ section with at least 8 questions covering: privacy/opt-in, data residency,
  pricing model, SDK language support, self-hosting option, SLA, onboarding time,
  and competitive differentiation.
- One-page customer narrative ("day in the life") for each user persona.
- Working backwards document: what does success look like in 18 months?

## Non-Goals
- Actual code, SDK, or infrastructure design (handled in a follow-up spec).
- Marketing copy, ad creative, or landing page HTML.
- Pricing sheet or legal terms.

Delivery boundary: Markdown documents only; no code, no external services,
no tooling configuration required. All output files live under `docs/prfaq/`.
