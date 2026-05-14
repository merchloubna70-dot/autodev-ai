import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Keep tests offline & deterministic.
os.environ.setdefault("FACTORY_LOG", "WARNING")
# Force the executor router to substitute mock executors so tests never call
# real `codex` / `claude` CLIs even when they happen to be installed.
os.environ.setdefault("FACTORY_FORCE_MOCK", "1")
# Allow A2AHttpTransport to connect to localhost in integration tests that
# spin up fake servers on 127.0.0.1.  Production code never sets this env var.
os.environ.setdefault("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", "1")
