# Vibecode — Quickstart Guide

This guide walks a new developer through installing Vibecode, creating an architecture map
for any local repository, and using the safe OpenCode workflow to run agent-assisted tasks.

---

## What Vibecode can do

- **`init`** — bootstrap a `.vibecode/` project layer in any repository
- **`index`** — scan files; produce a file inventory, symbol map, dependency map, test map, entrypoints list, risk map, and a compact repo-tree
- **`validate`** — check that all generated artifacts are internally consistent and that human-maintained files are in place
- **`map`** — print a one-page project summary (file counts, languages, symbols, tests, high-risk files) from the last index run
- **`context`** — generate a task-scoped `.vibecode/current/context_pack.md` ready to be pasted as agent context
- **`run-plan`** — assemble and inspect a full run plan without launching an agent (pre-flight check)
- **`run`** — execute the full agent loop: context generation, platform invocation, post-run guard/check/handoff
- **`guard`** — check git diff against guard rules (protected paths, generated files, architecture truth)
- **`check`** — run required checks from `.vibecode/checks/required_checks.yaml`
- **`handoff-check`** — validate handoff files (NOW/NEXT/BLOCKERS) and architecture-change recording
- **`export-agents`** — write `AGENTS.md` with pre-edit and post-edit agent instructions
- **`project add/use/list/remove/current`** — register and manage named projects in a local registry

## What Vibecode does not do

The following behaviors are **explicitly out of scope**:

- No custom coding agent runtime bundled with Vibecode — the `run` command invokes an external tool (e.g. OpenCode) that must be installed separately
- No LLM or AI API calls from Vibecode itself — all inference happens in the external tool
- No auto-commit or auto-approve — every agent edit is reviewed through guard checks before and after the run
- No GUI — CLI-first by design
- No MCP server

> **Note:** OpenCode prompt export (`--platform opencode`) prepares a file you can pass to an external agent manually.
> The `vibecode run` command can invoke OpenCode directly if it is on PATH, but this is still a **manual, user-initiated action** —
> Vibecode orchestrates the workflow, the external tool does the editing.
> Agent runtime integration is a supported workflow but requires OpenCode to be installed.

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

## Two workflows

Vibecode supports two complementary workflows. Use whichever fits the task.

### 1. Explicit-path workflow

Pass the repository root on the command line every time. No setup required.

```powershell
python -m vibecode.cli init   C:\path\to\repo --id my_repo
python -m vibecode.cli index  C:\path\to\repo
python -m vibecode.cli map    C:\path\to\repo
python -m vibecode.cli context "Update login flow" --repo C:\path\to\repo
python -m vibecode.cli run    C:\path\to\repo --task "Update login flow" --profile safe
```

### 2. Registry workflow

Register projects once by name, then omit the path in future commands.
The registry lives at `~/.vibecode/projects.yaml` — it is local machine state
and is never committed to version control.

```powershell
# Register (once per machine)
python -m vibecode.cli project add STOCKS C:\DATA\PROJECTS\STOCKS

# Set the active project
python -m vibecode.cli project use STOCKS

# Now path is optional — active project is used automatically
python -m vibecode.cli index
python -m vibecode.cli map
python -m vibecode.cli context "Update login flow"
python -m vibecode.cli run --task "Update login flow" --profile safe
```

Registry commands:

| Command | Action |
|---|---|
| `vibecode project add <name> <path>` | Register a project by name |
| `vibecode project use <name>` | Set the active project |
| `vibecode project list` | List all registered projects (`*` marks the active one) |
| `vibecode project current` | Show the currently active project name and path |
| `vibecode project remove <name>` | Remove a project from the registry |

Explicit repo paths always take priority over registry and default fallbacks.

Commands that use the registry when no path is given (``index``, ``map``,
``validate``, ``guard``, ``check``, ``handoff-check``, ``run``, ``context``):

1. Explicit ``--repo`` / positional argument — wins.
2. Active project from the registry — used when no explicit path is given.
3. If no active project exists, most commands **error** with
   ``No repository root given and no active project`` (run
   ``vibecode project use <name>`` first).  ``context`` is the exception:
   it falls back to ``.`` (current directory).

