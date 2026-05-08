<a id="readme-top"></a>

# VibecodeApp

VibecodeApp is a local repository architecture-map and context-pack CLI. Its first job is to create a deterministic `.vibecode/` project layer that helps coding agents understand repository structure, important files, entrypoints, tests, dependencies, symbols, protected areas, and current project rules before they edit code.

This repository is intentionally CLI-first. It does not launch OpenCode, Codex, or any other agent runtime yet.

## Table of Contents

1. [About The Project](#about-the-project)
2. [Built With](#built-with)
3. [Getting Started](#getting-started)
4. [Usage](#usage)
5. [Roadmap](#roadmap)
6. [Contributing](#contributing)
7. [License](#license)
8. [Acknowledgments](#acknowledgments)

## About The Project

VibecodeApp is meant to become the project control layer around agentic coding work. The initial architecture-map scope focuses on:

- creating and maintaining `.vibecode/`
- scanning repositories safely
- generating file inventory, symbol, dependency, test, entrypoint, and risk maps
- preserving human-maintained architecture and handoff files
- validating generated artifacts
- preparing for future context-pack and prompt export work

Current non-goals:

- no custom coding agent
- no GUI
- no MCP server
- no OpenCode run adapter
- no auto-commit or auto-approve behavior
- no LLM API calls

See `docs/PRD_VIBECODE_ARCHITECTURE_MAP.md` and `PRD.json` for the detailed product scope and task list.

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

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Usage

Initialize a target repository:

```powershell
python -m vibecode.cli init C:\path\to\example-repo --id example_repo --name ExampleRepo
```

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

Run the current context command:

```powershell
python -m vibecode.cli context "Update context panel copy" --repo C:\path\to\example-repo
```

The PRD-style form is also supported:

```powershell
python -m vibecode.cli context C:\path\to\example-repo --task "Update context panel copy"
```

`context` writes `.vibecode/current/context_pack.md`, a derived runtime artifact for the current task.

Generated files live under `.vibecode/index/`, `.vibecode/current/`, and `.vibecode/logs/`. Human-maintained project rules live under `.vibecode/project.yaml`, `.vibecode/architecture/`, `.vibecode/handoff/`, and `.vibecode/history/`.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Roadmap

- [x] CLI skeleton
- [x] `.vibecode/` init
- [x] repository scanning and file inventory
- [x] symbol, dependency, test, entrypoint, and risk maps
- [x] index run records and validation
- [ ] relevant-file scoring
- [ ] context-pack renderer
- [ ] context-pack length limits
- [ ] OpenCode prompt export without launching OpenCode
- [ ] generated agent instructions

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Contributing

Keep changes narrow and task-relevant. Before implementing agent runtime features, make sure the architecture map and context-pack core are truthful, deterministic, and tested.

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
