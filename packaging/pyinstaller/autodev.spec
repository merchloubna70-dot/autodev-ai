# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the `autodev` CLI binary.
# Generated for autodev-ai v0.1.0
#
# Build:
#   cd packaging/pyinstaller
#   bash build.sh
#
# The spec is re-runnable without manual intervention.

import sys
import os

# ---------------------------------------------------------------------------
# Locate the helper that enumerates all autodev.* submodules.
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(SPEC))  # noqa: F821 (SPEC is PyInstaller magic)
sys.path.insert(0, _HERE)
from _collect_hidden_imports import collect as _collect

block_cipher = None

# ---------------------------------------------------------------------------
# Hidden imports
# ---------------------------------------------------------------------------
# 1. All autodev submodules (dynamically discovered)
_autodev_modules = _collect()

# 2. Third-party packages that PyInstaller typically misses
_extra_hidden = [
    # typer / click
    "typer",
    "typer.main",
    "typer.models",
    "typer.params",
    "typer.utils",
    "click",
    "click.core",
    "click.decorators",
    "click.exceptions",
    "click.types",
    "click.utils",
    # pydantic v2
    "pydantic",
    "pydantic.v1",
    "pydantic_core",
    "pydantic.fields",
    "pydantic.main",
    "pydantic.validators",
    "pydantic.networks",
    "pydantic._internal",
    "pydantic._internal._model_construction",
    # pydantic-ai (optional, guard with try/except at runtime)
    "pydantic_ai",
    "pydantic_ai.models",
    # crewai (optional)
    "crewai",
    "crewai.agent",
    "crewai.crew",
    "crewai.task",
    # anthropic SDK
    "anthropic",
    "anthropic._client",
    "anthropic.types",
    # httpx (used by anthropic + a2a transport)
    "httpx",
    "httpx._client",
    "httpcore",
    # Standard library extras often missed
    "importlib.metadata",
    "importlib.resources",
    "importlib.abc",
    "email.mime.text",
    "email.mime.multipart",
    "logging.handlers",
    "concurrent.futures",
    "multiprocessing.pool",
    "multiprocessing.managers",
    "ctypes",
    "ctypes.util",
    "uuid",
    "json",
    "pathlib",
    "shutil",
    "tempfile",
    "subprocess",
    "threading",
    "asyncio",
    "asyncio.events",
    "asyncio.tasks",
    # MCP / JSON-RPC (mcp_server)
    "mcp",
    "mcp.server",
    # watchdog (used by _fs_observer)
    "watchdog",
    "watchdog.observers",
    "watchdog.events",
    # packaging utils
    "packaging",
    "packaging.version",
    "tomllib",
    "tomli",
]

hiddenimports = _autodev_modules + _extra_hidden

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    ["../../src/autodev/cli.py"],
    pathex=["../../src"],
    binaries=[],
    datas=[
        # Bundle any data files the package ships (e.g. py.typed marker,
        # templates, default configs).  Glob patterns are resolved relative
        # to the spec file location at build time.
        ("../../src/autodev", "autodev"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Packages to exclude to reduce binary size
    excludes=[
        "tkinter",
        "_tkinter",
        "Tkinter",
        "tk",
        "tcl",
        "sqlite3",
        "_sqlite3",
        "unittest",
        "xmlrpc",
        "xmlrpc.server",
        "xmlrpc.client",
        "doctest",
        "pdb",
        "profile",
        "cProfile",
        "difflib",
        "ftplib",
        "imaplib",
        "mailbox",
        "nntplib",
        "poplib",
        "smtpd",
        "telnetlib",
        "turtle",
        "turtledemo",
        "lib2to3",
        "distutils",
        "ensurepip",
        "venv",
        "test",
        "tests",
        "testing",
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "PIL",
        "PyQt5",
        "PyQt6",
        "wx",
        "gi",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)  # noqa: F821

# ---------------------------------------------------------------------------
# Single-file EXE
# ---------------------------------------------------------------------------
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="autodev",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,   # None = native arch; overridden per-arch in universal build
    codesign_identity=None,
    entitlements_file=None,
)
