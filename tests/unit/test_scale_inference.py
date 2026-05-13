"""Tests for RequirementAnalystAgent.infer_scale heuristic."""
from __future__ import annotations

import pytest

from autodev.agents.requirement_analyst import RequirementAnalystAgent
from autodev.schemas import (
    AcceptanceCriterion,
    Language,
    PRD,
    ProductBrief,
    Scale,
)


def _make_prd(n_ac: int, high_risk: bool = False) -> PRD:
    """Build a synthetic PRD with n_ac acceptance criteria."""
    acs = []
    for i in range(n_ac):
        desc = f"Criterion {i}"
        if high_risk and i == 0:
            desc = "CRITICAL: security compliance required"
        acs.append(AcceptanceCriterion(id=f"AC-{i:03d}", description=desc, verifiable_by="test"))
    return PRD(product_name="TestProduct", overview="overview", acceptance_criteria=acs)


def _make_brief(n_use_cases: int = 3) -> ProductBrief:
    return ProductBrief(
        product_name="TestProduct",
        goals=[f"goal {i}" for i in range(n_use_cases)],
        use_cases=[f"use case {i}" for i in range(n_use_cases)],
    )


def _analyst() -> RequirementAnalystAgent:
    return RequirementAnalystAgent()


class TestInferScaleBugFix:
    """<5 AC and not from_scratch => bug-fix."""

    def test_zero_ac_no_from_scratch(self):
        analyst = _analyst()
        prd = _make_prd(0)
        report = analyst.infer_scale(prd=prd, languages=[Language.PYTHON], from_scratch=False)
        assert report.scale == Scale.BUG_FIX

    def test_two_ac_no_from_scratch(self):
        analyst = _analyst()
        prd = _make_prd(2)
        report = analyst.infer_scale(prd=prd, languages=[Language.PYTHON], from_scratch=False)
        assert report.scale == Scale.BUG_FIX
        assert report.ac_count == 2

    def test_bug_fix_reasoning_contains_scale(self):
        analyst = _analyst()
        prd = _make_prd(1)
        report = analyst.infer_scale(prd=prd, languages=[Language.PYTHON])
        assert any("bug-fix" in r for r in report.reasoning)


class TestInferScaleSmall:
    """5-15 AC and 1 language => small. Also from_scratch => small."""

    def test_five_ac_single_language(self):
        analyst = _analyst()
        prd = _make_prd(5)
        report = analyst.infer_scale(prd=prd, languages=[Language.PYTHON], from_scratch=False)
        assert report.scale == Scale.SMALL

    def test_fifteen_ac_single_language(self):
        analyst = _analyst()
        prd = _make_prd(14)
        report = analyst.infer_scale(prd=prd, languages=[Language.PYTHON], from_scratch=False)
        assert report.scale == Scale.SMALL

    def test_from_scratch_promotes_to_small(self):
        analyst = _analyst()
        prd = _make_prd(2)  # <5 AC but from_scratch=True
        report = analyst.infer_scale(prd=prd, languages=[Language.PYTHON], from_scratch=True)
        assert report.scale == Scale.SMALL

    def test_small_language_count_one(self):
        analyst = _analyst()
        prd = _make_prd(8)
        report = analyst.infer_scale(prd=prd, languages=[Language.PYTHON])
        assert report.language_count == 1
        assert report.scale == Scale.SMALL


class TestInferScaleMedium:
    """15-50 AC OR 2 languages => medium."""

    def test_fifteen_ac_is_medium(self):
        analyst = _analyst()
        prd = _make_prd(15)
        report = analyst.infer_scale(prd=prd, languages=[Language.PYTHON], from_scratch=False)
        assert report.scale == Scale.MEDIUM

    def test_two_languages_promotes_to_medium(self):
        analyst = _analyst()
        prd = _make_prd(8)
        report = analyst.infer_scale(prd=prd, languages=[Language.PYTHON, Language.TYPESCRIPT])
        assert report.scale == Scale.MEDIUM
        assert report.language_count == 2

    def test_thirty_ac_is_medium(self):
        analyst = _analyst()
        prd = _make_prd(30)
        report = analyst.infer_scale(prd=prd, languages=[Language.PYTHON])
        assert report.scale == Scale.MEDIUM

    def test_medium_reasoning_present(self):
        analyst = _analyst()
        prd = _make_prd(20)
        report = analyst.infer_scale(prd=prd, languages=[Language.PYTHON])
        assert any("medium" in r for r in report.reasoning)


class TestInferScaleEnterprise:
    """>50 AC OR >=3 languages OR risk HIGH/CRITICAL => enterprise."""

    def test_fifty_one_ac_is_enterprise(self):
        analyst = _analyst()
        prd = _make_prd(51)
        report = analyst.infer_scale(prd=prd, languages=[Language.PYTHON])
        assert report.scale == Scale.ENTERPRISE

    def test_three_languages_is_enterprise(self):
        analyst = _analyst()
        prd = _make_prd(5)
        report = analyst.infer_scale(
            prd=prd,
            languages=[Language.PYTHON, Language.TYPESCRIPT, Language.RUST],
        )
        assert report.scale == Scale.ENTERPRISE
        assert report.language_count == 3

    def test_high_risk_ac_is_enterprise(self):
        analyst = _analyst()
        prd = _make_prd(3, high_risk=True)
        report = analyst.infer_scale(prd=prd, languages=[Language.PYTHON])
        assert report.scale == Scale.ENTERPRISE
        assert report.risk_level in ("high", "critical")

    def test_enterprise_reasoning_present(self):
        analyst = _analyst()
        prd = _make_prd(55)
        report = analyst.infer_scale(prd=prd, languages=[Language.PYTHON])
        assert any("enterprise" in r for r in report.reasoning)
