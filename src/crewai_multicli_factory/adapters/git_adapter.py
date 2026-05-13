"""Git adapter — safe wrappers around `git`. No commit/push/tag unless told."""
from __future__ import annotations

from pathlib import Path

from ..executors.shell_executor import ShellExecutor


class GitAdapter:
    def __init__(self, repo_path: str):
        self.repo_path = str(Path(repo_path).resolve())
        self.sh = ShellExecutor(cwd=self.repo_path)

    def has_git(self) -> bool:
        return (Path(self.repo_path) / ".git").exists()

    def status(self) -> str:
        return self.sh.run("git status").stdout

    def diff(self) -> str:
        return self.sh.run("git diff").stdout

    def add(self, paths: list[str]) -> int:
        if not paths:
            return 0
        # use one call per path to avoid quoting issues
        for p in paths:
            r = self.sh.run(f"git add {p}")
            if r.exit_code != 0:
                return r.exit_code
        return 0

    def commit(self, message: str, *, enabled: bool) -> int:
        if not enabled:
            return 0
        # Avoid command injection — write message to a file, commit -F
        msg_file = Path(self.repo_path) / ".dev-factory" / "COMMIT_MSG.txt"
        msg_file.parent.mkdir(parents=True, exist_ok=True)
        msg_file.write_text(message, encoding="utf-8")
        return self.sh.run(f"git commit -F {msg_file}").exit_code

    def tag(self, name: str, *, enabled: bool) -> int:
        if not enabled:
            return 0
        return self.sh.run(f"git tag {name}").exit_code

    def push(self, remote: str = "origin", branch: str | None = None, dry_run: bool = False, enabled: bool = False) -> int:
        """Push to remote.  Disabled by default; never accepts --force."""
        assert remote != "--force" and (branch is None or branch != "--force"), "force-push is never allowed"
        if not enabled:
            return 0
        parts = ["git push"]
        if dry_run:
            parts.append("--dry-run")
        parts.append(remote)
        if branch:
            parts.append(branch)
        return self.sh.run(" ".join(parts)).exit_code
