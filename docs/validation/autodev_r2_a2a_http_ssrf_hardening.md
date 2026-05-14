# A2A HTTP Transport SSRF Hardening — Validation Report

**Finding ID:** HIGH-SEC-01  
**Verdict:** `hardened_with_known_residual_risk`  
**Date:** 2026-05-14  
**Test pass count:** 13 / 13

---

## Patch Description

`src/autodev/adapters/a2a/transports/http.py` received three hardening changes:

1. **`_validate_url(url, allow_private=False)`** — pre-flight URL validator that:
   - Rejects any scheme other than `http` / `https` (blocks `file://`, `ftp://`, `gopher://`, `unix://`, etc.)
   - Fast-path: if the hostname is a numeric IP literal, checks it directly against the private-range table without calling `socket.getaddrinfo`
   - For hostname labels, calls `socket.getaddrinfo` and checks every resolved address
   - Blocked ranges: loopback IPv4/IPv6, link-local IPv4/IPv6 (incl. `169.254.169.254`), RFC-1918 class A/B/C, unique-local IPv6 (`fc00::/7`), unspecified (`0.0.0.0`, `::`)
   - Raises `A2AHttpSSRFError` (subclass of `ValueError`) on rejection
   - **Note:** `A2AHttpSSRFError` must be caught **before** a bare `except ValueError` to avoid being swallowed — the implementation uses a two-step parse (`try/except ValueError` only to test parseability, then a separate `if` branch for the private-range check)

2. **`_NoRedirectHandler`** — subclasses `urllib.request.HTTPRedirectHandler` to suppress automatic redirect following; `redirect_request` returns `None` so urllib surfaces a `HTTPError` with the 3xx code instead of silently following

3. **`_make_request` redirect loop** — iterates up to 5 redirect hops; on each hop re-calls `_validate_url` before opening any connection, so an attacker cannot smuggle a private address via a redirect chain

4. **`A2AHttpTransport.__init__`** — new `allow_private_networks: bool = False` parameter plus `AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS` env-var override (for integration-test environments that legitimately run against localhost)

---

## Attack Vectors Covered (12 explicit test cases + 1 redirect chain)

| # | Vector | Status |
|---|--------|--------|
| 1 | `file:///etc/passwd` — non-http/https scheme | Rejected (scheme check) |
| 2 | `ftp://example.com` — non-http/https scheme | Rejected (scheme check) |
| 3 | `http://127.0.0.1:8080/` — loopback IPv4 literal | Rejected (literal-IP fast-path) |
| 4 | `http://169.254.169.254/` — AWS/GCP metadata endpoint | Rejected (literal-IP fast-path) |
| 5 | `http://localhost/` — DNS name resolving to loopback | Rejected (DNS resolution check) |
| 6 | `http://0.0.0.0/` — unspecified address literal | Rejected (literal-IP fast-path) |
| 7 | `http://10.0.0.1/` — RFC-1918 class A literal | Rejected (literal-IP fast-path) |
| 8 | `http://192.168.1.1/` — RFC-1918 class C literal | Rejected (literal-IP fast-path) |
| 9 | `http://[::1]/` — loopback IPv6 literal | Rejected (literal-IP fast-path) |
| 10 | DNS name that resolves to `127.0.0.1` (monkeypatched) | Rejected (DNS resolution check) |
| 11 | `http://example.com/` when DNS returns `93.184.216.34` | Allowed (public IP) |
| 12 | `allow_private=True` bypasses all checks | Bypassed (intended escape hatch) |
| 13 | 302 redirect from public URL to `http://169.254.169.254/` | Rejected (redirect re-validation) |

---

## Known Residual Risks

### 1. DNS Rebinding / TOCTOU Between Resolution and Connect

`_validate_url` resolves the hostname at validation time, but the actual TCP connection is established milliseconds later by urllib. A DNS rebinding attacker who controls the domain's authoritative nameserver can return a public IP during validation and then switch the DNS record to a private IP by the time the socket connects. This is inherent to any pre-flight DNS-based SSRF check and cannot be fully eliminated without a proxy/egress firewall that enforces the IP at the kernel/network layer.

**Mitigation available but not implemented here:** bind the resolved IP directly into the request URL, or use a DNS-pinning HTTP adapter. These would significantly increase complexity.

### 2. IPv6 Scope IDs and Non-Standard Notation

The implementation normalises IPv6 addresses via `ipaddress.ip_address()`, which handles standard bracket notation correctly. However, exotic encodings (e.g. decimal-encoded IPv4, IPv6-mapped IPv4 addresses like `::ffff:192.168.1.1`) are handled by the `ipaddress` library's canonical form. If a future Python version changes the scope-ID parsing behavior, some edge cases could slip through.

---

## Files Changed

- `src/autodev/adapters/a2a/transports/http.py` — hardening implementation
- `tests/unit/test_a2a_http_ssrf_hardening.py` — 13 new tests (new file)
- `tests/unit/test_a2a_http_transport.py` — added `allow_private_networks=True` to all existing test transport instantiations
- `tests/conftest.py` — added `AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS=1` env var so integration tests that use localhost remain green
