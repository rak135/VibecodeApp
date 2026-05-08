"""End-to-end test: init → index → context for a realistic task.

Scenario
--------
1. Create a temporary fixture repository with a TypeScript/React screen, its
   test file, a high-risk matching module, and a node_modules directory that
   must not appear in the context pack.
2. Run ``vibecode init`` to scaffold ``.vibecode/``.
3. Adjust ``project.yaml`` protected_paths to include ``engine/matching.py``
   and replace ``INVARIANTS.md`` with project-specific invariants.
4. Run ``vibecode index`` against the fixture.
5. Run ``vibecode context`` for the task
   "Update context panel copy. Do not change matching algorithms."
6. Assert the generated ``context_pack.md`` contains the expected content.

Acceptance criteria
-------------------
- Test passes repeatedly.
- Does not require OpenCode or any external service.
- Verifies real files written under ``.vibecode/``.
"""

from __future__ import annotations

from pathlib import Path

from vibecode.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# E2E test
# ---------------------------------------------------------------------------


def test_e2e_context_panel_copy_task(tmp_path):
    """Full init → index → context flow; verifies .vibecode/ artifacts."""

    task = "Update context panel copy. Do not change matching algorithms."

    # ------------------------------------------------------------------ #
    # 1. Build a minimal fixture repository                               #
    # ------------------------------------------------------------------ #

    _write(
        tmp_path / "frontend" / "screens" / "ContextPanel.tsx",
        "import React from 'react';\n\n"
        "interface ContextPanelProps {\n"
        "  copy: string;\n"
        "}\n\n"
        "export function ContextPanel({ copy }: ContextPanelProps): JSX.Element {\n"
        "  return <div className='context-panel'><p>{copy}</p></div>;\n"
        "}\n\n"
        "export default ContextPanel;\n",
    )

    _write(
        tmp_path / "frontend" / "screens" / "ContextPanel.test.tsx",
        "import { render } from '@testing-library/react';\n"
        "import { ContextPanel } from './ContextPanel';\n\n"
        "describe('ContextPanel', () => {\n"
        "  it('renders copy text', () => {\n"
        "    const { getByText } = render(<ContextPanel copy='Hello world' />);\n"
        "    expect(getByText('Hello world')).toBeTruthy();\n"
        "  });\n"
        "});\n",
    )

    _write(
        tmp_path / "engine" / "matching.py",
        '"""Matching engine – high-risk core logic."""\n\n'
        "from __future__ import annotations\n\n\n"
        "def match_candidates(query: str, candidates: list[str]) -> list[str]:\n"
        "    q = query.lower()\n"
        "    return [c for c in candidates if q in c.lower()]\n\n\n"
        "class MatchingEngine:\n"
        "    def rank(self, query: str, candidates: list[str]) -> list[tuple[str, float]]:\n"
        "        return [(m, 1.0) for m in match_candidates(query, candidates)]\n",
    )

    _write(
        tmp_path / "README.md",
        "# SampleApp\n\nA sample application.\n",
    )

    _write(
        tmp_path / "pyproject.toml",
        "[project]\nname = 'sampleapp'\nversion = '0.1.0'\n",
    )

    # node_modules must be excluded from the index and the context pack.
    _write(
        tmp_path / "node_modules" / "some-package" / "index.js",
        "// vendor code\nmodule.exports = {};\n",
    )

    # ------------------------------------------------------------------ #
    # 2. Run init                                                         #
    # ------------------------------------------------------------------ #

    rc = main(["init", str(tmp_path), "--id", "sampleapp", "--name", "SampleApp"])
    assert rc == 0, "vibecode init should succeed"

    # ------------------------------------------------------------------ #
    # 3. Adjust project.yaml and overwrite INVARIANTS.md                 #
    # ------------------------------------------------------------------ #

    project_yaml_path = tmp_path / ".vibecode" / "project.yaml"
    yaml_content = project_yaml_path.read_text(encoding="utf-8")
    # Prepend engine/matching.py to protected_paths so it is explicitly
    # marked protected in addition to the heuristic high-risk classification.
    yaml_content = yaml_content.replace(
        "protected_paths:\n",
        'protected_paths:\n  - "engine/matching.py"\n',
    )
    project_yaml_path.write_text(yaml_content, encoding="utf-8")

    # Replace the unfilled INVARIANTS.md template with real invariants.
    _write(
        tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md",
        "# SampleApp \u2013 Architectural Invariants\n\n"
        "- The matching algorithm in engine/matching.py must not be changed without review.\n"
        "- Context panel UI must remain purely presentational; do not couple it to business logic.\n"
        "- Vendor dependencies must not be tracked or indexed by vibecode.\n",
    )

    # ------------------------------------------------------------------ #
    # 4. Run index                                                        #
    # ------------------------------------------------------------------ #

    rc = main(["index", str(tmp_path)])
    assert rc == 0, "vibecode index should succeed (no validation errors)"

    # ------------------------------------------------------------------ #
    # 5. Verify generated index artifacts                                 #
    # ------------------------------------------------------------------ #

    vibecode_dir = tmp_path / ".vibecode"

    inventory_path = vibecode_dir / "index" / "file_inventory.json"
    assert inventory_path.exists(), "file_inventory.json must be created by index"

    last_index_path = vibecode_dir / "current" / "last_index.json"
    assert last_index_path.exists(), "last_index.json must be created by index"

    # ------------------------------------------------------------------ #
    # 6. Run context                                                      #
    # ------------------------------------------------------------------ #

    rc = main(["context", str(tmp_path), "--task", task])
    assert rc == 0, "vibecode context should succeed"

    # ------------------------------------------------------------------ #
    # 7. Verify context_pack.md                                          #
    # ------------------------------------------------------------------ #

    pack_path = vibecode_dir / "current" / "context_pack.md"
    assert pack_path.exists(), "context_pack.md must be written"
    content = pack_path.read_text(encoding="utf-8")

    # Task appears verbatim in the context pack.
    assert task in content, "context pack must contain the task description"

    # Must-preserve / invariants section is present with project invariants.
    assert "## Must preserve / invariants" in content
    assert "matching algorithm" in content, (
        "invariant about matching algorithm must appear in context pack"
    )

    # Relevant TSX screen and its test file are mentioned.
    assert "ContextPanel.tsx" in content, (
        "context pack must reference the relevant TSX screen"
    )
    assert "ContextPanel.test.tsx" in content, (
        "context pack must reference the TSX test file"
    )

    # engine/matching.py must appear as risky/protected.
    assert "engine/matching.py" in content, (
        "engine/matching.py must appear in the context pack"
    )
    assert "risk `high`" in content, (
        "engine/matching.py must be flagged as high-risk in the context pack"
    )

    # node_modules must not bleed into the context pack as a file reference.
    # File paths always include a path separator, so check for "node_modules/"
    # rather than the bare word (which might legitimately appear in prose).
    assert "node_modules/" not in content, (
        "node_modules paths must never appear in the context pack"
    )

    # ------------------------------------------------------------------ #
    # 8. opencode_prompt.md must NOT exist without --platform export     #
    # ------------------------------------------------------------------ #

    opencode_path = vibecode_dir / "current" / "opencode_prompt.md"
    assert not opencode_path.exists(), (
        "opencode_prompt.md must only be created when --platform opencode is used"
    )


