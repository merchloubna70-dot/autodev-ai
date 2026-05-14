# SBOM Consumption Guide

Every tagged release of `autodev` includes two Software Bill of Materials (SBOM)
files attached as GitHub Release assets:

| File | Standard | Version |
|------|----------|---------|
| `sbom.cdx.json` | CycloneDX | 1.5 |
| `sbom.spdx.json` | SPDX | 2.3 |

---

## What Is an SBOM?

An SBOM is a machine-readable inventory of every software component that makes up
a release — direct dependencies, transitive dependencies, and the package itself.
It captures name, version, license, and (where available) the component's content
hash, enabling downstream tooling to answer questions about composition, risk, and
provenance without access to source code.

---

## The Two Formats

**CycloneDX 1.5** (`sbom.cdx.json`)
A security-focused standard maintained by OWASP. CycloneDX components carry
`purl` (Package URL) identifiers that link directly into vulnerability databases
such as the NVD. Preferred by Grype and Trivy.

**SPDX 2.3** (`sbom.spdx.json`)
The Linux Foundation standard and the format mandated by the US Executive Order
on Cybersecurity (EO 14028). SPDX captures SPDXID relationships between packages
and explicitly records license expressions using the SPDX License List identifiers.
Required for US Federal software procurement compliance.

---

## Four Key Use Cases

### 1. CVE / Vulnerability Lookup

Scan the SBOM against known vulnerability databases to find which release
components have published CVEs — without re-running a full dependency install.

```bash
# Grype (CycloneDX)
grype sbom:sbom.cdx.json

# Trivy (CycloneDX)
trivy sbom sbom.cdx.json
```

### 2. License Compliance

Extract the complete license inventory to verify that all transitive dependencies
are compatible with your organisation's open-source policy.

```bash
# Syft can re-read an SPDX SBOM and list licenses
syft scan packages:sbom.spdx.json

# Or use tern (SPDX-aware)
tern report -f spdxjson -i sbom.spdx.json
```

### 3. Audit and Procurement

Regulated environments (finance, healthcare, government) may require an SBOM as
part of supplier due diligence. Attach the release asset URL to your vendor
questionnaire or procurement record. The SPDX format is preferred by most audit
frameworks.

### 4. EU Cyber Resilience Act (CRA) & US EO 14028

Both regulations require software suppliers to provide an SBOM:

- **US EO 14028 (2021)** — agencies procuring software must obtain SBOMs in
  SPDX or CycloneDX format. `sbom.spdx.json` satisfies this requirement directly.
- **EU CRA (2024, enforcement 2027)** — manufacturers of products with digital
  elements must document components and actively monitor for vulnerabilities.
  Both formats are accepted; CycloneDX 1.5 VEX extensions allow attaching
  exploitability statements alongside the SBOM.

---

## Downloading the Assets

From the GitHub Releases page, expand the Assets section of any tagged release
and download `sbom.cdx.json` or `sbom.spdx.json`. Via the CLI:

```bash
# Replace v0.1.0 with the target tag
gh release download v0.1.0 --pattern "sbom.*" --repo your-org/autodev
```

---

## Tooling Reference

| Tool | Install | Supports |
|------|---------|----------|
| [Grype](https://github.com/anchore/grype) | `brew install grype` | CycloneDX, SPDX |
| [Trivy](https://github.com/aquasecurity/trivy) | `brew install trivy` | CycloneDX, SPDX |
| [Syft](https://github.com/anchore/syft) | `brew install syft` | SPDX, CycloneDX |
| [tern](https://github.com/tern-tools/tern) | `pip install tern` | SPDX |
