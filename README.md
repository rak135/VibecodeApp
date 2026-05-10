<a id="readme-top"></a>

# VibecodeApp

VibecodeApp is a local repository control-layer CLI. Its job is to create a deterministic `.vibecode/` project layer that helps coding agents understand repository structure, important files, entrypoints, tests, dependencies, symbols, protected areas, required checks, handoff state, and current project rules before they edit code.

This repository is intentionally CLI-first. VibecodeApp does not edit code itself; `vibecode run` can orchestrate an external OpenCode process when explicitly invoked.

## Table of Contents

1. [About The Project](#about-the-project)
2. [Built With](#built-with)
3. [Getting Started](#getting-started)
4. [Usage](#usage)
5. [Status](#status)
6. [Contributing](#contributing)
7. [License](#license)
8. [Acknowledgments](#acknowledgments)

→ **[Full quickstart guide — docs/QUICKSTART.md](docs/QUICKSTART.md)**

## About The Project

VibecodeApp is meant to become the project control layer around agentic coding work. The Architecture Map Core focuses on:

- creating and maintaining `.vibecode/`
- scanning repositories safely
- generating file inventory, symbol, dependency, test, entrypoint, and risk maps
- preserving human-maintained architecture and handoff files
- validating generated artifacts
- generating task-scoped context packs and prompt export files
- enforcing guard/check/handoff requirements around external agent runs

Non-goals:

- no custom coding agent — VibecodeApp does not edit code itself; it prepares context, validates plans, and orchestrates external tools
- no GUI
- no MCP server
- no LLM API calls

See `docs/ARCHITECTURE_MAP_PRD.md` for desired behavior and `docs/ARCHITECTURE_MAP_STATUS.md` for implementation status.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Built With

- Python 3.10+
- PyYAML
- pytest
- setuptools

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Getting Started

### Prerequisites

- Python 3.10 or newer
- Git, recommended for tracked/untracked file detection

### Installation

From the repository root:

```powershell
python -m pip install -e .
```

Verify the CLI:

```powershell
python -m vibecode.cli --help
```

Run the test suite:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -p no:cacheprovider
```

Run the required checks:

```powershell
python -m vibecode.cli check .
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Usage

### Windows paths

All commands accept Windows-style paths with backslashes.  Paths are
normalised to forward-slash POSIX format internally, so JSON and Markdown
outputs are always portable and never contain broken backslash escaping.

```powershell
# Init, index, validate, and map all accept C:\... roots directly.
python -m vibecode.cli init   C:\path\to\example-repo --id example_repo
python -m vibecode.cli index  C:\path\to\example-repo
python -m vibecode.cli validate C:\path\to\example-repo
python -m vibecode.cli map    C:\path\to\example-repo

# Context pack using the --repo flag with a Windows path
python -m vibecode.cli context "Update login flow" --repo C:\path\to\example-repo
```

The generated JSON files (``file_inventory.json``, ``last_index.json``, etc.)
always use forward slashes in their ``root`` and ``path`` fields regardless of
the host OS.



### Explicit-path workflow

Every command can accept an explicit repository root on the command line:

```powershell
python -m vibecode.cli index  C:\path\to\example-repo
python -m vibecode.cli map    C:\path\to\example-repo
python -m vibecode.cli context "Update context panel copy" --repo C:\path\to\example-repo
python -m vibecode.cli run    C:\path\to\example-repo --task "Update context panel copy" --profile safe
```

This is the simplest way to get started and works without any prior setup.



### Registry workflow

If you work with multiple repositories, you can register them by name once and
then refer to them without typing the full path every time.  The registry is a
local file (``~/.vibecode/projects.yaml``) — it is **not** committed to any
repository and lives outside all project folders.

**1. Register a project:**

```powershell
python -m vibecode.cli project add STOCKS C:\DATA\PROJECTS\STOCKS
```

**2. Set the active project:**

```powershell
python -m vibecode.cli project use STOCKS
```

**3. Run commands without an explicit path** — they fall back to the active
project from the registry:

```powershell
python -m vibecode.cli index
python -m vibecode.cli map
python -m vibecode.cli context "Update login flow"
python -m vibecode.cli run --task "Update login flow" --profile safe
```

**Other registry commands:**

```powershell
python -m vibecode.cli project list       # Show all registered projects (* = active)
python -m vibecode.cli project current    # Show the currently active project
python -m vibecode.cli project remove STOCKS  # Unregister a project
```

Key points:

- The registry lives at ``~/.vibecode/projects.yaml`` (overridable via the
  ``VIBECODE_HOME`` environment variable).
- The active project is tracked in ``~/.vibecode/.active_project``, a plain
  text sidecar file.
- Registry state is local to your machine and is never committed to version
  control.
- Explicit repo paths always win — when you pass ``--repo`` or a positional
  path argument, the registry is never consulted.
- These commands use the active project as a fallback when no path is given:
  ``index``, ``map``, ``validate``, ``guard``, ``check``, ``handoff-check``,
  ``run``, ``context``.  If no active project exists, they **error** with a
  clear message (except ``context``, which falls back to ``.``).
- These commands default to ``.`` (current directory) and do **not** consult
  the registry: ``init``, ``run-plan``, ``export-agents``, ``history new``.



### Quick reference

```powershell
# Explicit path (works without any setup)
python -m vibecode.cli context "my task" --repo C:\path\to\repo

# Registry workflow (set once, use many times)
python -m vibecode.cli project add MYREPO C:\path\to\repo
python -m vibecode.cli project use MYREPO
python -m vibecode.cli context "my task"        # uses MYREPO automatically
```

Agent-facing files have different lifecycles:

- Root `AGENTS.md` is stable agent instruction for the repository.
- `.vibecode/current/context_pack.md` is task-specific runtime output.
- `.vibecode/generated/AGENTS.generated.md` is generated export output and remains ignored.
- `.vibecode/agents/safe.json`, `.vibecode/agents/fast.json`, and `.vibecode/agents/audit.json` are committed permission profiles; `vibecode init` creates missing defaults without overwriting customized profiles unless `--force` is used.

`export-agents` writes `.vibecode/generated/AGENTS.generated.md` and creates or updates root `AGENTS.md` only when it is absent or Vibecode-managed. A manual root `AGENTS.md` is not overwritten without `--force`.

Generated indexes and runtime/current files are not source of truth. Regenerate `.vibecode/index/*` and `.vibecode/current/*` before giving the context to another agent. Human-maintained project rules live under `.vibecode/project.yaml`, `.vibecode/architecture/`, `.vibecode/checks/`, `.vibecode/handoff/`, `.vibecode/history/`, and `.vibecode/agents/`.



<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Status

The README is not the task tracker. Use `docs/ARCHITECTURE_MAP_STATUS.md` for the current Architecture Map Status and `docs/ARCHITECTURE_MAP_PRD.md` for the Architecture Map PRD.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Contributing

Keep changes narrow and task-relevant. Before implementing agent runtime features, make sure the Architecture Map Core is truthful, deterministic, and tested.

Recommended local loop:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -p no:cacheprovider
git status --short
```

Do not overwrite human-maintained `.vibecode/architecture/` or `.vibecode/handoff/` files unless the task explicitly asks for it.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## License

No license file is currently present in this repository.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Acknowledgments

- README structure inspired by [othneildrew/Best-README-Template](https://github.com/othneildrew/Best-README-Template).

<p align="right">(<a href="#readme-top">back to top</a>)</p>
