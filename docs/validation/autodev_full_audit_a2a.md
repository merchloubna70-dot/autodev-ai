# Pre-Tag Full Audit — A2A SSRF + DNS Rebinding Hardening (PreTag-E)

**Date:** 2026-05-14
**Agent:** PreTag-E
**Builds on:** R1-F, R2-D, R3-E (no re-analysis of prior deep findings)

---

## Test Results

Pytest filter: `a2a or roundtable or ssrf or rebinding`

| Result | Count |
|--------|-------|
| passed | 111 |
| xfail  | 0 |
| failed | 0 |

Command: `/Users/macworkers/autodev/.venv/bin/python -m pytest tests/ -k 'a2a or roundtable or ssrf or rebinding' -q`

---

## SSRF / DNS Rebinding Hardening Symbols

File: `src/autodev/adapters/a2a/transports/http.py`

| Symbol | Present |
|--------|---------|
| `A2AHttpSSRFError` (exception class, line 86) | YES |
| `_resolve_and_pin_host` (function, line 187) | YES |
| `_PinnedHTTPHandler` (class, line 289) | YES |
| `_PinnedHTTPSHandler` (class, line 320) | YES |
| `allow_private_networks` parameter on `A2AHttpTransport.__init__` (line 436) | YES |

All 5 symbols confirmed present. The DNS-pinning path is active when `allow_private_networks=False` (default): `_resolve_and_pin_host` is called per redirect hop, a custom urllib opener (`_build_pinned_opener`) connects directly to the pinned IP, and the OS resolver is never consulted again for that hop.

Documented residual risk (unchanged from R3-E): egress-proxy SSRF — an attacker controlling DNS plus a public proxy tunneling to a private host can bypass IP-pinning because the proxy's public IP passes all checks. This is a network-egress/firewall concern outside the HTTP adapter scope.

---

## Roundtable Party-Mode Invariant

File: `src/autodev/agents/roundtable.py`

| Check | Result |
|-------|--------|
| Each card receives `base_task.model_copy(deep=True)` — not a shared reference | YES (line 230) |
| Card-to-task association uses `dict[str, A2ATask]` keyed by `card.name` | YES (`results_by_card: dict[str, A2ATask] = {}`, line 226) |
| No zip-based ordering dependency — dict lookup used in assembly loop | YES (line 260: `results_by_card.get(card.name)`) |
| Agents dispatched in parallel via `ThreadPoolExecutor`; no inter-agent visibility | YES |

Party-mode invariant holds: each participant receives an independent deep copy of the base task before dispatch; the dict mapping guarantees card-to-result association is not sensitive to `as_completed` ordering.

---

## A2A Schema Count

File: `src/autodev/schemas.py`

The 6 canonical A2A schemas are all present:

1. `A2APart` (line 959)
2. `A2AMessage` (line 967)
3. `A2ATaskStatus` (line 976)
4. `A2ATask` (line 985)
5. `AgentCard` (line 996)
6. `A2AConversation` (line 1016)

Count: **6** (matches spec).

---

## Verdict

**a2a_hardened_with_residual_egress_proxy**

All SSRF and DNS-rebinding hardening symbols are in place. 111 A2A/roundtable tests pass with 0 failures. Roundtable party-mode invariant (deep-copy per card + dict mapping) holds. Schema count is exactly 6. No regression versus R3-E. The sole residual risk — egress-proxy SSRF — is documented in the module docstring and is a network-layer concern beyond the HTTP adapter's scope.
