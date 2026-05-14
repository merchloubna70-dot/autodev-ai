# Tutorial 02 — Rust Project Delivery

This tutorial delivers `examples/02-slug-rs` — a Rust base62 slug-generation
library — from brief to milestone artifacts using autodev.

**Time to complete:** ~5 minutes (with mock executor)

---

## About the example

`examples/02-slug-rs/brief.md` describes a Rust library crate (`slug-rs`) that:

- Encodes `u64` values as compact base62 strings (`12345` → `"3D7"`)
- Decodes slug strings back to `u64` (`"3D7"` → `Ok(12345)`)
- Ships a thin CLI binary with `encode` / `decode` subcommands
- Has zero external dependencies

---

## Step 1 — Prepare a working directory

```bash
mkdir -p /tmp/slug-rs-demo
```

---

## Step 2 — Deliver the project (dry-run with mock)

```bash
autodev deliver-project \
  --project-brief examples/02-slug-rs/brief.md \
  --from-scratch true \
  --languages rust \
  --mode dry-run \
  --executor auto \
  --allow-mock-executor true \
  --repo-path /tmp/slug-rs-demo
```

Expected output:

```
[autodev] --scale not given; will auto-infer from PRD/brief
run_id=20240514-150000-c3d4e5 mode=dry-run mock=True release=NotReleaseReady
```

---

## Step 3 — Explore artifacts

```bash
ls /tmp/slug-rs-demo/.dev-factory/runs/*/
```

Key Rust-specific artifacts:

| Path | Contents |
|------|----------|
| `product/prd.md` | PRD auto-generated from the Rust brief |
| `architecture/architecture.md` | Crate layout: `src/lib.rs`, `src/main.rs`, `src/error.rs` |
| `architecture/module_map.json` | Module map listing `encode`, `decode`, `SlugError` |
| `planning/milestones.json` | M1=scaffold, M2=core logic, M3=CLI+tests |
| `execution/executor_selection_*.json` | Router decisions per task |
| `delivery/README.generated.md` | README with `cargo add`, usage examples |

---

## How the router handles Rust

For a Rust project the `ExecutorRouter` applies the same task-type rules, but
the generated prompts include `--language rust` context so the executor writes
idiomatic Rust:

| Task | Selected backend | Reason |
|------|-----------------|--------|
| Scaffold `Cargo.toml` + `src/lib.rs` | Codex | Small mechanical write |
| Implement `encode` / `decode` logic | Codex | ≤5 files, low risk |
| Write unit tests (`#[cfg(test)]`) | Codex | Targeted additions |
| Architecture doc | Claude Code | Long-context reasoning preferred |

---

## Step 4 — Apply for real

If you have Codex CLI or Claude Code CLI installed:

```bash
autodev deliver-project \
  --project-brief examples/02-slug-rs/brief.md \
  --from-scratch true \
  --languages rust \
  --mode apply \
  --executor auto \
  --repo-path /tmp/slug-rs-demo
```

When mode is `apply` the executor physically writes files. After the run
completes you can build and test:

```bash
cd /tmp/slug-rs-demo
cargo build
cargo test
cargo run -- encode 12345   # prints: 3D7
cargo run -- decode 3D7     # prints: 12345
```

---

## Step 5 — Execute a specific milestone

For large projects you may want to run milestones individually:

```bash
# List milestones from a completed planning run
cat /tmp/slug-rs-demo/.dev-factory/runs/<run_id>/planning/milestones.json

# Execute milestone M2 with Claude Code
autodev execute-milestone \
  --run-id <run_id> \
  --milestone-id M2 \
  --executor claude-code \
  --allow-mock-executor true \
  --repo-path /tmp/slug-rs-demo
```

---

## Step 6 — Get the next suggested action

```bash
autodev next \
  --run-id <run_id> \
  --repo-path /tmp/slug-rs-demo
```

Example output:

```
NEXT: autodev execute-milestone --run-id ... --milestone-id M3 --executor codex
WHY:  M1 and M2 are complete; M3 (CLI binary + tests) is the remaining milestone.
CONFIDENCE: 0.92
EVIDENCE:
  .dev-factory/runs/.../planning/milestones.json
  .dev-factory/runs/.../execution/milestone_M2_results.json
```

---

## See also

- [Tutorial 01 — Bug-fix flow](01-bug-fix.md)
- [Tutorial 03 — Multi-CLI routing](03-multi-cli-routing.md)
- [Quickstart](../quickstart.md)
