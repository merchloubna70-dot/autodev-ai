"""Unit tests for PropertyTestDesigner (W5)."""
from __future__ import annotations

import textwrap
from pathlib import Path

from autodev.agents.property_test_designer import PropertyTestDesigner
from autodev.schemas import PropertyTestSuggestion


def _write_py(tmp_path: Path, name: str, source: str) -> str:
    """Write source to a temp .py file and return its path string."""
    p = tmp_path / name
    p.write_text(textwrap.dedent(source), encoding="utf-8")
    return str(p)


class TestPropertyTestDesignerBasic:
    """Core strategy proposal logic."""

    def test_simple_add_proposes_integers_strategy(self, tmp_path):
        path = _write_py(tmp_path, "add.py", """
            def add(a: int, b: int) -> int:
                return a + b
        """)
        designer = PropertyTestDesigner()
        suggestions = designer.analyze(path)
        assert len(suggestions) >= 1
        found = next((s for s in suggestions if s.function_name == "add"), None)
        assert found is not None
        assert isinstance(found, PropertyTestSuggestion)
        # Both parameters are int → should propose integers() for each
        assert any("integers()" in strat for strat in found.given_strategies)

    def test_no_type_hints_yields_empty(self, tmp_path):
        path = _write_py(tmp_path, "nohints.py", """
            def compute(x, y):
                return x + y
        """)
        designer = PropertyTestDesigner()
        suggestions = designer.analyze(path)
        # No typed params → no suggestions for this function
        assert all(s.function_name != "compute" for s in suggestions)

    def test_side_effect_function_excluded(self, tmp_path):
        path = _write_py(tmp_path, "sideeffects.py", """
            def delete_record(record_id: int) -> None:
                pass

            def write_file(path: str) -> None:
                with open(path, "w") as f:
                    f.write("data")

            def save_data(value: str) -> bool:
                return True
        """)
        designer = PropertyTestDesigner()
        suggestions = designer.analyze(path)
        side_effect_names = {s.function_name for s in suggestions}
        # All three are write-like and should be excluded
        assert "delete_record" not in side_effect_names
        assert "write_file" not in side_effect_names
        assert "save_data" not in side_effect_names

    def test_mixed_file_only_pure_functions_returned(self, tmp_path):
        path = _write_py(tmp_path, "mixed.py", """
            def multiply(a: int, b: int) -> int:
                return a * b

            def update_counter(n: int) -> None:
                # side-effect verb in name
                pass

            def greet(name: str) -> str:
                return f"Hello, {name}"
        """)
        designer = PropertyTestDesigner()
        suggestions = designer.analyze(path)
        names = {s.function_name for s in suggestions}
        assert "multiply" in names
        assert "greet" in names
        assert "update_counter" not in names

    def test_suggestion_has_invariants(self, tmp_path):
        path = _write_py(tmp_path, "inv.py", """
            def square(n: int) -> int:
                return n * n
        """)
        designer = PropertyTestDesigner()
        suggestions = designer.analyze(path)
        found = next((s for s in suggestions if s.function_name == "square"), None)
        assert found is not None
        assert len(found.invariants) >= 1

    def test_target_file_field_matches_path(self, tmp_path):
        path = _write_py(tmp_path, "target.py", """
            def double(x: int) -> int:
                return x * 2
        """)
        designer = PropertyTestDesigner()
        suggestions = designer.analyze(path)
        assert all(s.target_file == path for s in suggestions)

    def test_str_param_proposes_text_strategy(self, tmp_path):
        path = _write_py(tmp_path, "strtarget.py", """
            def upper(s: str) -> str:
                return s.upper()
        """)
        designer = PropertyTestDesigner()
        suggestions = designer.analyze(path)
        found = next((s for s in suggestions if s.function_name == "upper"), None)
        assert found is not None
        assert any("text(" in strat for strat in found.given_strategies)
