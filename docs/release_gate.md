# Release Gate

`ReleaseGate.check(state)` returns `ReleaseReady`, `NotReleaseReady`, or
`Blocked`.

It is **not release-ready** if any of:

- a milestone has no successful ImplementationResult
- any QualityGate is `failed`
- VerificationReport is `failed`
- mock executor was used
- mode is `dry-run`
- no delivery_report present

It is **blocked** if SecurityReviewReport is `failed`.

Otherwise it is `ReleaseReady`. The reasons list documents every reason a
run did not graduate.