Commands that default to ``.`` and do **not** consult the registry:
``init``, ``run-plan``, ``export-agents``, ``history new``.

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

### Step 3 — check

Run the required checks defined in `.vibecode/checks/required_checks.yaml`:

```powershell
python -m vibecode.cli check C:\path\to\example-repo
```

Results are written to `.vibecode\current\check_results.json`. Each check prints `PASS`, `FAIL`, or `WARN`. A non-zero exit code indicates at least one required check failed.

### Step 4 — validate

Check that all artifacts are consistent and required files are present:

```powershell
python -m vibecode.cli validate C:\path\to\example-repo
```

Each check prints `OK`, `WARN`, or `ERROR`. A `WARN` on the invariants file means the
architecture templates have not been filled in yet; this is expected on a fresh project.

### Step 5 — map

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

### Step 6 — context

Generate a task-scoped context pack for a coding agent:

```powershell
python -m vibecode.cli context "Add rate limiting to the auth endpoint" --repo C:\path\to\example-repo
```

This writes `.vibecode\current\context_pack.md`, a task-specific runtime artifact.
To also export an OpenCode-compatible prompt wrapper, add `--platform opencode`:

```powershell
python -m vibecode.cli context "Add rate limiting to the auth endpoint" --repo C:\path\to\example-repo --platform opencode
```

This additionally writes `.vibecode\current\opencode_prompt.md` with pre-edit and post-edit instructions.
**Vibecode does not launch OpenCode** — passing the prompt to an external agent is a manual step.

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
lower-priority sections are dropped first and a notice is added. Generate a fresh context
pack for each agent task instead of relying on old `.vibecode\current\context_pack.md`
content.

Alternative forms of the `context` command:

```powershell
# PRD-style: repo root as positional, task as --task
python -m vibecode.cli context C:\path\to\example-repo --task "Add rate limiting to the auth endpoint"

# Registry workflow: no path needed when a project is active
python -m vibecode.cli context "Add rate limiting to the auth endpoint"
```

### Step 7 — run-plan (preview)

Before launching an agent, assemble and inspect a full run plan:

```powershell
python -m vibecode.cli run-plan C:\path\to\example-repo --task "Add rate limiting to the auth endpoint"
```

`run-plan` checks preconditions without making changes:

- Git working tree status (clean or dirty)
- Project config exists and is valid
- Index freshness (warns if stale or missing)
- OpenCode availability on PATH
- Permission profile resolution

It writes `.vibecode\current\run_plan.json` and prints a human-readable summary.
Errors must be resolved before proceeding with `run`.

### Step 8 — run (agent loop)

Execute the full safe agent loop:

```powershell
python -m vibecode.cli run C:\path\to\example-repo --task "Add rate limiting to the auth endpoint" --profile safe
```

`run` orchestrates the complete workflow:

1. Check git status (abort if dirty, unless `--allow-dirty`)
2. Generate or refresh the index if missing or stale (>5 min)
3. Generate the context pack and OpenCode prompt
4. Invoke the platform command (e.g. OpenCode) with the prompt on stdin
5. Capture stdout / stderr / exit code
6. Run post-run guard, required checks, and handoff validation
7. Write session metadata to `.vibecode/runs/<session_id>.json` and a summary

Permission profiles are **Vibecode-side advisory metadata**.  Vibecode validates
that the selected profile exists on disk and records it in run plans and session
metadata, but does **not** directly constrain OpenCode tool permissions.  Actual
OpenCode tool permissions are controlled separately through OpenCode configuration
(``opencode.json``, agent definitions, or ``OPENCODE_PERMISSION``).

| Profile | `allows` | `prompts` | `denies` | Use case |
|---|---|---|---|---|
| **safe** (default) | read, grep, glob | edit, bash | write_generated, write_runtime | Most workflows |
| **fast** | read, grep, glob, edit | bash | write_generated, write_runtime | Trusted edits; guard runs after |
| **audit** | read, grep, glob | (none) | edit, write, write_generated, write_runtime | Read-only inspection |

Flags:

| Flag | Default | Purpose |
|---|---|---|
| `--profile` | safe | Permission profile name |
| `--allow-dirty` | off | Allow running with uncommitted changes (warn only) |
| `--no-index` | off | Skip automatic index generation/refresh |

