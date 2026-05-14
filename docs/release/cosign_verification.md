# Container Image Verification with Cosign (Keyless / Sigstore)

Every `ghcr.io/merchloubna70-dot/autodev-x` image pushed on a version tag is
automatically signed using **keyless Sigstore signing** — no private key is
stored in the repository or CI environment.

## How it works

| Component | Role |
|-----------|------|
| **Fulcio** | Sigstore's certificate authority. Issues a short-lived X.509 cert tied to the GitHub Actions OIDC identity (`https://token.actions.githubusercontent.com`). |
| **Rekor** | Sigstore's transparency log. Stores an immutable, publicly auditable record of every signature. |
| **cosign** | CLI that requests the Fulcio cert, creates the signature, appends it to Rekor, and attaches the detached signature to the image manifest in GHCR. |

No long-lived private key is required. Trust is derived from GitHub's OIDC
token issued to the workflow run, and the signature is verifiable by anyone
with the `cosign` CLI.

## Verify an image (consumer)

Install cosign:

```bash
brew install cosign          # macOS
# or: https://docs.sigstore.dev/cosign/system_config/installation/
```

Verify a specific release:

```bash
cosign verify ghcr.io/merchloubna70-dot/autodev-x:v0.1.0a3 \
  --certificate-identity-regexp='https://github.com/merchloubna70-dot/autodev-x/.+' \
  --certificate-oidc-issuer=https://token.actions.githubusercontent.com
```

A successful verification prints the signing certificate metadata and exits 0.
Any tampered or unsigned image causes a non-zero exit.

## Admission controller integration

### Kyverno (Kubernetes policy engine)

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: verify-autodev-x-signature
spec:
  validationFailureAction: Enforce
  rules:
    - name: check-image-signature
      match:
        resources:
          kinds: [Pod]
      verifyImages:
        - imageReferences:
            - "ghcr.io/merchloubna70-dot/autodev-x:*"
          attestors:
            - entries:
                - keyless:
                    subject: "https://github.com/merchloubna70-dot/autodev-x/.+"
                    issuer: "https://token.actions.githubusercontent.com"
```

### Sigstore Policy Controller

```yaml
apiVersion: policy.sigstore.dev/v1beta1
kind: ClusterImagePolicy
metadata:
  name: autodev-x-keyless
spec:
  images:
    - glob: "ghcr.io/merchloubna70-dot/autodev-x**"
  authorities:
    - keyless:
        identities:
          - issuer: https://token.actions.githubusercontent.com
            subjectRegExp: 'https://github\.com/merchloubna70-dot/autodev-x/.+'
```

## Audit the Rekor log

```bash
# Lookup all log entries for a digest (no cosign install required):
rekor-cli search --artifact <digest>
```

Or browse <https://search.sigstore.dev> and search by image digest.
