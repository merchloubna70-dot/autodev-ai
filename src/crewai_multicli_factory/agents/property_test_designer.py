"""PropertyTestDesigner — AST-based Hypothesis strategy proposer.

Analyzes a Python source file using ``ast`` (pure stdlib, no execution) and
proposes Hypothesis ``@given`` strategies for functions with type annotations.

Heuristic side-effect filter: functions whose names contain write-like verbs
(delete, write, save, send, post, put, update, remove, drop, truncate) or
whose bodies reference ``open(`` / ``os.remove`` / ``shutil`` are flagged and
skipped because property-testing I/O side-effecting functions without proper
sandboxing is risky.
"""
from __future__ import annotations

import ast
from pathlib import Path

from ..schemas import PropertyTestSuggestion

# Map Python built-in type annotation names → Hypothesis strategy strings
_TYPE_TO_STRATEGY: dict[str, str] = {
    "int": "integers()",
    "float": "floats(allow_nan=False)",
    "str": "text(min_size=1)",
    "bool": "booleans()",
    "bytes": "binary()",
    "list": "lists(integers())",
    "dict": "fixed_dictionaries({})",
    "tuple": "tuples(integers())",
    "set": "sets(integers())",
}

# Write-like verb fragments that indicate side effects
_SIDE_EFFECT_VERBS = frozenset({
    "delete", "write", "save", "send", "post", "put", "update",
    "remove", "drop", "truncate", "insert", "commit", "flush",
    "create", "mkdir", "unlink",
})

# AST node call names that indicate I/O side effects in the function body
_SIDE_EFFECT_CALLS = frozenset({
    "open", "write", "remove", "unlink", "rmdir", "rmtree",
    "makedirs", "mkdir", "rename", "replace",
})


def _annotation_to_strategy(annotation: ast.expr | None) -> str | None:
    """Convert an AST annotation node to a Hypothesis strategy string, or None."""
    if annotation is None:
        return None
    if isinstance(annotation, ast.Name):
        return _TYPE_TO_STRATEGY.get(annotation.id)
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        return _TYPE_TO_STRATEGY.get(annotation.value)
    # Optional[X] / Union[X, None] — pick the first non-None arg
    if isinstance(annotation, ast.Subscript):
        # Handle generic aliases like List[int], Optional[str], etc.
        if isinstance(annotation.value, ast.Name):
            outer = annotation.value.id
            if outer in ("Optional",):
                # e.g. Optional[int] → integers()
                inner = annotation.slice
                return _annotation_to_strategy(inner)
            if outer in ("List", "list"):
                inner_strat = _annotation_to_strategy(annotation.slice)
                if inner_strat:
                    return f"lists({inner_strat})"
    return None


def _has_side_effects(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Heuristic: return True if the function likely has I/O side effects."""
    name_lower = func_node.name.lower()
    if any(verb in name_lower for verb in _SIDE_EFFECT_VERBS):
        return True
    for node in ast.walk(func_node):
        if isinstance(node, ast.Call):
            # Check plain calls like open(...)
            if isinstance(node.func, ast.Name) and node.func.id in _SIDE_EFFECT_CALLS:
                return True
            # Check attribute calls like os.remove(...), shutil.rmtree(...)
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in _SIDE_EFFECT_CALLS:
                    return True
                if isinstance(node.func.value, ast.Name):
                    if node.func.value.id in ("shutil", "os", "pathlib"):
                        return True
    return False


class PropertyTestDesigner:
    """Propose Hypothesis ``@given`` strategies for typed Python functions.

    Uses only ``ast`` (pure stdlib).  The target file is **never executed**.
    """

    def analyze(self, target_file: str) -> list[PropertyTestSuggestion]:
        """Parse ``target_file`` and return property-test suggestions.

        Parameters
        ----------
        target_file:
            Path to the Python source file to analyze.

        Returns
        -------
        list[PropertyTestSuggestion]
            One entry per eligible function.  Functions without type hints or
            with detected side effects are skipped.
        """
        source = Path(target_file).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=target_file)
        suggestions: list[PropertyTestSuggestion] = []

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            # Skip private/dunder helpers
            if node.name.startswith("_"):
                continue
            # Skip side-effecting functions
            if _has_side_effects(node):
                continue

            strategies = self._extract_strategies(node)
            if not strategies:
                continue  # no typed parameters → skip

            invariants = self._infer_invariants(node, strategies)
            risk_notes = []
            if isinstance(node, ast.AsyncFunctionDef):
                risk_notes.append("async function — wrap with @pytest.mark.asyncio")

            suggestions.append(PropertyTestSuggestion(
                target_file=target_file,
                function_name=node.name,
                given_strategies=strategies,
                invariants=invariants,
                risk_notes=risk_notes,
            ))

        return suggestions

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_strategies(
        self,
        func: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> list[str]:
        """Return a strategy string for each typed argument (skip *args/**kwargs)."""
        strategies: list[str] = []
        args = func.args
        all_args = args.args + args.posonlyargs + args.kwonlyargs
        annotations_map = {
            a.arg: a.annotation
            for a in all_args
            if a.annotation is not None and a.arg not in ("self", "cls")
        }
        for arg in all_args:
            if arg.arg in ("self", "cls"):
                continue
            ann = annotations_map.get(arg.arg)
            strat = _annotation_to_strategy(ann)
            if strat:
                strategies.append(strat)
        return strategies

    def _infer_invariants(
        self,
        func: ast.FunctionDef | ast.AsyncFunctionDef,
        strategies: list[str],
    ) -> list[str]:
        """Generate human-readable invariant strings from return annotation."""
        invariants: list[str] = []
        ret_ann = func.returns
        if ret_ann is not None:
            ret_strat = _annotation_to_strategy(ret_ann)
            if ret_strat:
                invariants.append(
                    f"Return type matches annotation; result should be a valid {_annotation_name(ret_ann)}"
                )
            else:
                invariants.append("Function should not raise for valid typed inputs")
        else:
            invariants.append("Function should not raise for valid typed inputs")
        return invariants


def _annotation_name(annotation: ast.expr) -> str:
    if isinstance(annotation, ast.Name):
        return annotation.id
    if isinstance(annotation, ast.Constant):
        return str(annotation.value)
    return "value"
