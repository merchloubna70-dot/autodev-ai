"""Pure-Python OpenAPI / JSON-Schema diff — no external deps."""
from __future__ import annotations


def diff_json_schemas(old: dict, new: dict) -> dict:
    """Diff two flat JSON-Schema-like dicts (properties level).

    Returns:
        {
            "added_fields": list[str],
            "removed_fields": list[str],
            "changed_types": list[dict]  # {field, old_type, new_type}
        }
    """
    old_props: dict = old.get("properties", old)
    new_props: dict = new.get("properties", new)

    old_keys = set(old_props.keys())
    new_keys = set(new_props.keys())

    added_fields = sorted(new_keys - old_keys)
    removed_fields = sorted(old_keys - new_keys)

    changed_types: list[dict] = []
    for key in old_keys & new_keys:
        old_val = old_props[key]
        new_val = new_props[key]
        # Compare "type" if both are dicts, or direct values otherwise
        if isinstance(old_val, dict) and isinstance(new_val, dict):
            old_type = old_val.get("type")
            new_type = new_val.get("type")
        else:
            old_type = old_val
            new_type = new_val
        if old_type != new_type:
            changed_types.append({"field": key, "old_type": old_type, "new_type": new_type})

    return {
        "added_fields": added_fields,
        "removed_fields": removed_fields,
        "changed_types": changed_types,
    }


def diff_openapi_specs(old_spec: dict, new_spec: dict) -> dict:
    """Diff two OpenAPI spec dicts.

    Each spec is expected to have an optional "paths" key mapping:
        path -> method -> schema_dict

    Returns:
        {
            "added_endpoints": list[str],    e.g. "GET /foo"
            "removed_endpoints": list[str],
            "changed_endpoints": list[dict], # {path, method, added_fields, removed_fields, changed_types}
        }
    """
    old_paths: dict = old_spec.get("paths", {})
    new_paths: dict = new_spec.get("paths", {})

    # Build flat map "METHOD /path" -> schema
    def flatten(paths: dict) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for path, methods in paths.items():
            if not isinstance(methods, dict):
                continue
            for method, schema in methods.items():
                key = f"{method.upper()} {path}"
                result[key] = schema if isinstance(schema, dict) else {}
        return result

    old_flat = flatten(old_paths)
    new_flat = flatten(new_paths)

    old_keys = set(old_flat.keys())
    new_keys = set(new_flat.keys())

    added_endpoints = sorted(new_keys - old_keys)
    removed_endpoints = sorted(old_keys - new_keys)

    changed_endpoints: list[dict] = []
    for key in old_keys & new_keys:
        schema_diff = diff_json_schemas(old_flat[key], new_flat[key])
        if (
            schema_diff["added_fields"]
            or schema_diff["removed_fields"]
            or schema_diff["changed_types"]
        ):
            # Parse back into path / method
            parts = key.split(" ", 1)
            method = parts[0]
            path = parts[1] if len(parts) > 1 else ""
            changed_endpoints.append(
                {
                    "path": path,
                    "method": method,
                    "added_fields": schema_diff["added_fields"],
                    "removed_fields": schema_diff["removed_fields"],
                    "changed_types": schema_diff["changed_types"],
                }
            )

    return {
        "added_endpoints": added_endpoints,
        "removed_endpoints": removed_endpoints,
        "changed_endpoints": changed_endpoints,
    }
