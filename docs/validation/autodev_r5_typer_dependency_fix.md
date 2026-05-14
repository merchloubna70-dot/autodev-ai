# R5-A — typer dependency fix

**Verdict: `pass`**

## Issue

When users install `autodev-ai` from PyPI, pip emits:
```
WARNING: typer 0.25.1 does not provide the extra 'all'
```

Cause: `pyproject.toml` had `typer[all]>=0.9`. typer dropped the `[all]` extra around version 0.12 because `rich` + `shellingham` are bundled directly into the typer wheel now.

## Fix

```diff
 dependencies = [
     "pydantic>=2.5,<3.0",
-    "typer[all]>=0.9",
+    "typer>=0.12",
     "rich>=13.7",
+    "shellingham>=1.5",
     "PyYAML>=6.0",
     "jinja2>=3.1",
 ]
```

- Pin `typer>=0.12` to skip the legacy `[all]` resolution path.
- Explicitly declare `shellingham>=1.5` (previously implicit via `[all]`) so we're not exposed if typer ever stops bundling it.
- `rich>=13.7` was already explicit; left as-is.

## Verification

```
$ pip install -e . --quiet
(no `does not provide the extra 'all'` warning)

$ autodev --version
autodev-ai 0.1.0a2

$ pytest tests/unit/test_version_consistency.py tests/unit/test_cli_help_surface.py -q
42 passed
```

## Release impact

This is a metadata-only fix. Behavior unchanged. A new `v0.1.0a3` release (or whatever the next tag is) will carry this cleaner declaration and PyPI users will no longer see the warning. Until then, the `v0.1.0a2` already-published wheel keeps the warning — it's cosmetic, doesn't break install.
