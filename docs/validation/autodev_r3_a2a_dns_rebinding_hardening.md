# A2A HTTP Transport DNS-Rebinding TOCTOU Hardening — Validation Report

**Finding ID:** HIGH-SEC-02  
**Verdict:** `hardened_with_documented_residual_risk`  
**Date:** 2026-05-14  
**Round:** R3-E  
**Test pass count:** 10 / 10 (new tests) · 1045 total / 4 xfailed (full suite)

---

## Threat Model: DNS Rebinding TOCTOU

### Attack scenario

The R2 SSRF-hardening patch validated URLs by resolving the hostname via
`socket.getaddrinfo` and checking every returned address against a private-network
blocklist.  This is sound against naïve SSRF but has a TOCTOU (time-of-check /
time-of-use) race:

1. Attacker registers a domain (e.g. `evil.attacker.com`) with a very short TTL.
2. At **validation time** the authoritative DNS returns a legitimate public IP
   (e.g. `1.2.3.4`) → validation passes.
3. The attacker flips the DNS record to a private IP (e.g. `169.254.169.254`).
4. At **connect time** urllib calls the OS resolver again for the same hostname,
   now receives the private IP, and opens a TCP connection to the cloud metadata
   endpoint.

The window between step 2 and step 4 can be as small as a few milliseconds, but
with a TTL of 0 s (supported by most authoritative name servers) an attacker who
controls both the DNS and the timing can reliably win the race.

---

## Mitigation: IP-Pinning via Custom urllib Handlers

### Implementation

New symbols added to `src/autodev/adapters/a2a/transports/http.py`:

| Symbol | Role |
|--------|------|
| `_resolve_and_pin_host(hostname, allow_private)` | Resolves hostname via `socket.getaddrinfo` **once**, validates every address, returns the first address as the "pinned IP". Handles numeric IP literals (no DNS call). |
| `_PinnedHTTPSConnection` | Subclass of `http.client.HTTPSConnection` that connects the TCP socket to the pinned IP but passes `server_hostname=original_host` to the SSL handshake, ensuring TLS SNI and certificate validation use the original hostname. |
| `_PinnedHTTPHandler` | Subclass of `urllib.request.HTTPHandler` that overrides `do_open` to create an `http.client.HTTPConnection` targeting the pinned IP.  Injects `Host: original_host` into every request. |
| `_PinnedHTTPSHandler` | Subclass of `urllib.request.HTTPSHandler`; same as above but creates `_PinnedHTTPSConnection`. |
| `_build_pinned_opener(pinned_ip, original_host, scheme, port)` | Assembles a `urllib.request.OpenerDirector` with the appropriate pinned handler plus `_NoRedirectHandler`. |

### Request flow (allow_private_networks=False)

```
_make_request(url)
  │
  ├─ _validate_url(url, allow_private=False)   ← scheme check + DNS (all addresses)
  │
  ├─ _resolve_and_pin_host(hostname)           ← DNS resolution (single call), returns pinned_ip
  │
  ├─ _build_pinned_opener(pinned_ip, ...)      ← opens TCP to pinned_ip, sets Host header
  │
  └─ opener.open(req)                          ← OS never calls DNS again for this hop
```

On every redirect hop the Location URL is fully re-validated and
independently re-pinned — the pinned IP from hop N is never carried over to
hop N+1.

### DNS call count

For hostname labels, `socket.getaddrinfo` is called **twice** per hop:
once inside `_validate_url` (checks all addresses) and once inside
`_resolve_and_pin_host` (picks the first address to pin).  A DNS-rebinding
attacker must win **both** races simultaneously.  For numeric IP literals
(e.g. `http://169.254.169.254/`) no DNS call is made at all — the fast-path
literal-IP check fires.

### Escape hatch

When `allow_private_networks=True` (or `AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS=1`)
the entire DNS resolution / IP-pinning path is bypassed and the default
`urllib.request.build_opener` is used, preserving backwards compatibility for
integration-test environments that legitimately point at `localhost`.

---

## Test Results (10/10 pass)

| # | Test | Scenario | Result |
|---|------|----------|--------|
| 1 | `test_dns_rebinding_connect_to_pinned_public_ip` | DNS returns public IP at validate time; would return private IP at third call — connection uses pinned public IP | PASS |
| 2 | `test_different_public_ip_at_connect_time_succeeds` | Two different public IPs at validate vs. pin time — both safe, request succeeds | PASS |
| 3 | `test_redirect_to_private_hostname_rejected` | 302 redirect whose Location hostname resolves to `10.0.0.1` | PASS (blocked) |
| 4 | `test_redirect_to_public_hostname_allowed` | 302 redirect whose Location hostname resolves to public IP | PASS (allowed) |
| 5 | `test_max_redirects_5_enforced` | 6 sequential 302 responses — budget exhausted, returns `(0, b'')` | PASS |
| 6 | `test_https_server_hostname_set_correctly` | `_PinnedHTTPSConnection` stores `server_hostname=original_host` for SNI | PASS |
| 7 | `test_allow_private_networks_bypasses_ip_pinning` | `allow_private_networks=True` never calls `_build_pinned_opener` | PASS |
| 8 | `test_ipv6_redirect_to_loopback_rejected` | 302 redirect to `http://[::1]/admin` | PASS (blocked) |
| 9 | `test_resolve_and_pin_host_returns_public_ip` | `_resolve_and_pin_host` returns public IP for valid hostname | PASS |
| 10 | `test_resolve_and_pin_host_rejects_private_ip` | `_resolve_and_pin_host` raises `A2AHttpSSRFError` for private hostname | PASS |

Full suite: **1045 passed, 4 xfailed** (baseline before this patch: 1019 passed, 4 xfailed).

---

## Residual Risks

### RR-1: Egress-proxy SSRF (network-layer concern)

**Description:** An attacker who controls *both* DNS and a public HTTPS proxy
that internally tunnels requests to private hosts can bypass IP-pinning.  The
proxy's public IP passes all DNS and IP-range checks; the forwarding to a private
host happens inside the proxy's network, invisible to this adapter.

**Mitigation scope:** This is a network-egress / firewall concern.  The correct
mitigation is an egress firewall or transparent proxy that enforces IP-range
restrictions at the kernel/routing layer, not at the application layer.

**Status:** Not mitigated in this adapter.  Documented for operator awareness.

### RR-2: Kernel-level network attacks

**Description:** Routing table manipulation, anycast hijacking, on-path BGP
interception, or other kernel/network-layer attacks can redirect a TCP connection
to a pinned IP to a different host after `connect()` returns.  Pure-Python code
running in userspace has no visibility into these.

**Mitigation scope:** Requires network-layer security controls (RPKI, BGPsec,
mutual TLS, certificate pinning at the PKI level).  Outside the scope of an
HTTP-adapter patch.

**Status:** Not mitigated in this adapter.  Documented for operator awareness.

---

## Files Changed

- `src/autodev/adapters/a2a/transports/http.py` — IP-pinning implementation
- `tests/unit/test_a2a_dns_rebinding_hardening.py` — 10 new tests (new file)
