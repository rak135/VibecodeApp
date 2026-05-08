# Vibecode — Quickstart Guide

This guide walks a new developer through installing Vibecode, creating an architecture map
for any local repository, and inspecting the generated output.

---

## What Vibecode can do (current scope)

- **`init`** — bootstrap a `.vibecode/` project layer in any repository
- **`index`** — scan files; produce a file inventory, symbol map, dependency map, test map, entrypoints list, risk map, and a compact repo-tree
- **`validate`** — check that all generated artifacts are internally consistent and that human-maintained files are in place
- **`map`** — print a one-page project summary (file counts, languages, symbols, tests, high-risk files) from the last index run
- **`context`** — generate a task-scoped `.vibecode/current/context_pack.md` ready to be pasted as agent context
- **`export-agents`** — write `AGENTS.md` (and `.vibecode/generated/AGENTS.generated.md`) with pre-edit and post-edit agent instructions

## What Vibecode cannot do yet

The following are **explicitly out of scope** for this release:

| Not available yet | Why deferred |
|---|---|
| Launching OpenCode or any other coding agent | Agent runtime work begins after the map and context pack are verified |
| Calling any LLM or AI API | This release is fully deterministic and offline |
| MCP server | Depends on a stable index |
| GUI | CLI-first by design |
| Auto-commit or auto-approve | Dangerous without a validated, stable index |

> **Note:** OpenCode prompt export (`--platform opencode`) prepares a file you can pass
> to an external agent yourself. Vibecode does **not** launch OpenCode.
> OpenCode runtime integration is a future phase.

---

## Local install

### Prerequisites

- Python 3.10 or newer
- Git (recommended — used for accurate file lists via `git ls-files`)

### Install from source

```powershell
# From the VibecodeApp repository root
python -m pip install -e .
```

### Verify

```powershell
python -m vibecode.cli --help
```

Expected output starts with:

```
usage: vibecode [-h] [--version] COMMAND ...
Local repository architecture map and context-pack CLI.
```

You can also invoke the installed entry-point directly once the package is on PATH:

```powershell
vibecode --help
```

### Run the test suite

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m pytest -p no:cacheprovider
```

---

## Quickstart scenario

The following example uses `C:\path\to\example-repo` as a placeholder. Substitute the
real path to any Git repository on your machine (or an empty directory).

### Step 1 — init

Create the `.vibecode/` project layer:

```powershell
python -m vibecode.cli init C:\path\to\example-repo --id example_repo
```

Flags:

| Flag | Default | Purpose |
|---|---|---|
| `--id` | directory name | Machine-readable project identifier used in generated artifacts |
| `--name` | directory name | Human-readable project name written into `project.yaml` |
| `--force` | off | Overwrite existing **human-maintained** files (safe to skip on first run) |

After `init`, the following files are created. Files marked **human-maintained** are yours
to edit and are never overwritten without `--force`:

```
C:\path\to\example-repo\
└── .vibecode\
    ├── project.yaml                     ← human-maintained: edit to add/remove include patterns
    ├── architecture\
    │   ├── OVERVIEW.md                  ← human-maintained: describe the project
    │   ├── INVARIANTS.md                ← human-maintained: non-negotiable architectural rules
    │   ├── STRUCTURE.md                 ← human-maintained: directory conventions
    │   ├── MODULE_BOUNDARIES.md         ← human-maintained: module responsibilities
    │   ├── PROTECTED_AREAS.md           ← human-maintained: sensitive paths
    │   └── DATA_FLOW.md                 ← human-maintained: how data moves through the system
    ├── checks\
    │   └── required_checks.yaml         ← human-maintained: checks the agent must run
    ├── handoff\
    │   ├── NOW.md                       ← human-maintained: current work in progress
    │   ├── NEXT.md                      ← human-maintained: queued work
    │   └── BLOCKERS.md                  ← human-maintained: current blockers
    ├── history\
    │   └── README.md                    ← human-maintained: index of significant changes
    ├── index\                           ← generated (do not edit)
    ├── current\                         ← generated (do not edit)
    └── logs\                            ← generated (do not edit)
