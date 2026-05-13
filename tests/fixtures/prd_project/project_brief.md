# Project Brief: Compliance Reporting Service

We want to build a small SaaS that ingests transaction CSVs and produces
compliance reports for finance teams.

## Goals
- Provide a CLI + HTTP API for ingestion.
- Produce monthly summary reports.
- Be auditable end-to-end.

## Users
- Compliance officers
- Finance analysts

## Use Cases
- Upload monthly CSV and get a structured report.
- Re-run a report against a prior period.

## MVP scope
- CLI ingestion of CSV.
- One report type ("monthly summary").
- File-based persistence.

## Non-Goals
- Multi-tenant SaaS.
- Real-time streaming ingestion.

Delivery boundary: Single repository, no external SaaS infra required.
