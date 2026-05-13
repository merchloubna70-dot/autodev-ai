# Claude Code CLI Adapter

`executors/claude_code_executor.py` is the only module that may invoke
`claude`.

- Config: `ClaudeCodeExecutorConfig` (binary, command_template, timeout,
  allowed_tools, disallowed_patterns).
- Default template: `claude --print {prompt}`. Override with
  `FACTORY_CLAUDE_CMD` or by passing a custom config.
- Versions of Claude Code that don't accept a particular flag are
  surfaced as `error_type=unsupported_cli_args` (not a crash).
- Prompt safety: every prompt gets the standard boundary block; the
  adapter also rejects prompts containing disallowed patterns
  (`rm -rf`, `sudo`, `cat .env`, etc.).
- Missing CLI ⇒ `error_type=cli_missing`. Router substitutes
  `MockClaudeExecutor` when `allow_mock=True`.
