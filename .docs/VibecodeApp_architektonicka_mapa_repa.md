# VibecodeApp: Aider-style architektonická mapa repa initial scope

**Datum:** 2026-05-08  
**Stav:** návrh implementačního MVP  
**Cíl:** postavit první chybějící kus VibecodeApp — lokální mapu repozitáře, která agentovi dá orientaci v architektuře, modulech, entrypointech, testech, rizikových souborech a projektových pravidlech bez nutnosti cpát celé repo do context window.

---

## 1. Executive summary

VibecodeApp nemá být další coding agent. To by byl slepý směr. Agentů je dost: OpenCode, Codex, Claude Code, Copilot, Aider-like nástroje. Skutečný problém je, že agent většinou neví, **v jakém projektu stojí**, **jaká pravidla platí**, **kde jsou hranice modulů**, **které soubory jsou rizikové**, **jaké testy ověřují změny** a **co se už v projektu rozhodlo**.

První stavební blok VibecodeApp bude proto:

> **Aider-style architektonická mapa repa**

Nejde jen o strom souborů. Strom souborů je levný a hloupý. Potřebujeme kombinaci:

- deterministicky vygenerované struktury repa,
- symbol mapy,
- mapy modulů,
- entrypointů,
- test mapy,
- rizikových/protected oblastí,
- ručně potvrzených invariantů,
- krátké LLM/agent-friendly sumarizace,
- context packu pro konkrétní task.

Aider repo map byla silná proto, že modelu dávala kompaktní orientaci v kódu. VibecodeApp musí jít dál: mapa nemá popsat jen **kde jsou funkce**, ale také **jaký význam mají části systému a co se nesmí porušit**.

---

## 2. Problém, který řešíme

Dnešní coding agent často dostane task typu:

```text
Oprav problém s FX kurzem.
```

A začne:

- grepovat náhodné výskyty,
- číst špatné soubory,
- přepisovat širší části systému,
- porušovat dřívější rozhodnutí,
- aktualizovat README jako skládku,
- měnit architekturu bez vědomí operátora,
- zapomenout aktualizovat handoff.

To není inteligence. To je nekontrolovaný dělník bez plánu stavby.

VibecodeApp musí agentovi před každou prací poskytnout:

```text
Tady je projekt.
Tady je jeho struktura.
Tady jsou důležité moduly.
Tady jsou vstupy/výstupy.
Tady jsou testy.
Tady jsou invarianty.
Tady jsou riziková místa.
Tady jsou relevantní soubory k tomuto tasku.
Tady je poslední handoff.
Do těchto oblastí nesahej bez povolení.
```

---

## 3. Cíle MVP

MVP má splnit pět věcí:

1. **Načíst repo a vytvořit základní mapu struktury.**
2. **Vytvořit symbolickou mapu důležitých souborů a definic.**
3. **Vygenerovat architektonickou mapu vhodnou pro agenta.**
4. **Vytvořit context pack pro konkrétní task.**
5. **Uložit vše lokálně v repu do `.vibecode/`, čitelně a verzovatelně.**

MVP nesmí hned řešit všechno. Nesmíme spadnout do pasti, že budeme půl roku stavět „dokonalý knowledge graph“, zatímco agent dál rozkopává projekty.

---

## 4. Non-goals pro initial scope

Tyto věci se v první verzi nedělají:

- vlastní coding agent,
- vlastní IDE/editor,
- komplexní knowledge graph,
- multi-agent swarm,
- automatické hluboké refaktoringy,
- plně autonomní aktualizace architektury,
- automatické commity,
- automatické schvalování změn.

initial scope je mapa a context engine. Nic víc. Jakmile bude pevná mapa, můžeme na ni napojit OpenCode run workflow.

---

## 5. Základní principy

### 5.1 Deterministické jádro, LLM jen jako nadstavba

Mapa nesmí být jen text, který napsal agent. To by byla krásná halucinace.

Správné vrstvy:

```text
git ls-files / filesystem scan
→ ignored paths filtering
→ language detection
→ symbol extraction
→ imports/dependencies extraction
→ test mapping
→ risk/protection rules
→ generated index files
→ optional LLM summary
→ human-reviewable architecture map
```

LLM může sumarizovat, ale základ musí být ověřitelný.

### 5.2 Lokální first

Vše se ukládá do repa:

```text
.vibecode/
```

Žádná skrytá cloudová pravda. Žádná magická databáze, kterou si člověk neumí přečíst. Pokud se VibecodeApp rozbije, projektová paměť a mapa musí pořád existovat jako soubory.

