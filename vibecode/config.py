"""Project configuration loading and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class ProjectConfig:
    project_id: str
    project_name: str
    root: Path
    include: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)
    protected_paths: List[str] = field(default_factory=list)
    risk_rules: List[str] = field(default_factory=list)
    required_checks: List[str] = field(default_factory=list)


def load_config(vibecode_dir: Path) -> ProjectConfig:
    """Load and validate .vibecode/project.yaml.

    Raises FileNotFoundError if project.yaml is absent.
    Raises NotImplementedError until task 04 is implemented.
    """
    config_path = vibecode_dir / "project.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"project.yaml not found: {config_path}")
    # Full YAML loading implemented in task 04.
    raise NotImplementedError("Config loading is implemented in task 04.")
