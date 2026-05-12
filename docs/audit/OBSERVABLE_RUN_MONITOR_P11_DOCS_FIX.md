# Observable Run Monitor P11 Docs Fix

Generated: 2026-05-12

## Applied fixes

### 1. `runs list` examples use `--repo` flag (was positional path)

- **README.md:379** — `vibecode runs list C:\path\to\repo` → `vibecode runs list --repo C:\path\to\repo`
- **docs/QUICKSTART.md:433** — `runs list C:\path\to\example-repo` → `runs list --repo C:\path\to\example-repo`
- **docs/QUICKSTART.md:604** — same fix

Matches implemented `vibecode/cli.py:456-474` which requires `--repo` for `runs list`.

### 2. Monitor `--task` flag described as optional

- **README.md:339** — `--task` | `(required)` → `(optional at CLI)` with purpose updated to `Task description (recommended)`

Matches `vibecode/cli.py:172` and `vibecode/cli.py:406` which accept `default=""`.

### 3. Guard timing corrected (post-run only)

- **docs/QUICKSTART.md:34** — "before and after the run" → "after the run"

Matches `vibecode/run.py:744-758` where guard runs under "Post-run quality checks" after agent exits.

### 4. `metadata.json` added to run artifact lists

- **README.md:362** — added `metadata.json` entry in session artifact tree
- **docs/QUICKSTART.md:418** — same
- **docs/QUICKSTART.md:617** — added to prose list of session files
- **docs/QUICKSTART.md:670** — added to `.vibecode/` structure reference

Described as "platform metadata (fallback artifact, may be absent)" matching `vibecode/run.py:170-208` and `vibecode/show_run.py:69-71`.

## Files changed

- `README.md`
- `docs/QUICKSTART.md`

## Checks run

No source files were modified — only documentation text in README.md and docs/QUICKSTART.md.
