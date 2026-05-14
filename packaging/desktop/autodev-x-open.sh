#!/usr/bin/env bash
# autodev-x 桌面入口（modeled after codex-fanout-open.sh）
# 双击桌面 .app → launcher stub → 此脚本 → Ghostty + tmux 三栏
#
# 启动日志：~/.autodev-x/.launcher.log（每次启动追加，便于排查"双击没反应/报错"）

LAUNCHER_LOG="$HOME/.autodev-x/.launcher.log"
mkdir -p "$(dirname "$LAUNCHER_LOG")"
{
  echo "==== $(date +%Y-%m-%dT%H:%M:%S%z) launcher start ===="
  echo "  args: $*"
  echo "  PATH head: ${PATH%%:*}"
  echo "  HOME: $HOME"
} >> "$LAUNCHER_LOG"

# Locate tmux — check common Homebrew paths then fallback to PATH
if [ -x "/opt/homebrew/opt/tmux/bin/tmux" ]; then
    TMUX="/opt/homebrew/opt/tmux/bin/tmux"
elif [ -x "/usr/local/opt/tmux/bin/tmux" ]; then
    TMUX="/usr/local/opt/tmux/bin/tmux"
elif command -v tmux &>/dev/null; then
    TMUX="$(command -v tmux)"
else
    TMUX="/opt/homebrew/opt/tmux/bin/tmux"  # will fail pre-check below
fi

SESSION="autodev"

# macOS 双击 .app 可能传 -psn_0_* 这种 Apple Event 参数 → 不能当 WORKDIR
case "${1:-}" in
  -psn_*|-*) WORKDIR="$HOME" ;;
  "") WORKDIR="$HOME" ;;
  *)  WORKDIR="$1" ;;
esac
echo "  WORKDIR resolved: $WORKDIR" >> "$LAUNCHER_LOG"

# 预检：tmux 和 Ghostty 都得在
for bin in "$TMUX" /Applications/Ghostty.app; do
  if [ ! -e "$bin" ]; then
    echo "ERROR: $bin not found" | tee -a "$LAUNCHER_LOG" >&2
    osascript -e "display alert \"autodev-x 启动失败\" message \"找不到 $bin，请检查安装。\" as critical" 2>/dev/null
    exit 1
  fi
done

# 横幅写文件（避免 send-keys 多行转义陷阱）
BANNER_FILE="$HOME/.autodev-x/.banner.txt"
mkdir -p "$(dirname "$BANNER_FILE")"
cat > "$BANNER_FILE" <<'BANNER'
🤖 autodev-x (AI software factory)
────────────────────────────────────────
Main:
  autodev scan --repo-path .
  autodev deliver-project --project-brief ./brief.md --mode dry-run
  autodev run-issue --issue-file ./issue.md
  autodev fix-bug --bug "<text>"
  autodev roundtable --topic "..." --skills "architecture,security,perf"

Servers:
  autodev mcp-serve              # stdio JSON-RPC (Cursor / Claude Code)
  autodev a2a-serve --port 8421  # HTTP A2A server

A2A:
  autodev a2a-register --endpoint http://...
  autodev a2a-call --skill scan --task-json '...'

Reports:
  autodev report --run-id <id>
  autodev replay --run-id <id> --from-stage architecture
────────────────────────────────────────
BANNER

# 若 session 已存在直接 attach（保留正在跑的 autodev）
if ! "$TMUX" has-session -t "$SESSION" 2>/dev/null; then
    # pane 0 (left)：autodev CLI — banner + bash prompt
    P0=$("$TMUX" new-session -d -s "$SESSION" -n "autodev" -c "$WORKDIR" -PF '#{pane_id}')
    "$TMUX" select-pane -t "$P0" -T "🤖 autodev"
    "$TMUX" send-keys -t "$P0" \
        "clear; cat \"$BANNER_FILE\"; echo; echo '  autodev REPL ready — run any command above.'; echo" Enter

    # pane 1 (top-right)：watch runs directory
    P1=$("$TMUX" split-window -h -t "$P0" -c "$WORKDIR" -PF '#{pane_id}')
    "$TMUX" select-pane -t "$P1" -T "📂 Runs"
    "$TMUX" send-keys -t "$P1" \
        "clear; echo '📂 .dev-factory/runs/ (refreshes every 5s)'; echo; watch -n 5 'ls -lat .dev-factory/runs/ 2>/dev/null | head'" Enter

    # pane 2 (bottom-right)：tail autodev logs
    P2=$("$TMUX" split-window -v -t "$P1" -c "$WORKDIR" -PF '#{pane_id}')
    "$TMUX" select-pane -t "$P2" -T "📋 Logs"
    "$TMUX" send-keys -t "$P2" \
        "clear; echo '📋 autodev log tail'; echo; tail -F /tmp/autodev-*.log 2>/dev/null || echo '(no autodev logs yet — will appear when autodev runs)'" Enter

    # set layout and focus pane 0
    WIN=$("$TMUX" display-message -p -t "$P0" '#{window_id}')
    "$TMUX" select-layout -t "$WIN" main-vertical 2>/dev/null
    "$TMUX" select-pane -t "$P0"
fi

echo "  attaching to session $SESSION" >> "$LAUNCHER_LOG"

# 打开 Ghostty 并 attach
open -na Ghostty.app --args \
    --title="autodev-x" \
    -e "$TMUX" attach-session -t "$SESSION" 2>>"$LAUNCHER_LOG"

echo "==== launcher done ====" >> "$LAUNCHER_LOG"
