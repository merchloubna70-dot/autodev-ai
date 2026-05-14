"""Coverage tests for autodev/gates/post_edit_lint_gate.py (49.5% → target 80%+).

Uncovered branches:
- line 45: lang == TYPESCRIPT/JAVASCRIPT → _check_node
- line 47: lang == RUST → _check_rust
- line 84/85/86: _check_python SyntaxError path
- line 90+: _check_node (node not available → skip)
- line 116+: _check_rust (cargo not available → skip)
"""
from __future__ import annotations

import shutil

from autodev.gates.post_edit_lint_gate import PostEditLintGate, _normalise
from autodev.schemas import Language

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

GATE = PostEditLintGate()


# ---------------------------------------------------------------------------
# 1. _normalise handles string and Language enum
# ---------------------------------------------------------------------------

def test_normalise_string_python():
    assert _normalise("python") == Language.PYTHON


def test_normalise_language_enum_passthrough():
    assert _normalise(Language.RUST) == Language.RUST


def test_normalise_unknown_string():
    assert _normalise("cobol") == Language.UNKNOWN


# ---------------------------------------------------------------------------
# 2. Python — valid file passes
# ---------------------------------------------------------------------------

def test_python_valid_file_passes(tmp_path):
    f = tmp_path / "good.py"
    f.write_text("x = 1 + 2\nprint(x)\n")
    result = GATE.run(str(tmp_path), ["good.py"], "python")
    assert result.ok is True
    assert result.errors == []


# ---------------------------------------------------------------------------
# 3. Python — syntax error file is caught and reported
# ---------------------------------------------------------------------------

def test_python_syntax_error_reported(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("def foo(\n  # unclosed paren\n")
    result = GATE.run(str(tmp_path), ["bad.py"], Language.PYTHON)
    assert result.ok is False
    assert any("bad.py" in e for e in result.errors)


# ---------------------------------------------------------------------------
# 4. Python — non-.py files in changed_files list are skipped
# ---------------------------------------------------------------------------

def test_python_skips_non_py_files(tmp_path):
    f = tmp_path / "readme.md"
    f.write_text("# hello")
    result = GATE.run(str(tmp_path), ["readme.md"], "python")
    assert result.ok is True
    assert result.errors == []


# ---------------------------------------------------------------------------
# 5. Python — missing file is skipped (no error, no crash)
# ---------------------------------------------------------------------------

def test_python_missing_file_skipped(tmp_path):
    result = GATE.run(str(tmp_path), ["does_not_exist.py"], "python")
    assert result.ok is True


# ---------------------------------------------------------------------------
# 6. TypeScript / JavaScript — node not present → skip gracefully
# ---------------------------------------------------------------------------

def test_typescript_no_node_skips_gracefully(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda x: None)
    f = tmp_path / "app.ts"
    f.write_text("const x: number = 1;\n")
    result = GATE.run(str(tmp_path), ["app.ts"], "typescript")
    assert result.ok is True
    assert result.errors == []


def test_javascript_no_node_skips_gracefully(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda x: None)
    f = tmp_path / "script.js"
    f.write_text("console.log('hi');\n")
    result = GATE.run(str(tmp_path), ["script.js"], Language.JAVASCRIPT)
    assert result.ok is True


# ---------------------------------------------------------------------------
# 7. Rust — cargo not present → skip gracefully
# ---------------------------------------------------------------------------

def test_rust_no_cargo_skips_gracefully(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda x: None)
    result = GATE.run(str(tmp_path), ["src/lib.rs"], "rust")
    assert result.ok is True
    assert result.errors == []


# ---------------------------------------------------------------------------
# 8. Unknown language → skip (ok=True)
# ---------------------------------------------------------------------------

def test_unknown_language_skips(tmp_path):
    result = GATE.run(str(tmp_path), ["main.go"], "go")
    assert result.ok is True
    assert result.errors == []


# ---------------------------------------------------------------------------
# 9. changed_files metadata is preserved in result
# ---------------------------------------------------------------------------

def test_changed_files_in_result(tmp_path):
    files = ["a.py", "b.py"]
    result = GATE.run(str(tmp_path), files, "python")
    assert set(result.changed_files) == set(files)