### 5.3 README není hlavní pravda

README je prezentace. Ne projektová databáze.

Hlavní mapa a pravidla patří do `.vibecode/`. README může obsahovat jen vybrané generované bloky.

### 5.4 Agent nesmí vědět míň než projekt už ví

Pokud projekt ví, že `workbook is not runtime truth`, agent to musí dostat. Pokud projekt ví, že `matching.py` je rizikový, agent to musí dostat. Pokud projekt ví, že určitý test je povinný, agent to musí dostat.

---

## 6. Cílová složková struktura

Po spuštění:

```powershell
vibecode index C:\DATA\PROJECTS\STOCKS
```

vznikne:

```text
.vibecode/
  project.yaml

  index/
    repo_tree.md
    file_inventory.json
    symbol_map.json
    dependency_map.json
    test_map.json
    entrypoints.md
    risky_files.md
    generated_summary.md

  architecture/
    OVERVIEW.md
    STRUCTURE.md
    MODULE_BOUNDARIES.md
    DATA_FLOW.md
    INVARIANTS.md
    PROTECTED_AREAS.md

  current/
    context_pack.md
    active_task.md
    last_index.json

  handoff/
    NOW.md
    NEXT.md
    BLOCKERS.md

  history/
    README.md

  logs/
    index_runs/
```

initial scope nemusí naplnit všechno dokonale, ale musí vytvořit stabilní kontrakt.

---

## 7. Soubor `project.yaml`

Tento soubor definuje identitu projektu a základní pravidla indexace.

```yaml
version: 1
project:
  id: stocks
  name: STOCKS
  root: C:\DATA\PROJECTS\STOCKS
  type: application
  primary_languages:
    - python
    - typescript
  description: >
    Czech stock tax processing app with FastAPI backend, React frontend,
    CSV imports, ProjectState runtime ownership and audit/evidence workflows.

indexing:
  include:
    - stock_tax_app/**
    - ui/frontend/src/**
    - tests/**
    - docs/**
    - pyproject.toml
    - package.json
  exclude:
    - .git/**
    - .venv/**
    - node_modules/**
    - dist/**
    - build/**
    - __pycache__/**
    - .pytest_cache/**
    - .mypy_cache/**
    - exports/**
    - .csv/**

protected_paths:
  - stock_tax_app/engine/matching.py
  - stock_tax_app/engine/policy.py
  - stock_tax_app/engine/fx.py
  - docs/audit/**

risk_rules:
  - id: tax_matching_logic
    paths:
      - stock_tax_app/engine/matching.py
    severity: high
    reason: >
      Matching algorithms affect tax calculations and require explicit tests,
      audit note and operator approval.

required_checks:
  python:
    - pytest
  frontend:
    - bun test
```

Pro první verzi stačí ruční konfigurace. Automatická detekce může přijít později.

---

## 8. Indexované datové zdroje

### 8.1 Git/filesystem

Základní zdroj pravdy:

```bash
git ls-files
```

Fallback bez gitu:

```bash
filesystem walk
```

Index musí rozlišit:

- trackované soubory,
- netrackované soubory,
- ignorované soubory,
- velké soubory,
- binární soubory,
- generované artefakty.

### 8.2 Konfigurační soubory

Index musí speciálně hledat:

```text
pyproject.toml
setup.py
requirements.txt
package.json
vite.config.*
tsconfig.json
pytest.ini
ruff.toml
mypy.ini
Dockerfile
docker-compose.yml
Makefile
README.md
AGENTS.md
CLAUDE.md
.github/copilot-instructions.md
```

Tyto soubory často definují realitu projektu.

### 8.3 Testy

Testy nejsou obyčejné soubory. Test mapa je jedna z nejdůležitějších částí.

Index musí najít:

- Python testy: `test_*.py`, `*_test.py`, `tests/**`
- TypeScript/React testy: `*.test.ts`, `*.test.tsx`, `*.spec.ts`, `*.spec.tsx`
- e2e testy: `playwright`, `cypress`, případně custom složky

### 8.4 Dokumentace

Index musí najít:

- `docs/**`
- `README.md`
- audit dokumenty,
- design dokumenty,
- ADR soubory,
- handoff soubory.

---

## 9. Výstup: `file_inventory.json`

Příklad:

```json
{
  "version": 1,
  "project_id": "stocks",
  "generated_at": "2026-05-08T14:00:00+02:00",
  "root": "C:/DATA/PROJECTS/STOCKS",
  "files": [
    {
      "path": "stock_tax_app/engine/core.py",
      "language": "python",
      "size_bytes": 18432,
      "role_guess": "backend_engine",
      "is_test": false,
      "is_config": false,
      "is_doc": false,
      "risk_level": "medium"
    },
    {
      "path": "ui/frontend/src/screens/tax-years-screen.tsx",
      "language": "typescriptreact",
      "size_bytes": 23104,
      "role_guess": "frontend_screen",
      "is_test": false,
      "is_config": false,
      "is_doc": false,
      "risk_level": "medium"
    }
  ]
}
```

Role guess může být primitivní v první verzi:

```text
backend_engine
backend_api
frontend_screen
frontend_component
test
doc
config
script
unknown
```

---

## 10. Výstup: `repo_tree.md`

Cílem není vypsat úplně všechno. Cílem je kompaktní strom se zvýrazněním důležitých částí.

Příklad:

```md
# Repo tree

Root: `C:/DATA/PROJECTS/STOCKS`

## Top-level

```text
stock_tax_app/        Backend and tax calculation engine
ui/frontend/          React/Vite frontend
scripts/              Utility and export scripts
docs/                 Audit and design documentation
tests/                Backend test suite
.vibecode/            Vibecode project memory and architecture map
```

## Backend

```text
stock_tax_app/
  api/                FastAPI routes and API models
  engine/             Calculation engine and runtime state handling
    core.py           Main calculation orchestration
    matching.py       Tax lot matching algorithms [HIGH RISK]
    policy.py         Year/method policy and soft-lock behavior [HIGH RISK]
    ui_state.py       Review/UI state ownership
  state/              ProjectState load/save and schema
```

## Frontend

```text
ui/frontend/src/
  screens/            Main application screens
  components/         Shared UI components
  api/                API client hooks
  state/              Frontend state/helpers
```
```

---

## 11. Výstup: `symbol_map.json`

Symbol mapa je technický index. initial scope může být jednoduchá.

Pro Python:

- moduly,
- třídy,
- funkce,
- metody,
- FastAPI routy, pokud detekovatelné.

Pro TypeScript/React:

- exportované funkce,
- komponenty,
- hooks,
- typy/interface,
- routy/screen komponenty.

Příklad:

```json
{
  "version": 1,
  "files": [
    {
      "path": "stock_tax_app/engine/policy.py",
      "language": "python",
      "symbols": [
        {
          "name": "YearPolicy",
          "kind": "class",
          "line_start": 12,
          "line_end": 48
        },
        {
          "name": "resolve_year_policy",
          "kind": "function",
          "line_start": 51,
          "line_end": 112
        }
      ]
    },
    {
      "path": "ui/frontend/src/screens/tax-years-screen.tsx",
      "language": "typescriptreact",
      "symbols": [
        {
          "name": "TaxYearsScreen",
          "kind": "react_component",
          "line_start": 35,
          "line_end": 240
        },
        {
          "name": "formatComparisonLabel",
          "kind": "function",
          "line_start": 242,
          "line_end": 260
        }
      ]
    }
  ]
}
```

### Implementační poznámka

initial scope může použít jednoduchý parser:

- Python: standardní `ast` modul.
- TypeScript/TSX: regex fallback + později Tree-sitter.

To není dokonalé, ale je to lepší než nic. Kdybychom čekali na perfektní indexer, nepostavíme nic.

---

## 12. Výstup: `dependency_map.json`

initial scope stačí import mapa.

```json
{
  "version": 1,
  "edges": [
    {
      "from": "stock_tax_app/engine/core.py",
      "to": "stock_tax_app/engine/policy.py",
      "type": "python_import"
    },
    {
      "from": "ui/frontend/src/screens/tax-years-screen.tsx",
      "to": "ui/frontend/src/api/tax-years.ts",
      "type": "typescript_import"
    }
  ]
}
```

Později lze přidat:

- call graph,
- endpoint-to-frontend mapping,
- test-to-code mapping,
- ownership mapping.

---

## 13. Výstup: `test_map.json`

Test mapa musí odpovědět:

> Když agent mění tento soubor, jaké testy má spustit?

Příklad:

```json
{
  "version": 1,
  "rules": [
    {
      "path_pattern": "stock_tax_app/engine/matching.py",
      "required_checks": [
        "pytest test_matching.py",
        "pytest test_method_comparison_semantics.py"
      ],
      "reason": "Tax lot matching changes require invariant and comparison tests."
    },
    {
      "path_pattern": "ui/frontend/src/screens/tax-years-screen.tsx",
      "required_checks": [
        "bun test tax-years-screen.test.tsx"
      ],
      "reason": "Tax Years UI behavior and copy changed."
    }
  ]
}
```

