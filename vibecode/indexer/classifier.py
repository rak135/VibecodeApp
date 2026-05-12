"""Language detection and file-role guessing for indexed files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

_EXT_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescriptreact",
    ".js": "javascript",
    ".jsx": "javascriptreact",
    ".md": "markdown",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
    ".cfg": "config",
    ".ini": "config",
    ".env": "config",
    ".sh": "script",
    ".bash": "script",
    ".zsh": "script",
    ".ps1": "script",
}


def detect_language(posix: str) -> str:
    """Return the language identifier for *posix* based on its file extension."""
    suffix = PurePosixPath(posix).suffix.lower()
    return _EXT_TO_LANGUAGE.get(suffix, "unknown")


# ---------------------------------------------------------------------------
# Config detection
# ---------------------------------------------------------------------------

_CONFIG_FILENAMES: frozenset[str] = frozenset({
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    ".eslintrc.json",
    ".prettierrc",
    ".babelrc",
    "Dockerfile",
    ".dockerignore",
    ".gitignore",
    ".gitattributes",
    "Makefile",
    "tox.ini",
    "pytest.ini",
    ".env",
    ".env.example",
    ".flake8",
    "mypy.ini",
})


def _is_config_file(posix: str) -> bool:
    """Return True if *posix* is a well-known configuration file."""
    name = PurePosixPath(posix).name
    return name in _CONFIG_FILENAMES or name.startswith("vite.config.")


# ---------------------------------------------------------------------------
# Test detection
# ---------------------------------------------------------------------------


def _is_test(posix: str) -> bool:
    """Return True if *posix* looks like a test file."""
    name = PurePosixPath(posix).name
    parts = posix.split("/")
    # tests/** directory
    if "tests" in parts[:-1]:
        return True
    # test_*.py or *_test.py
    if name.startswith("test_") and name.endswith(".py"):
        return True
    if name.endswith("_test.py"):
        return True
    # *.test.tsx / *.spec.tsx / *.test.ts / *.spec.ts / *.test.js / *.spec.js
    for ext in (".test.tsx", ".spec.tsx", ".test.ts", ".spec.ts", ".test.js", ".spec.js"):
        if name.endswith(ext):
            return True
    return False


# ---------------------------------------------------------------------------
# Doc detection
# ---------------------------------------------------------------------------


def _is_doc(posix: str) -> bool:
    """Return True if *posix* looks like a documentation file."""
    parts = posix.split("/")
    # docs/** directory
    if "docs" in parts[:-1]:
        return True
    # Any .md file (README, CHANGELOG, etc.)
    if PurePosixPath(posix).suffix.lower() == ".md":
        return True
    return False


# ---------------------------------------------------------------------------
# Role guessing
# ---------------------------------------------------------------------------

_FRONTEND_SCREEN_SEGMENTS: frozenset[str] = frozenset({"screens"})
_FRONTEND_COMPONENT_SEGMENTS: frozenset[str] = frozenset({"components"})
_ENGINE_SEGMENTS: frozenset[str] = frozenset({"engine"})
_API_SEGMENTS: frozenset[str] = frozenset({"api", "routes", "server"})
_GENERATED_DIRS: frozenset[str] = frozenset({
    "dist", "build", ".vibecode/index", "vibecode.egg-info", "__pycache__",
})
_SCRIPT_EXTENSIONS: frozenset[str] = frozenset({".sh", ".bash", ".zsh", ".ps1"})


def guess_role(posix: str) -> str:
    """Return a role string for the file at *posix*.

    Heuristics are applied from most-specific to most-general so that
    config filenames, tests, and docs are never mis-classified as API/engine.
    """
    parts = posix.split("/")
    suffix = PurePosixPath(posix).suffix.lower()

    if _is_config_file(posix):
        return "config"
    if _is_test(posix):
        return "test"
    if _is_doc(posix):
        return "doc"
    if _parts_contain(parts, _FRONTEND_SCREEN_SEGMENTS):
        return "frontend_screen"
    if _parts_contain(parts, _FRONTEND_COMPONENT_SEGMENTS):
        return "frontend_component"
    if _parts_contain(parts, _ENGINE_SEGMENTS):
        return "backend_engine"
    if _parts_contain(parts, _API_SEGMENTS):
        return "backend_api"
    if _is_generated(posix):
        return "generated"
    if suffix in _SCRIPT_EXTENSIONS:
        return "script"
    return "unknown"


def _parts_contain(parts: list[str], dirs: frozenset[str]) -> bool:
    """Return True if any directory component (not the filename) is in *dirs*."""
    return any(part in dirs for part in parts[:-1])


def _is_generated(posix: str) -> bool:
    """Return True for files that look like generated artefacts."""
    parts = posix.split("/")
    if any(p in {"dist", "build", "__pycache__"} for p in parts[:-1]):
        return True
    return PurePosixPath(posix).suffix.lower() in {".pyc", ".pyo"}


# ---------------------------------------------------------------------------
# Risk level
# ---------------------------------------------------------------------------

_ROLE_TO_RISK: dict[str, str] = {
    "backend_engine": "high",
    "backend_api": "high",
    "frontend_screen": "medium",
    "frontend_component": "medium",
    "script": "medium",
    "test": "low",
    "doc": "low",
    "config": "low",
    "generated": "low",
    "unknown": "low",
}


def compute_risk_level(role: str) -> str:
    """Return a risk level string for the given *role*."""
    return _ROLE_TO_RISK.get(role, "low")


# ---------------------------------------------------------------------------
# FileRecord
# ---------------------------------------------------------------------------


@dataclass
class FileRecord:
    """Enriched file entry with language, role, and risk metadata."""

    path: str
    language: str
    size_bytes: int
    role_guess: str
    is_test: bool
    is_config: bool
    is_doc: bool
    risk_level: str


def classify(path: str, size_bytes: int) -> FileRecord:
    """Return a :class:`FileRecord` for the file at *path*.

    All heuristics are deterministic; unknown file types never raise.
    """
    language = detect_language(path)
    role = guess_role(path)
    return FileRecord(
        path=path,
        language=language,
        size_bytes=size_bytes,
        role_guess=role,
        is_test=_is_test(path),
        is_config=_is_config_file(path),
        is_doc=_is_doc(path),
        risk_level=compute_risk_level(role),
    )