def test_e2e_opencode_prompt_created_only_with_platform_flag(tmp_path):
    """opencode_prompt.md is written when --platform opencode is requested."""

    task = "Update context panel copy. Do not change matching algorithms."

    _write(
        tmp_path / ".vibecode" / "project.yaml",
        "# vibecode project configuration\n"
        "# schema: vibecode/project/v1\n"
        "project:\n"
        "  id: sampleapp\n"
        "  name: SampleApp\n"
        "  root: .\n"
        "indexing:\n"
        "  include: []\n"
        "  exclude: []\n"
        "protected_paths: []\n"
        "risk_rules: []\n",
    )
    _write(
        tmp_path / ".vibecode" / "architecture" / "INVARIANTS.md",
        "# SampleApp \u2013 Invariants\n\n"
        "- Do not modify the matching engine without review.\n",
    )
    _write(
        tmp_path / ".vibecode" / "index" / "file_inventory.json",
        '{"files": []}\n',
    )

    rc = main(["context", str(tmp_path), "--task", task, "--platform", "opencode"])
    assert rc == 0

    opencode_path = tmp_path / ".vibecode" / "current" / "opencode_prompt.md"
    assert opencode_path.exists(), "opencode_prompt.md must exist when --platform opencode is used"
    prompt = opencode_path.read_text(encoding="utf-8")
    assert task in prompt
    assert "Vibecode-controlled repository" in prompt
