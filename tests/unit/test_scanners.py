from pathlib import Path

from autodev.scanners import (
    MonorepoScanner,
    PythonScanner,
    RepoScanner,
    RustScanner,
    TypeScriptScanner,
)
from autodev.schemas import Language

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def test_python_scanner():
    res = PythonScanner().scan(FIX / "python_project")
    assert res.detected
    assert any("pyproject.toml" in pf for pf in res.package_files)


def test_rust_scanner():
    res = RustScanner().scan(FIX / "rust_project")
    assert res.detected
    assert any("Cargo.toml" in pf for pf in res.package_files)


def test_typescript_scanner():
    res = TypeScriptScanner().scan(FIX / "typescript_project")
    assert res.detected
    assert any("package.json" in pf for pf in res.package_files)


def test_repo_scanner_mixed():
    res = RepoScanner().scan(str(FIX / "mixed_project"))
    langs = {lang.value for lang in res.detected_languages}
    assert "python" in langs
    assert "rust" in langs
    assert "typescript" in langs


def test_monorepo_detected():
    assert MonorepoScanner().is_monorepo(FIX / "monorepo_project")


def test_repo_scanner_empty():
    res = RepoScanner().scan(str(FIX / "empty_project"))
    assert res.is_empty is True
    assert res.detected_languages == [] or res.detected_languages == [Language.UNKNOWN]
