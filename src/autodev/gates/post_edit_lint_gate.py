"""PostEditLintGate — language-aware syntax check after an edit step.

Rules:
- Python: ast.parse — available everywhere, never raises.
- TypeScript/JavaScript: ``node --check`` if node is on PATH, else skip.
- Rust: ``cargo check --quiet`` if cargo is on PATH, else skip.
- Any other language: skip (ok=True, no errors).

NEVER raises — all exceptions are caught and recorded in LintGateResult.errors.
"""
from __future__ import annotations

import ast
import shutil
import subprocess
from pathlib import Path

from ..schemas import Language, LintGateResult


class PostEditLintGate:
    """Run language-aware syntax checks on a set of changed files."""

    def run(
        self,
        repo_path: str,
        changed_files: list[str],
        language: str | Language,
    ) -> LintGateResult:
        """Check *changed_files* under *repo_path* for syntax errors.

        Returns LintGateResult.  Never raises.
        """
        lang = _normalise(language)
        result = LintGateResult(
            language=lang,
            ok=True,
            changed_files=list(changed_files),
        )

        try:
            if lang == Language.PYTHON:
                _check_python(repo_path, changed_files, result)
            elif lang in (Language.TYPESCRIPT, Language.JAVASCRIPT):
                _check_node(repo_path, changed_files, result)
            elif lang == Language.RUST:
                _check_rust(repo_path, result)
            # else: skip — unsupported language
        except Exception as exc:  # pragma: no cover — safety net
            result.ok = False
            result.errors.append(f"unexpected error in lint gate: {exc}")

        return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _normalise(language: str | Language) -> Language:
    if isinstance(language, Language):
        return language
    try:
        return Language(language.lower())
    except ValueError:
        return Language.UNKNOWN


def _check_python(repo_path: str, changed_files: list[str], result: LintGateResult) -> None:
    root = Path(repo_path)
    for rel in changed_files:
        if not rel.endswith(".py"):
            continue
        path = root / rel
        if not path.exists():
            continue
        try:
            source = path.read_text(encoding="utf-8")
            ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            result.ok = False
            result.errors.append(f"{rel}:{exc.lineno}: {exc.msg}")
        except Exception as exc:
            result.ok = False
            result.errors.append(f"{rel}: read/parse error: {exc}")


def _check_node(repo_path: str, changed_files: list[str], result: LintGateResult) -> None:
    if not shutil.which("node"):
        # node not available — skip gracefully
        return
    root = Path(repo_path)
    for rel in changed_files:
        if not (rel.endswith(".ts") or rel.endswith(".js")):
            continue
        path = root / rel
        if not path.exists():
            continue
        try:
            proc = subprocess.run(
                ["node", "--check", str(path)],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if proc.returncode != 0:
                result.ok = False
                result.errors.append(f"{rel}: {(proc.stderr or proc.stdout).strip()}")
        except Exception as exc:
            result.ok = False
            result.errors.append(f"{rel}: node check error: {exc}")


def _check_rust(repo_path: str, result: LintGateResult) -> None:
    if not shutil.which("cargo"):
        # cargo not available — skip gracefully
        return
    try:
        proc = subprocess.run(
            ["cargo", "check", "--quiet"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            result.ok = False
            stderr = (proc.stderr or proc.stdout).strip()
            for line in stderr.splitlines()[:20]:  # cap error lines
                result.errors.append(line)
    except Exception as exc:
        result.ok = False
        result.errors.append(f"cargo check error: {exc}")