### Step 9 — post-run audit

After a `run` completes (or independently), inspect results:

**Guard checks** — verify no protected paths were modified without proper scope:

```powershell
python -m vibecode.cli guard C:\path\to\example-repo
```

Use `--strict` to treat warnings as hard failures.

**Required checks** — re-run the check suite on the post-run state:

```powershell
python -m vibecode.cli check C:\path\to\example-repo
```

**Handoff validation** — confirm handoff files are consistent with changes:

```powershell
python -m vibecode.cli handoff-check C:\path\to\example-repo [--json]
```

### Step 10 — export-agents (optional)

```powershell
python -m vibecode.cli export-agents C:\path\to\example-repo
```

This writes:
- root `AGENTS.md` — stable agent instruction for the repository; created if absent, updated if Vibecode-managed, and skipped if manual unless `--force` is given
- `.vibecode\generated\AGENTS.generated.md` — generated export output that is ignored and always updated

`export-agents` must not overwrite a manual root `AGENTS.md` without `--force`.
Future agents should read root `AGENTS.md`, then generate a task-specific
`.vibecode\current\context_pack.md` for each task.

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

### Check results

```powershell
Get-Content C:\path\to\example-repo\.vibecode\current\check_results.json | python -m json.tool
```

### Run log

```powershell
Get-ChildItem C:\path\to\example-repo\.vibecode\logs\index_runs\ | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Get-Content
```

### Run metadata

After a `vibecode run`, session metadata is written under `.vibecode\runs\<session_id>\summary.json`:

```powershell
Get-ChildItem C:\path\to\example-repo\.vibecode\runs\ -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Get-ChildItem | Get-Content
```

The summary includes overall status, agent exit code, guard results, check results, handoff results, and a diff summary of changes made during the run.

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
├── agents/                    ← HUMAN-MAINTAINED; committed to version control
│   ├── safe.json              ← safe profile: read & grep allowed, edit/bash ask, generated deny
│   ├── fast.json              ← fast profile: edit allowed, bash ask, guard after run
│   └── audit.json             ← audit profile: read-only, no edits, no writes
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
│   ├── last_index.json        ← summary of the last index run
│   └── check_results.json     ← results from the last `vibecode check` run
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
- `.vibecode/agents/*.json` ← choose the right profile for your security posture

> **Security note:** Sensitive or production projects should use the **audit**
> or **safe** profile. The **fast** profile allows edits without confirmation.
> Review `.vibecode/agents/*.json` and pick the right profile before running
> any agent-assisted workflow.

**Do not commit** (generated — add to `.gitignore`):
- `.vibecode/index/*.generated.*`
- `.vibecode/current/*`
- `.vibecode/generated/*`
- `.vibecode/logs/*`

**Registry files** (local machine state — never commit):
- `~/.vibecode/projects.yaml` — registered project names and paths
- `~/.vibecode/.active_project` — the currently active project name

---

## Next steps after the quickstart

1. Fill in the six architecture template files under `.vibecode/architecture/`. Remove the
   `<!-- vibecode:unfilled -->` marker from each file once it contains project-specific facts.
2. Edit `.vibecode/checks/required_checks.yaml` to match your actual test and lint commands.
3. Update `.vibecode/handoff/NOW.md` before each agent session.
4. Re-run `vibecode index` whenever repository structure changes significantly.
5. Re-run `vibecode context` to refresh the context pack before each agent task.
6. Use the safe OpenCode workflow:
   - `vibecode context "task" --repo . --platform opencode` to generate context + prompt
   - `vibecode run-plan . --task "task"` to pre-flight the run
   - `vibecode run . --task "task" --profile safe` to execute the agent loop
   - `vibecode guard .`, `vibecode check .`, `vibecode handoff-check .` for post-run audit
   - Review session metadata in `.vibecode/runs/<session_id>/summary.json`
7. For multi-repo setups, register each project once and switch with `vibecode project use`:
   - `vibecode project add STOCKS C:\DATA\PROJECTS\STOCKS`
   - `vibecode project use STOCKS`
   - `vibecode context "Add rate limiting"` (no path needed)
