# Codex CLI Adapter

`executors/codex_cli_executor.py` is the only module that may invoke
`codex`. Everything else routes through `ExecutorRouter`.

- Config: `CodexCliExecutorConfig` (binary, command_template, timeout).
- Default template: `codex exec --skip-git-repo-check {prompt}`.
- The adapter never uses `shell=True`. The rendered command is `shlex.split`
  before `subprocess.run`.
- Prompt safety: every prompt is appended with a hard-coded safety boundary
  forbidding `.env`, `rm -rf`, scope expansion, fabricated passes.
- If `codex` is not installed: returns `error_type=cli_missing` and the
  router can substitute `MockCodexExecutor` when `allow_mock=True`.
