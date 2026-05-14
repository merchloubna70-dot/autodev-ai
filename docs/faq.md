# Frequently Asked Questions

---

## 1. Does autodev actually call the Codex CLI / Claude Code CLI?

Yes — when both `--mode apply` and a real CLI binary are available. The
`ExecutorRouter` resolves the binary from `PATH` (or from `FACTORY_CODEX_BIN`
/ `FACTORY_CLAUDE_BIN` env vars) and invokes it as a subprocess.

The exact commands used:

- **Codex:** `codex exec --skip-git-repo-check {prompt}`
- **Claude Code:** `claude --print {prompt}`

Every invocation is logged in `.dev-factory/runs/<run_id>/execution/execution_calls.jsonl`.

---

## 2. What if I have no API key? (mock mode)

Pass `--allow-mock-executor true`. When the real CLI is not found, autodev
substitutes a deterministic mock that generates realistic-looking artifacts
without any network calls.

```bash
autodev deliver-project \
  --project-brief examples/01-mdlines/brief.md \
  --from-scratch true \
  --mode dry-run \
  --allow-mock-executor true \
  --repo-path /tmp/demo
```

Mock runs are safe for exploring the tool, CI pipelines, and documentation.
They are always tagged `mock_used=true` in audit records, so `release_check`
will return `NotReleaseReady` — mocks cannot produce real release evidence.

---

## 3. How do I use my own Anthropic Claude Max subscription?

The `claude` CLI (Claude Code) authenticates via the same OAuth session as
your Max subscription. Log in once:

```bash
claude auth login
```

Then autodev invokes `claude --print {prompt}` using your authenticated
session — no `ANTHROPIC_API_KEY` env var required.

If you want to use an API key instead:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Both paths work. The CLI takes precedence if both are set.

---

## 4. What is dry-run mode vs apply mode?

| Mode | Effect |
|------|--------|
| `--mode dry-run` (default) | Plans and records everything; executors run but file writes are withheld |
| `--mode apply` | Executors physically write files, run tests, and commit if `--commit` is set |

Start with `dry-run` to review artifacts before committing. Switch to `apply`
when you are confident in the plan.

---

## 5. Is it safe to run `--mode apply` on my production repo?

By default: safe, but conservative. The safety defaults are:

- `--commit false` — no Git commits unless you explicitly pass `--commit`
- `--push false` — no pushes unless `--push`
- `--tag false` — no tags unless `--tag`
- Shell executor blocks `rm -rf`, `sudo`, `chmod 777`, `cat .env`,
  `curl | bash`, and similar dangerous patterns in all modes

For an extra sandboxing layer use `SandboxedExecutor` (currently for advanced
users; configure via `FactoryConfig`).

---

## 6. What sandbox security does autodev provide?

Three layers:

1. **Shell allowlist** — `ShellExecutor` rejects commands matching known
   dangerous patterns before any subprocess is started.
2. **Mock fall-back** — when a CLI is unavailable and `allow_mock=true`,
   the mock executor is used instead of attempting risky operations.
3. **`SandboxedExecutor`** — wraps any executor call in an OS-level sandbox
   (macOS Sandbox, Linux seccomp, or no-op on unsupported platforms).

No executor can bypass the allowlist: business code cannot call `codex` or
`claude` directly.

---

## 7. How do I add a new agent?

1. Create `src/autodev/agents/my_agent.py` with a class that has:
   - `crewai_agent() -> crewai.Agent` — for live runs
   - `run(input: MyInput) -> MyOutput` — for direct / test calls

2. Add a Pydantic `MyInput` / `MyOutput` to `schemas.py`.

3. Wire the agent into the relevant flow in `flows/`.

4. Add a CLI command in `cli.py` if end-users need to invoke it directly.

5. Write tests in `tests/test_agents/` using the deterministic `.run()` method.

The existing agents in `src/autodev/agents/` are the best reference — start
with `agents/doc_writer.py` which is small and well-commented.

---

## 8. How do I run a single milestone instead of the whole project?

```bash
# 1. Run deliver-project to get a run_id with a completed plan
autodev deliver-project \
  --project-brief examples/02-slug-rs/brief.md \
  --from-scratch true \
  --repo-path /tmp/demo \
  --mode dry-run \
  --allow-mock-executor true

# 2. Get the run_id from the output, then execute just M2
autodev execute-milestone \
  --run-id 20240514-143012-a1b2c3 \
  --milestone-id M2 \
  --executor claude-code \
  --allow-mock-executor true \
  --repo-path /tmp/demo
```

---

## 9. How do I resume a failed run?

```bash
autodev continue-run \
  --run-id 20240514-143012-a1b2c3 \
  --repo-path /tmp/demo
```

`RunState` is written after every stage. `continue-run` rehydrates from disk
and picks up from the last successful stage.

---

## 10. What is the difference between `--executor codex`, `--executor claude`, and `--executor auto`?

- `codex` — forces all tasks to Codex CLI (fast, mechanical, small patches)
- `claude` — forces all tasks to Claude Code CLI (deep reasoning, large context)
- `auto` (default) — `ExecutorRouter` picks per task based on `task_type`,
  `risk_level`, and `files_affected`

See [Tutorial 03 — Multi-CLI routing](tutorials/03-multi-cli-routing.md) for
the full routing table.

---

## 11. How does roundtable party-mode work?

`autodev roundtable` recruits N independent agent personas (by skill token)
and runs each as a separate `claude --print` subprocess. All participants
receive the same topic. A synthesizer agent merges the outputs into a single
recommendation.

Set `FACTORY_FORCE_MOCK=1` to use deterministic mock agents with no API calls.

See [Tutorial 05 — Roundtable](tutorials/05-roundtable.md).

---

## 12. Can autodev create GitHub pull requests?

Yes. Pass `--commit --push` to commit and push changes, then:

```bash
autodev create-pr \
  --run-id <run_id> \
  --repo-path /tmp/demo
```

This calls `gh pr create` via the `adapters/github/` layer. The `gh` CLI
must be installed and authenticated.

---

## 13. What does `release_check = NotReleaseReady` mean?

It means one or more conditions prevented marking the run as production-ready:

- `dry-run` mode was used (no real code changes)
- Mock executor was used (`mock_used=true`)
- A quality gate or security gate failed

This is the expected and correct result for demos and CI test runs. Only a
`--mode apply` run with real CLIs, passing gates, and no mock usage can
produce `release_check = ReleaseReady`.

---

## 14. How do I use autodev with Claude Desktop (MCP)?

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "autodev": {
      "command": "autodev",
      "args": ["mcp-serve"]
    }
  }
}
```

Restart Claude Desktop. autodev's pipeline commands become callable tools in
any Claude conversation.

See [Tutorial 06 — MCP server](tutorials/06-mcp-server.md).

---

## 15. How do I integrate autodev with another AI agent over HTTP?

Start the A2A server:

```bash
autodev a2a-serve --port 8421 --bind 127.0.0.1
```

The server exposes an agent card at `GET /.well-known/agent.json` and accepts
tasks at `POST /tasks/send`. Any A2A-compatible client (or another autodev
instance) can call it:

```bash
autodev a2a-call \
  --endpoint http://127.0.0.1:8421 \
  --skill fix-bug \
  --task-json '{"text": "Fix the off-by-one in aggregate.py"}'
```

See [Tutorial 07 — A2A server](tutorials/07-a2a-server.md).
