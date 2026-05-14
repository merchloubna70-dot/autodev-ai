# Project Brief: pdf-extractor — Python PDF Text & Table Library

A Python library that extracts plain text and tabular data from PDF files using
`pdfplumber`, returning structured results consumable by downstream pipelines.

## Goals
- Provide a clean, typed Python API for PDF text and table extraction.
- Handle multi-page documents and mixed text/table pages.
- Ship as an installable package with a thin CLI entry point.

## Users
- Data engineers ingesting PDF reports into data pipelines.
- Legal tech developers extracting clauses from contract PDFs.

## Use Cases
- `from pdf_extractor import extract_text` returns page-indexed text blocks.
- `from pdf_extractor import extract_tables` returns a list of DataFrames, one per table found.
- `pdf-extractor extract report.pdf --out report.json` writes structured JSON output.

## MVP Scope
- Package layout: `pdf_extractor/__init__.py`, `pdf_extractor/text.py`,
  `pdf_extractor/tables.py`, `pdf_extractor/cli.py`.
- `extract_text(path: str) -> list[PageText]` where `PageText` has `page`, `content` fields.
- `extract_tables(path: str) -> list[TableResult]` where `TableResult` has `page`,
  `df` (pandas DataFrame) fields.
- CLI: `pdf-extractor extract <file> [--out <json>] [--pages <range>]`.
- `pytest` suite with three fixture PDFs (text-only, tables-only, mixed).
- `pyproject.toml` with `pdfplumber` and `pandas` as runtime deps.

## Non-Goals
- OCR of scanned/image PDFs.
- Form field extraction.
- PDF generation or modification.

Delivery boundary: Single repository, installable via `pip install -e .`,
fixture PDFs included in `tests/fixtures/`.
