<a id="readme-top"></a>

# VibecodeApp

VibecodeApp is a local repository architecture-map and context-pack CLI. Its first job is to create a deterministic `.vibecode/` project layer that helps coding agents understand repository structure, important files, entrypoints, tests, dependencies, symbols, protected areas, and current project rules before they edit code.

This repository is intentionally CLI-first. It does not launch OpenCode, Codex, or any other agent runtime yet.

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



Index a repository:

```powershell
python -m vibecode.cli index C:\path\to\example-repo
```

Validate Vibecode artifacts:

```powershell
python -m vibecode.cli validate C:\path\to\example-repo
```

Print a compact repository map:

```powershell
python -m vibecode.cli map C:\path\to\example-repo
```

Generate a context pack:

```powershell
python -m vibecode.cli context "Update context panel copy" --repo C:\path\to\example-repo
```

This writes `.vibecode\current\context_pack.md`, a task-specific runtime artifact.
To also export an OpenCode-compatible prompt wrapper, add `--platform opencode`:

```powershell
python -m vibecode.cli context "Update context panel copy" --repo C:\path\to\example-repo --platform opencode
```

This additionally writes `.vibecode\current\opencode_prompt.md` with pre-edit and post-edit instructions.
`vibecode` does **not** launch OpenCode — passing the prompt to an external agent is a manual step.

Preview a full agent run without launching it:

```powershell
python -m vibecode.cli run-plan C:\path\to\example-repo --task "Update context panel copy"
```

`run-plan` checks preconditions (git status, index freshness, OpenCode availability, permission profile)
and writes `.vibecode\current\run_plan.json`.

Run an agent session:

```powershell
python -m vibecode.cli run C:\path\to\example-repo --task "Update context panel copy" --profile safe
```

`run` orchestrates the full loop: generate context pack → invoke the platform command with the prompt on stdin →
run post-run guard, required checks, and handoff validation → write session metadata.
Use `--profile safe` (default), `fast`, or `audit` to control permission levels.
Use `--allow-dirty` to run with uncommitted changes (warn only, no error).
Use `--no-index` to skip automatic index generation.

Execute a post-run audit:

```powershell
python -m vibecode.cli guard C:\path\to\example-repo [--strict]
python -m vibecode.cli check C:\path\to\example-repo
python -m vibecode.cli handoff-check C:\path\to\example-repo [--json]
```

These can also be run independently outside of a `run` session.

Export agent instructions:

```powershell
python -m vibecode.cli export-agents .
```

Agent-facing files have different lifecycles:

- Root `AGENTS.md` is stable agent instruction for the repository.
- `.vibecode/current/context_pack.md` is task-specific runtime output.
- `.vibecode/generated/AGENTS.generated.md` is generated export output and remains ignored.

`export-agents` writes `.vibecode/generated/AGENTS.generated.md` and creates or updates root `AGENTS.md` only when it is absent or Vibecode-managed. A manual root `AGENTS.md` is not overwritten without `--force`.

Generated indexes and runtime/current files are not source of truth. Regenerate `.vibecode/index/*` and `.vibecode/current/*` before giving the context to another agent. Human-maintained project rules live under `.vibecode/project.yaml`, `.vibecode/architecture/`, `.vibecode/checks/`, `.vibecode/handoff/`, and `.vibecode/history/`.

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
