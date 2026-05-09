"""Agent permission profiles for vibecode run workflows.

Permission profiles define what an agent is allowed to do during a run:
- safe:   read allow, grep/glob allow, edit ask, bash ask, generated files deny
- fast:   edit allow, bash ask, guard after run
- audit:  read only, no edit, no write
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Permission profile names and their default definitions.
# Each profile is a dict that can be serialized to JSON.
PROFILES: dict[str, dict[str, Any]] = {
    "safe": {
        "description": "Read allow; grep/glob allow; edit ask; bash ask; generated files deny.",
        "allows": ["read", "grep", "glob"],
        "prompts": ["edit", "bash"],
        "denies": ["write_generated", "write_runtime"],
    },
    "fast": {
        "description": "Edit allow; bash ask; guard after run.",
        "allows": ["read", "grep", "glob", "edit"],
        "prompts": ["bash"],
        "denies": ["write_generated", "write_runtime"],
        "post_run": ["guard", "check"],
    },
    "audit": {
        "description": "Read only; no edit; no write.",
        "allows": ["read", "grep", "glob"],
        "prompts": [],
        "denies": ["edit", "write", "write_generated", "write_runtime", "bash"],
    },
}


def all_profile_paths() -> list[str]:
    """Return relative paths for all known permission profile files."""
    return [profile_path(name) for name in PROFILES]


def profile_path(profile_name: str) -> str:
    """Return the relative path for a given profile name."""
    return f".vibecode/agents/{profile_name}.json"


def write_profile(
    repo_root: Path, profile_name: str, profile_data: dict[str, Any], *, force: bool = False
) -> bool:
    """Write a permission profile file.

    Returns True if the file was written (or overwritten with --force).
    Returns False if a human-maintained profile already exists and --force was not set.
    """
    rel = profile_path(profile_name)
    target = repo_root / Path(rel)
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() and not force:
        # Check if it's a default-generated profile we can safely overwrite.
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
            if existing == profile_data:
                return False  # Already up-to-date, no need to rewrite.
        except (json.JSONDecodeError, OSError):
            pass
        # File exists with custom content; don't overwrite.
        return False

    target.write_text(json.dumps(profile_data, indent=2) + "\n", encoding="utf-8")
    return True