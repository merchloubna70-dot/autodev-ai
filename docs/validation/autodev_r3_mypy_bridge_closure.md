# R3 mypy bridge closure

**Date:** 2026-05-14
**Agent:** R3-A

## Exact mypy error before fix

```
src/autodev/adapters/a2a/transports/http.py:136: error: Argument 1 to "_is_private_address" has incompatible type "str | int"; expected "str"  [arg-type]
Found 1 error in 1 file (checked 171 source files)
```

Note: `pydantic_ai_bridge.py` itself was already clean (0 errors). The last remaining error in `src/autodev` was in `a2a/transports/http.py:136`.

## Root cause

`socket.getaddrinfo` returns type `list[tuple[AddressFamily, SocketKind, int, str, tuple[str, int] | tuple[str, int, int, int] | tuple[int, bytes]]]` per typeshed. The third union variant — `tuple[int, bytes]` — is for `AF_NETLINK` sockets (Linux kernel netlink). At index 0 this gives `int`, so the union type of `sockaddr[0]` is inferred as `str | int`.

The function `_is_private_address` has signature `(addr: str) -> bool`, so mypy correctly rejects the `str | int` argument.

At runtime the code only ever processes IPv4/IPv6 addresses (index 0 is always `str`), but mypy cannot know this.

## Fix

File: `src/autodev/adapters/a2a/transports/http.py`, line 135.

Changed:
```python
addr_str = sockaddr[0]
```
to:
```python
addr_str = str(sockaddr[0])
```

A one-line comment explains the `AF_NETLINK` typeshed gap. **No `# type: ignore` was used** — the fix is a real type narrowing via `str()` conversion, which is safe at runtime (IPv4/IPv6 address strings remain unchanged when passed through `str()`).

## type: ignore used?

No. The fix is a genuine type correction: wrapping `sockaddr[0]` in `str()` narrows from `str | int` to `str`. This is correct for IPv4/IPv6 and safe for `AF_NETLINK` (which this code path never reaches in practice).

## mypy error counts

| Phase | Errors |
|-------|--------|
| Before (pydantic_ai_bridge.py only) | 0 |
| Before (full src/autodev) | 1 |
| After (pydantic_ai_bridge.py only) | 0 |
| After (full src/autodev) | 0 |

## Test coverage

`tests/unit/test_pydantic_ai_bridge.py` — 5 tests:
1. `test_build_typed_classifier_returns_stub_when_pydantic_ai_missing` — factory returns stub, not None
2. `test_stub_forwards_to_input_classifier_agent` — stub delegates to InputClassifierAgent
3. `test_bridge_status_reports_stub_when_unavailable` — bridge_status reports stub=True
4. `test_bridge_status_schema_fields` — PydanticAIBridgeStatus construction
5. `test_build_typed_classifier_consistent_with_bridge_status` — stub state consistent with status

## Full test suite

```
1019 passed, 4 xfailed, 1 warning in 33.57s
```

## Verdict

`pass`
