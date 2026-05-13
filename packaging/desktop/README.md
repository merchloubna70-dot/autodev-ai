# autodev-ai macOS Desktop Launcher

Double-click `autodev-ai.app` on your Desktop to open a Ghostty window with a tmux 3-pane layout for the autodev-ai AI software factory.

## Prerequisites

| Dependency | Install |
|---|---|
| [Ghostty](https://ghostty.org/) | Download `.dmg` from ghostty.org or `brew install --cask ghostty` |
| [tmux](https://github.com/tmux/tmux) | `brew install tmux` |
| autodev-ai Python package | `pip install autodev-ai` or install from source with `.venv/` |

## Installation

Run once from the project root:

```bash
bash packaging/desktop/install.sh
```

This script:
1. Copies `autodev-ai.app` → `~/Desktop/`
2. Copies `autodev-ai-open.sh` → `~/bin/`
3. `chmod +x` both files
4. Strips the macOS quarantine flag so first launch skips the Gatekeeper "unidentified developer" warning

## Pane Layout

```
┌─────────────────────┬──────────────────┐
│                     │  📂 Runs         │
│  🤖 autodev         │  watch runs dir  │
│  REPL + banner      ├──────────────────┤
│                     │  📋 Logs         │
│                     │  tail -F logs    │
└─────────────────────┴──────────────────┘
```

- **Pane 0 (left):** autodev CLI with command banner + bash prompt
- **Pane 1 (top-right):** `watch -n 5 'ls -lat .dev-factory/runs/'` — live run listing
- **Pane 2 (bottom-right):** `tail -F /tmp/autodev-*.log` — live log tail

## Customizing Without Re-signing

The `.app` launcher stub immediately delegates to `~/bin/autodev-ai-open.sh`. Edit that file to change pane contents, session name, or banner — no code signing needed.

## Common Issues

### "tmux: command not found" / alert on launch
Install tmux: `brew install tmux`

Ghostty must also be installed at `/Applications/Ghostty.app`.

### "找不到 ~/bin/autodev-ai-open.sh"
Run `bash packaging/desktop/install.sh` from the project root first.

### Double-click does nothing / "unidentified developer" warning
Run step 5 of install.sh manually:
```bash
xattr -dr com.apple.quarantine ~/Desktop/autodev-ai.app
```

### Re-launch attaches to existing session
This is by design — the tmux session is named `autodev` and reused. Kill it with `tmux kill-session -t autodev` to start fresh.

### Launcher log
Diagnostic log is written to `~/.autodev-ai/.launcher.log` on every launch.

## AppIcon

`AppIcon.icns` is copied from the existing `自动化编程.app` bundle if available at install time. If it is missing, the app launches without a custom icon (macOS shows a generic app icon).
