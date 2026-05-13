# Usage

## Install

```
pip install -e ".[dev]"
pip install -e ".[crewai]"   # optional: real CrewAI runtime
```

## Issue mode

```bash
autodev run-issue \
  --repo-path . \
  --issue-file ./issue.md \
  --languages python,rust,typescript \
  --mode dry-run \
  --executor auto \
  --allow-mock-executor true
```

To apply changes:

```bash
autodev run-issue \
  --repo-path . \
  --issue-url https://github.com/org/repo/issues/123 \
  --languages python,rust,typescript \
  --mode apply \
  --executor auto \
  --allow-mock-executor false
```

## Project Delivery mode

```bash
autodev deliver-project \
  --repo-path . \
  --project-brief ./project_brief.md \
  --languages python,rust,typescript \
  --mode dry-run \
  --executor auto

autodev deliver-project \
  --repo-path ./new-project \
  --project-name "legal-agent-platform" \
  --project-brief ./brief.md \
  --from-scratch true \
  --languages python,typescript \
  --mode apply \
  --executor auto
```

## Planning

```
autodev classify-input --input ./brief.md
autodev create-prd --project-brief ./brief.md --output .dev-factory/prd.md
autodev plan-project --repo-path . --prd ./prd.md --languages python,rust
autodev plan-milestones --repo-path . --prd ./prd.md --max-milestones 6
autodev plan-tasks --repo-path . --milestone-id M1
```

## Per-milestone execution

```
autodev execute-milestone \
  --run-id <run_id> \
  --milestone-id M2 \
  --mode apply \
  --executor auto \
  --concurrency 3

autodev continue-run --run-id <run_id>
autodev replay --run-id <run_id> --from-stage architecture
```

## Verification & delivery

```
autodev scan --repo-path .
autodev verify --run-id <run_id>
autodev release-check --run-id <run_id>
autodev report --run-id <run_id>
autodev export-delivery --run-id <run_id> --output ./delivery_package
```

## Global flags

- `--executor auto | codex | claude-code`
- `--allow-mock-executor true | false`
- `--claude-timeout 900` / `--codex-timeout 600`
- `--concurrency 3`
- `--fail-fast / --no-fail-fast`
- `--continue-and-report / --no-continue-and-report`
- `--commit` (off by default)
- `--push` (off by default; ignored unless `--commit`)
- `--tag` (off by default)
