# Usage

## Install

```
pip install -e ".[dev]"
pip install -e ".[crewai]"   # optional: real CrewAI runtime
```

## Issue mode

```bash
crewai-factory run-issue \
  --repo-path . \
  --issue-file ./issue.md \
  --languages python,rust,typescript \
  --mode dry-run \
  --executor auto \
  --allow-mock-executor true
```

To apply changes:

```bash
crewai-factory run-issue \
  --repo-path . \
  --issue-url https://github.com/org/repo/issues/123 \
  --languages python,rust,typescript \
  --mode apply \
  --executor auto \
  --allow-mock-executor false
```

## Project Delivery mode

```bash
crewai-factory deliver-project \
  --repo-path . \
  --project-brief ./project_brief.md \
  --languages python,rust,typescript \
  --mode dry-run \
  --executor auto

crewai-factory deliver-project \
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
crewai-factory classify-input --input ./brief.md
crewai-factory create-prd --project-brief ./brief.md --output .dev-factory/prd.md
crewai-factory plan-project --repo-path . --prd ./prd.md --languages python,rust
crewai-factory plan-milestones --repo-path . --prd ./prd.md --max-milestones 6
crewai-factory plan-tasks --repo-path . --milestone-id M1
```

## Per-milestone execution

```
crewai-factory execute-milestone \
  --run-id <run_id> \
  --milestone-id M2 \
  --mode apply \
  --executor auto \
  --concurrency 3

crewai-factory continue-run --run-id <run_id>
crewai-factory replay --run-id <run_id> --from-stage architecture
```

## Verification & delivery

```
crewai-factory scan --repo-path .
crewai-factory verify --run-id <run_id>
crewai-factory release-check --run-id <run_id>
crewai-factory report --run-id <run_id>
crewai-factory export-delivery --run-id <run_id> --output ./delivery_package
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