initial scope může být ruční + heuristická:

- když existuje `foo.py`, hledat `test_foo.py`, `foo_test.py`, testy obsahující import `foo`,
- u TSX hledat `foo.test.tsx`, `foo-screen.test.tsx`,
- doplnit ruční pravidla v `project.yaml`.

---

## 14. Výstup: `entrypoints.md`

Agent musí vědět, kde systém začíná.

Příklad:

```md
# Entrypoints

## Backend

- `stock_tax_app/main.py` — FastAPI app bootstrap.
- `stock_tax_app/api/*` — API routes.
- `build_stock_tax_workbook.py` — legacy/export compatibility script, not runtime truth.

## Frontend

- `ui/frontend/src/main.tsx` — frontend bootstrap.
- `ui/frontend/src/App.tsx` — route shell.
- `ui/frontend/src/screens/*` — screen-level UI.

## CLI / scripts

- `scripts/export_ticker_tax_method_pdfs.py` — evidence/export script.

## Runtime state

- `.stock_tax_state.json` — ProjectState runtime source.
- `.ui_state.json` — canonical UI/review state.
```

---

## 15. Výstup: `risky_files.md`

Tohle je guardrail pro agenta.

```md
# Risky files

These files are allowed to be changed only with explicit task relevance and review.

## High risk

### `stock_tax_app/engine/matching.py`

Tax lot matching algorithms. Changes can affect taxable gains and year comparison semantics.

Required before editing:

- explicit task permission,
- relevant invariant tests,
- audit note if semantics change,
- operator review.

### `stock_tax_app/engine/policy.py`

Year policy, soft-lock behavior and method comparison rules.

Required before editing:

- confirm filed years remain soft locks,
- run policy/API tests,
- update audit docs if behavior changes.

## Medium risk

### `ui/frontend/src/screens/tax-years-screen.tsx`

Main Tax Years screen. UI copy changes are lower risk, but semantics shown here must match backend truth.
```

---

## 16. Ručně potvrzené architektonické soubory

### 16.1 `architecture/INVARIANTS.md`

Tento soubor je nejdůležitější. Agent ho musí dostat vždy.

Příklad pro STOCKS:

```md
# Project invariants

## Runtime ownership

- Workbook is not runtime truth.
- ProjectState owns canonical runtime state.
- UI/review state is owned by `.ui_state.json` / backend UI state module.

## CSV behavior

- CSV issues must not block navigation.
- CSV issues are warnings/checks/actionable issues.
- Refresh/recalculate must reread CSV files from `.csv/`.

## Tax year behavior

- Filed/closed years are soft locks only.
- User must be able to unlock/reset/recalculate.
- No hard tax-year lock may block the app workflow.

## FX behavior

- No silent FX fallback from daily to yearly/default.
- FX daily requires exact or explicitly permitted earlier-fill policy.
- FX unified/yearly requires real configured yearly FX.

## Calculation safety

- Matching algorithm changes require explicit tests.
- Method comparison must preserve documented semantics.
- UI labels must not imply a stronger truth than backend provides.
```

### 16.2 `architecture/MODULE_BOUNDARIES.md`

```md
# Module boundaries

## Backend API

Owns HTTP shape, request/response models and conversion from engine state to UI/API data.
Does not own tax calculation semantics.

## Engine

Owns calculations, matching, FX policy, ProjectState interpretation and method comparison semantics.
Does not own frontend presentation copy.

## Frontend

Owns UI state, display, warnings, review flows and operator interactions.
Does not invent backend truth.

## Docs/audit

Owns status records and rationale for migrations/refactors.
Docs must be updated when semantics or ownership rules change.
```

### 16.3 `architecture/STRUCTURE.md`

Tento soubor může být částečně generovaný, částečně ručně upravený.

```md
# Project structure

## Backend

`stock_tax_app/engine/` contains the calculation engine and policy logic.

Important files:

- `core.py` — orchestration of calculation flow.
- `matching.py` — lot matching algorithms.
- `policy.py` — tax year/method policy.
- `ui_state.py` — canonical review/UI state handling.

## Frontend

`ui/frontend/src/screens/` contains screen-level application flows.

Important files:

- `tax-years-screen.tsx` — tax year method comparison and filed-year UI.
- `fx-screen.tsx` — FX status and missing dates.
- `sales-review-screen.tsx` — sale review queue and detail.
```

---

## 17. Context pack pro task

VibecodeApp nesmí agentovi dávat všechno. Musí dát krátký, tvrdý a relevantní balík.

Soubor:

```text
.vibecode/current/context_pack.md
```

Příklad:

```md
# Vibecode Context Pack

## Project

STOCKS — Czech stock tax processing app.

## Current task

Oprav copy na Tax Years screen tak, aby jasně rozlišovalo global comparison a year-only comparison. Neměň calculation semantics ani matching algorithms.

## Must preserve

- Filed years are soft locks only.
- Workbook is not runtime truth.
- ProjectState owns canonical runtime state.
- CSV issues are warnings, not blockers.
- No silent FX fallback.
- Do not modify matching algorithms unless explicitly requested.

## Relevant architecture

- Backend owns method comparison semantics.
- Frontend may display labels/help copy, but must not invent semantics.
- Audit docs should be updated if behavior/copy clarification affects documented status.

## Relevant files

- `ui/frontend/src/screens/tax-years-screen.tsx`
- `ui/frontend/src/screens/tax-years-screen.test.tsx`
- `docs/audit/METHOD_COMPARISON_SEMANTICS_STATUS.md`

## Risky files not allowed for this task

- `stock_tax_app/engine/matching.py`
- `stock_tax_app/engine/policy.py`

## Required checks

- `bun test tax-years-screen.test.tsx`
- backend tests only if backend files changed

## Handoff required

After changes, update:

- `.vibecode/handoff/NOW.md`
- `.vibecode/history/<timestamp>_tax-years-copy.md`

## Working rule

Make the smallest change that satisfies the task. Do not refactor unrelated code.
```

Tohle je přesně balík, který bude vkládán do OpenCode/Codex/Aider-like workeru.

---

## 18. Jak se vybírají relevantní soubory

initial scope jednoduchý scoring:

```text
score = 0
+ 10 pokud cesta/filename obsahuje klíčové slovo z tasku
+ 8 pokud symbol name obsahuje klíčové slovo z tasku
+ 6 pokud soubor byl v posledním handoffu
+ 5 pokud soubor je v recent git diff/history pro podobné téma
+ 4 pokud jde o test související s vybraným souborem
+ 3 pokud dependency graph spojuje soubor s vybraným modulem
- 10 pokud je soubor excluded/generated
- 8 pokud je protected a task ho explicitně nevyžaduje
```

Příklad tasku:

```text
Oprav Tax Years UI copy kolem method comparison.
```

Relevantní slova:

```text
tax, years, ui, copy, method, comparison
```

Vybrané soubory:

```text
ui/frontend/src/screens/tax-years-screen.tsx
ui/frontend/src/screens/tax-years-screen.test.tsx
docs/audit/METHOD_COMPARISON_SEMANTICS_STATUS.md
```

Zakázané nebo varované:

```text
stock_tax_app/engine/matching.py
stock_tax_app/engine/policy.py
```

---

## 19. CLI návrh pro initial scope

### 19.1 Inicializace

```powershell
vibecode init C:\DATA\PROJECTS\STOCKS --id stocks --name STOCKS
```

Vytvoří:

```text
.vibecode/project.yaml
.vibecode/architecture/INVARIANTS.md
.vibecode/architecture/STRUCTURE.md
.vibecode/handoff/NOW.md
```

### 19.2 Indexace

```powershell
vibecode index C:\DATA\PROJECTS\STOCKS
```

Vytvoří/aktualizuje:

```text
.vibecode/index/*
```

### 19.3 Zobrazení mapy

```powershell
vibecode map C:\DATA\PROJECTS\STOCKS
```

Vypíše kompaktní mapu:

```text
Project: STOCKS
Languages: Python, TypeScript
Backend: stock_tax_app/
Frontend: ui/frontend/
High-risk files: 3
Tests detected: 118
Entrypoints: 5
Last index: 2026-05-08 14:00
```

### 19.4 Context pack pro task

```powershell
vibecode context C:\DATA\PROJECTS\STOCKS --task "Oprav Tax Years UI copy"
```

Vytvoří:

```text
.vibecode/current/context_pack.md
```

### 19.5 Export pro OpenCode

```powershell
vibecode context C:\DATA\PROJECTS\STOCKS --task "..." --platform opencode
```

Vytvoří:

```text
.vibecode/current/opencode_prompt.md
```

---

## 20. OpenCode prompt wrapper

VibecodeApp může pro OpenCode generovat prompt:

```md
You are working inside a Vibecode-controlled repository.

You must follow the project context below. Do not ignore protected areas.
Make the smallest safe change. Do not refactor unrelated code.

Before editing:
1. Read the task.
2. Read relevant files.
3. Confirm whether protected files are needed.
4. Prefer narrow edits.

After editing:
1. Summarize changed files.
2. List tests run.
3. Update handoff files if instructed.

---

{{ context_pack.md }}
```

OpenCode pak zůstává worker. Vibecode drží pravidla.

---

## 21. Generování `AGENTS.md`

VibecodeApp může vygenerovat krátký `AGENTS.md` v rootu:

```md
# Agent instructions

This repository is managed by VibecodeApp.

Before doing work, read:

- `.vibecode/current/context_pack.md`
- `.vibecode/architecture/INVARIANTS.md`
- `.vibecode/architecture/MODULE_BOUNDARIES.md`
- `.vibecode/handoff/NOW.md`

Rules:

- Make minimal task-relevant changes.
- Do not modify protected files unless the task explicitly requires it.
- Do not update README outside marked generated blocks.
- Run required checks listed in the context pack.
- Update handoff after work.
```

Důležité: `AGENTS.md` je export. Hlavní pravda je pořád `.vibecode/`.

---

## 22. Implementační návrh v Pythonu

### 22.1 Balíček

```text
vibecode/
  __init__.py
  cli.py
  project.py
  config.py
  indexer/
    __init__.py
    file_inventory.py
    python_symbols.py
    typescript_symbols.py
    imports.py
    tests.py
    tree.py
  context/
    builder.py
    scoring.py
    renderer.py
  templates/
    context_pack.md.j2
    repo_tree.md.j2
    agents.md.j2
```

### 22.2 Datové typy

```python
@dataclass
class ProjectConfig:
    id: str
    name: str
    root: Path
    include: list[str]
    exclude: list[str]
    protected_paths: list[str]
    required_checks: dict[str, list[str]]

@dataclass
class FileRecord:
    path: str
    language: str | None
    size_bytes: int
    role_guess: str
    is_test: bool
    is_config: bool
    is_doc: bool
    risk_level: str

@dataclass
class SymbolRecord:
    path: str
    name: str
    kind: str
    line_start: int
    line_end: int | None

@dataclass
class ContextPack:
    project_id: str
    task: str
    invariants: list[str]
    relevant_files: list[str]
    risky_files: list[str]
    required_checks: list[str]
    handoff_required: bool
```

---

## 23. Symbol extraction initial scope

### 23.1 Python

Použít `ast`:

- `ast.FunctionDef`
- `ast.AsyncFunctionDef`
- `ast.ClassDef`
- decorators pro routy: `@router.get`, `@app.post`, atd.

Základní implementace:

```python
import ast
from pathlib import Path


def extract_python_symbols(path: Path) -> list[dict]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    symbols = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            symbols.append({
                "name": node.name,
                "kind": "class",
                "line_start": node.lineno,
                "line_end": getattr(node, "end_lineno", None),
            })
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = "function"
            if any(_looks_like_route_decorator(d) for d in node.decorator_list):
                kind = "api_route"
            symbols.append({
                "name": node.name,
                "kind": kind,
                "line_start": node.lineno,
                "line_end": getattr(node, "end_lineno", None),
            })

    return symbols
```

### 23.2 TypeScript/TSX

initial scope může použít hrubší parser:

- `export function X`
- `function X`
- `const X = (...) =>`
- `export const X =`
- `interface X`
- `type X =`
- React komponenty heuristicky podle PascalCase + JSX návratu

Později nahradit Tree-sitterem nebo TypeScript compiler API.

---

## 24. Kvalitní mapa není jen automatika

Tady je tvrdá pravda: plně automatická architektonická mapa nebude stačit.

Scanner pozná:

```text
kde jsou soubory
jaké mají symboly
co importují
kde jsou testy
```

Scanner nepozná spolehlivě:

```text
proč workbook nesmí být runtime truth
proč filed years jsou soft locks
proč matching.py je daňově rizikový
proč CSV problém nesmí blokovat UI
```

To musí být ručně potvrzené v invariantních souborech.

VibecodeApp má tedy kombinovat:

```text
deterministický index
+ lidsky potvrzené invarianty
+ agent-friendly summary
```

Bez lidsky potvrzených invariantů bude mapa jen hezčí grep.

---

## 25. Validace mapy

Po `vibecode index` musí proběhnout validace:

```text
[OK] project.yaml exists
[OK] root path exists
[OK] index excludes node_modules/.venv/.git
[OK] file inventory written
[OK] symbol map written
[OK] test map written
[WARN] architecture/INVARIANTS.md is empty
[WARN] no protected paths configured
[OK] context pack can be generated
```

Pokud chybí invarianty, není to fail. Ale appka musí dát jasné varování:

> Projekt nemá potvrzené invarianty. Agent dostane technickou mapu, ale ne projektová pravidla. To je slabé.

---

## 26. Acceptance criteria pro MVP

MVP je hotové, pokud platí:

### 26.1 Indexace

- `vibecode init` vytvoří `.vibecode/` strukturu.
- `vibecode index` projde repo bez pádu.
- Ignoruje `.git`, `node_modules`, `.venv`, cache a build výstupy.
- Vygeneruje `file_inventory.json`.
- Vygeneruje `repo_tree.md`.
- Vygeneruje `symbol_map.json` pro Python.
- Aspoň hrubě vygeneruje symboly pro TypeScript/TSX.
- Vygeneruje `test_map.json`.

### 26.2 Context pack

- `vibecode context --task "..."` vytvoří `context_pack.md`.
- Context pack obsahuje:
  - název projektu,
  - task,
  - invarianty,
  - relevantní soubory,
  - protected/risky soubory,
  - required checks,
  - handoff instrukce.

### 26.3 Použitelnost pro agenta

- Context pack je kratší než cca 4 000–8 000 slov.
- Neobsahuje celé dlouhé soubory.
- Obsahuje jasné zákazy a relevantní soubory.
- Dá se přímo vložit do OpenCode promptu.

### 26.4 Stabilita

- Opakované spuštění `vibecode index` nepřepisuje ručně psané architektonické soubory bez markerů.
- Generated soubory jsou oddělené od human-maintained souborů.

---

## 27. Human vs generated soubory

Musí být jasně rozlišeno:

### Human-maintained

```text
.vibecode/architecture/INVARIANTS.md
.vibecode/architecture/MODULE_BOUNDARIES.md
.vibecode/architecture/PROTECTED_AREAS.md
.vibecode/handoff/NOW.md
.vibecode/project.yaml
```

### Generated

```text
.vibecode/index/repo_tree.md
.vibecode/index/file_inventory.json
.vibecode/index/symbol_map.json
.vibecode/index/dependency_map.json
.vibecode/index/test_map.json
.vibecode/current/context_pack.md
```

Generated soubory mohou být přepsané. Human-maintained soubory ne.

Pokud potřebujeme generované bloky v human souboru, použijeme markery:

```md
<!-- VIBECODE:GENERATED:START -->
...
<!-- VIBECODE:GENERATED:END -->
```

---

## 28. Minimální GUI obrazovka pro později

Až bude CLI fungovat, GUI může mít jednu jednoduchou obrazovku:

```text
Project: STOCKS
Root: C:\DATA\PROJECTS\STOCKS
Status: indexed 2026-05-08 14:00

Tabs:
- Overview
- Repo map
- Symbols
- Tests
- Invariants
- Context pack

Actions:
[Re-index]
[Generate context for task]
[Copy OpenCode prompt]
[Run with OpenCode]
```

Nejdřív ale CLI. GUI bez pevného indexeru by bylo pozlátko.

---

## 29. Pozdější rozšíření

### 29.1 Serena MCP

Jakmile mapa funguje, připojit semantic code tools:

- find symbol,
- find references,
- replace symbol body,
- insert before/after symbol.

Serena není náhrada mapy. Serena je nástroj pro práci se symboly. Mapa je projektová orientace.

### 29.2 ast-grep

Pro strukturální hledání a codemody:

- najít patterny,
- bezpečně přepsat importy,
- najít React prop usage,
- najít FastAPI endpoint patterny.

### 29.3 Tree-sitter

Pro lepší multi-language symbol extraction.

### 29.4 Project memory retrieval

Přidat:

```text
.vibecode/history/
.vibecode/decisions/
.vibecode/memory/known_failures.md
```

a context builder začne vybírat relevantní historické změny.

---

## 30. Rizika

### 30.1 Příliš dlouhý context pack

Pokud context pack naroste, agent ho přestane respektovat.

Ochrana:

- tvrdý limit délky,
- scoring relevantních souborů,
- ruční priority,
- sekce „must preserve“ vždy nahoře.

### 30.2 Halucinovaná architektura

Pokud mapu bude psát hlavně LLM, bude hezká, ale nedůvěryhodná.

Ochrana:

- deterministický index jako základ,
- human-reviewed invarianty,
- generované summary označit jako generated,
- nikdy nepřepsat ruční soubory bez markerů.

### 30.3 Přehnaná automatizace

Pokud se hned udělá auto-run + auto-edit + auto-commit, opět vznikne chaos.

Ochrana:

- nejdřív map + context,
- pak OpenCode run,
- pak guard layer,
- commity až po review.

### 30.4 Špatně označené protected files

Když nejsou protected paths správně nastavené, agent může sahat do citlivých míst.

Ochrana:

- ruční editace `project.yaml`,
- varování, pokud protected paths jsou prázdné,
- risk heuristika podle názvů: `matching`, `policy`, `state`, `migration`, `auth`, `security`, `tax`, `fx`.

---

## 31. Doporučené pořadí implementace

### Fáze 1: skeleton

- `vibecode init`
- `.vibecode/` struktura
- `project.yaml`
- prázdné invarianty/handoff soubory

### Fáze 2: file inventory

- git/filesystem scan
- include/exclude pravidla
- language detection
- role_guess
- `file_inventory.json`

### Fáze 3: repo tree

- kompaktní strom
- zvýraznění hlavních složek
- `repo_tree.md`

### Fáze 4: symbol map

- Python AST parser
- TS/TSX heuristika
- `symbol_map.json`

### Fáze 5: test map

- test file discovery
- simple source-to-test matching
- required checks from config
- `test_map.json`

### Fáze 6: context pack

- task scoring
- invariant loading
- relevant files
- risky files
- required checks
- `context_pack.md`

### Fáze 7: OpenCode prompt export

- `opencode_prompt.md`
- zatím bez samotného run adapteru

Teprve potom řešit:

```text
vibecode run --platform opencode
```

---

## 32. První testovací scénář

Repo:

```text
C:\DATA\PROJECTS\STOCKS
```

Příkaz:

```powershell
vibecode init C:\DATA\PROJECTS\STOCKS --id stocks --name STOCKS
vibecode index C:\DATA\PROJECTS\STOCKS
vibecode context C:\DATA\PROJECTS\STOCKS --task "Oprav Tax Years UI copy kolem global vs year-only comparison. Neměň matching algoritmy."
```

Očekávaný výsledek:

- context pack obsahuje `tax-years-screen.tsx`,
- obsahuje frontend test pro Tax Years,
- varuje před `matching.py`,
- říká, že matching algoritmy nejsou povolené,
- obsahuje invarianty o soft-locks a ProjectState,
- navrhuje relevantní frontend test,
- neobsahuje celé repo.

---

## 33. Druhý testovací scénář

Task:

```text
Zkontroluj, proč 2025 LIFO vychází vyšší než MAX_GAIN.
```

Očekávaný výsledek:

- context pack vybere `matching.py`, `policy.py`, relevantní testy,
- označí `matching.py` jako high risk,
- nedovolí přímé změny bez explicitního potvrzení,
- zahrne known invariant o method comparison semantics,
- doporučí nejdřív analýzu/test, ne refaktor.

---

## 34. Třetí testovací scénář

Task:

```text
Uprav spacing a copy na homepage prototypu.
```

Očekávaný výsledek:

- context pack vybere frontend soubory,
- nezahrne backend engine invarianty kromě globálních pravidel,
- neblokuje design změny,
- nevyžaduje backend testy.

Tohle ověří, že mapa není paranoidní kladivo na všechno.

---

## 35. Shrnutí rozhodnutí

Pro initial scope stavíme:

```text
Vibecode architecture map
```

Obsahuje:

```text
file inventory
repo tree
symbol map
dependency/import map
test map
entrypoints
risky files
human-maintained invariants
context pack generator
OpenCode prompt export
```

Nestavíme ještě:

```text
agent runtime
MCP server
Serena integration
auto-commit
auto-memory graph
GUI dashboard
```

To je správné. Tohle je základní kostra. Bez ní by OpenCode byl jen další nástroj, kterému musíš pokaždé ručně vysvětlovat, kde stojí.

---

## 36. Finální verdikt

Tento kus je potřeba postavit jako první.

Ne protože je efektní. Není. Je to nudná infrastruktura. Ale přesně nudná infrastruktura je rozdíl mezi:

```text
agentem, který náhodně kope do kódu
```

a

```text
agentem, který pracuje uvnitř jasně popsaného projektu
```

Pokud VibecodeApp zvládne jen jednu věc dobře, má to být tato:

> **Před každým agentním runem vytvořit pravdivý, krátký, projektově ukotvený context pack.**

Jakmile to bude fungovat, má smysl přidat OpenCode run adapter, Serena MCP, guard layer a handoff enforcement.

Bez téhle mapy by všechno další bylo jen hezčí chaos.