```

### Step 2 — index

Scan the repository and write all generated indexes:

```powershell
python -m vibecode.cli index C:\path\to\example-repo
```

What `index` writes under `.vibecode\index\`:

| File | Contents |
|---|---|
| `file_inventory.json` | Every indexed file with language, role, and risk level |
| `symbol_map.json` | Functions and classes extracted from Python and TypeScript files |
| `dependency_map.json` | Lightweight import-edge map between files |
| `test_map.json` | Source-to-test file associations and required checks |
| `entrypoints.md` | CLI scripts, backend/frontend entry files, runtime config |
| `risky_files.md` | Files flagged as high-risk or protected |
| `repo_tree.generated.md` | Compact text tree of the indexed file set |

A run record is written to `.vibecode\logs\index_runs\<timestamp>.json` and a summary
is written to `.vibecode\current\last_index.json`.

**Expected warnings** on a fresh `init` — architecture template files still contain the
`<!-- vibecode:unfilled -->` marker. Fill in the templates and re-run `index` to clear them.

### Step 3 — validate

Check that all artifacts are consistent and required files are present:

```powershell
python -m vibecode.cli validate C:\path\to\example-repo
```

Each check prints `OK`, `WARN`, or `ERROR`. A `WARN` on the invariants file means the
architecture templates have not been filled in yet; this is expected on a fresh project.

### Step 4 — map

Print a one-page summary of the last index run:

```powershell
python -m vibecode.cli map C:\path\to\example-repo
```

Example output:

```
Project:     example-repo  (id: example_repo)
Root:        C:/path/to/example-repo
Languages:   python, typescript
Files:       42
Symbols:     138
Tests:       17
High-risk:   5
Entrypoints: 3
Indexed:     2026-05-08 12:00:00 UTC
Warnings:    none
```

### Step 5 — context

Generate a task-scoped context pack for a coding agent:

```powershell
python -m vibecode.cli context "Add rate limiting to the auth endpoint" --repo C:\path\to\example-repo
```

This writes `.vibecode\current\context_pack.md`. Inspect it:

```powershell
Get-Content C:\path\to\example-repo\.vibecode\current\context_pack.md
```

The context pack contains:

- **Current task** — the task description you passed in
- **Project summary** — name, id, root
- **Must preserve / invariants** — bullets from `INVARIANTS.md`
- **Relevant architecture** — excerpts from `architecture/*.md`
- **Relevant files with reasons** — scored file list with risk notes
- **Generated index status** — what was indexed and when
- **Required checks** — from `required_checks.yaml` and `test_map.json`
- **Risky / protected files** — files requiring confirmation before editing
- **Handoff** — current `NOW.md` content
- **Working rule** — minimal-change reminder

The pack is automatically truncated to ~32 000 characters if the repository is large;
lower-priority sections are dropped first and a notice is added.

Alternative forms of the `context` command:

```powershell
# PRD-style: repo root as positional, task as --task
python -m vibecode.cli context C:\path\to\example-repo --task "Add rate limiting to the auth endpoint"
```

### Step 6 — OpenCode prompt export

Wrap the context pack in OpenCode-compatible pre/post-edit instructions:

```powershell
python -m vibecode.cli context "Add rate limiting to the auth endpoint" --repo C:\path\to\example-repo --platform opencode
```

This writes two files:

| File | Purpose |
|---|---|
| `.vibecode\current\context_pack.md` | Raw context pack (always written) |
| `.vibecode\current\opencode_prompt.md` | OpenCode wrapper with pre/post-edit instructions |

Inspect the prompt:

```powershell
Get-Content C:\path\to\example-repo\.vibecode\current\opencode_prompt.md
```

> **This command does not launch OpenCode.** It only writes the file. Passing the file to
> an external agent session is a manual step for now. Automated OpenCode integration is a
> planned future phase.

### Step 7 — export-agents (optional)

Write `AGENTS.md` agent instructions to the repository root:

```powershell
python -m vibecode.cli export-agents C:\path\to\example-repo
```

This writes:
- `AGENTS.md` in the repository root (created if absent; updated if Vibecode-managed; skipped if externally managed unless `--force` is given)
- `.vibecode\generated\AGENTS.generated.md` — always updated

---

## Inspecting output files

All generated files are plain JSON or Markdown. Use standard tools to read them.

### File inventory

```powershell
Get-Content C:\path\to\example-repo\.vibecode\index\file_inventory.json | python -m json.tool | Select-Object -First 40
```

Each entry includes `path`, `language`, `role`, `size_bytes`, and `risk_level`.

### Symbol map

```powershell
Get-Content C:\path\to\example-repo\.vibecode\index\symbol_map.json | python -m json.tool | Select-Object -First 40
```

### Repo tree

```powershell
Get-Content C:\path\to\example-repo\.vibecode\index\repo_tree.generated.md
```

### Last index summary

```powershell
Get-Content C:\path\to\example-repo\.vibecode\current\last_index.json | python -m json.tool
```

### Run log

```powershell
Get-ChildItem C:\path\to\example-repo\.vibecode\logs\index_runs\ | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Get-Content
```

---

## `.vibecode/` structure reference

```
.vibecode/
├── project.yaml               ← project config (include/exclude patterns, protected paths)
│
├── architecture/              ← HUMAN-MAINTAINED; committed to version control
│   ├── OVERVIEW.md            ← project purpose and control-layer role
│   ├── INVARIANTS.md          ← non-negotiable rules agents must respect
│   ├── STRUCTURE.md           ← top-level directory conventions
│   ├── MODULE_BOUNDARIES.md   ← module responsibilities and allowed dependencies
│   ├── PROTECTED_AREAS.md     ← sensitive paths requiring extra review
│   └── DATA_FLOW.md           ← how data moves between components
│
├── checks/                    ← HUMAN-MAINTAINED; committed to version control
│   └── required_checks.yaml   ← checks an agent must run before declaring work complete
│
├── handoff/                   ← HUMAN-MAINTAINED; committed to version control
│   ├── NOW.md                 ← what is being worked on right now
│   ├── NEXT.md                ← queued work
│   └── BLOCKERS.md            ← current blockers
│
├── history/                   ← HUMAN-MAINTAINED; committed to version control
│   └── README.md              ← index of significant changes and decisions
│
├── index/                     ← GENERATED; regenerated by `vibecode index`
│   ├── file_inventory.json
│   ├── symbol_map.json
│   ├── dependency_map.json
│   ├── test_map.json
│   ├── entrypoints.md
│   ├── risky_files.md
│   └── repo_tree.generated.md
│
├── current/                   ← GENERATED; session/runtime output
│   ├── context_pack.md        ← current task context pack
│   ├── opencode_prompt.md     ← OpenCode wrapper (only when --platform opencode used)
│   └── last_index.json        ← summary of the last index run
│
├── generated/                 ← GENERATED; derived from human-maintained files
│   └── AGENTS.generated.md
│
└── logs/
    └── index_runs/            ← GENERATED; per-run records and warnings
        └── <timestamp>.json
```

### Human-maintained vs generated — the rule

> If a file can be regenerated from source code and human-maintained docs, it is **generated**.
> If a future agent must know it after cloning the repository, it should be **committed**.

**Commit** (human-maintained):
- `.vibecode/project.yaml`
- `.vibecode/architecture/*.md`
- `.vibecode/checks/*.yaml`
- `.vibecode/handoff/*.md`
- `.vibecode/history/README.md`

**Do not commit** (generated — add to `.gitignore`):
- `.vibecode/index/*.generated.*`
- `.vibecode/current/*`
- `.vibecode/generated/*`
- `.vibecode/logs/*`

---

## Next steps after the quickstart

1. Fill in the six architecture template files under `.vibecode/architecture/`. Remove the
   `<!-- vibecode:unfilled -->` marker from each file once it contains project-specific facts.
2. Edit `.vibecode/checks/required_checks.yaml` to match your actual test and lint commands.
3. Update `.vibecode/handoff/NOW.md` before each agent session.
4. Re-run `vibecode index` whenever repository structure changes significantly.
5. Re-run `vibecode context` to refresh the context pack before each agent task.
