# VibecodeApp — plán dalších kroků

## Executive summary

VibecodeApp má teď funkční základ: lokální Python CLI, které umí inicializovat `.vibecode/` projektovou vrstvu, indexovat repo, generovat architektonické mapy, symbol mapy, test mapy, dependency mapy, risk mapy a task-scoped context pack pro externí agenty.

To je dobrý základ, ale ještě to není plná VibecodeApp. Zatím existuje mapovací a context engine. Chybí guard layer, handoff enforcement, project registry, přímý OpenCode run adapter, a později GUI.

Nejbližší priorita není GUI ani OpenCode integrace. Nejbližší priorita je udělat architektonickou mapu opravdu užitečnou pro agenta.

---

## Aktuální stav

### Co už existuje

- Python CLI balíček `vibecode`.
- Inicializace `.vibecode/` struktury v repozitáři.
- Human-maintained projektové dokumenty pod `.vibecode/architecture/`.
- Required checks pod `.vibecode/checks/required_checks.yaml`.
- Handoff soubory pod `.vibecode/handoff/`.
- Generated/runtime soubory jsou ignorované a nejsou source of truth.
- Indexace repa:
  - file inventory,
  - repo tree,
  - symbol map,
  - dependency map,
  - test map,
  - entrypoints,
  - risky/protected files.
- Context pack generator.
- OpenCode prompt export.
- AGENTS export support.
- Validace `.vibecode` artefaktů.
- Silná test suite.

### Co to zatím není

- Není to GUI aplikace.
- Nespouští to OpenCode.
- Nespouští to Codex.
- Nemá to MCP server.
- Nemá to guard command.
- Nemá to check runner.
- Nemá to project registry.
- Nemá to plnohodnotnou memory vrstvu.
- Nemá to skutečné řízení agent runu od začátku do konce.

---

## Základní pravidlo dalšího vývoje

VibecodeApp nesmí být další coding agent. VibecodeApp má být projektová řídicí vrstva nad agenty.

Rozdělení rolí:

```text
OpenCode / Codex / jiný agent = worker, který mění kód
VibecodeApp = stavbyvedoucí, který drží mapu, pravidla, kontext, handoff, checks a diff guard
```

Pokud se začne stavět GUI nebo agent runtime dřív, než bude pevné jádro mapy a guardrails, vznikne jen hezký launcher nad chaosem.

---

# Fáze 1 — Zlepšit architektonickou mapu

## 1.1 Zlepšit `repo_tree.generated.md`

Aktuální repo tree je užitečný začátek, ale nesmí zůstat mělkým stromem. Musí fungovat jako orientační mapa pro agenta.

### Cíl

`repo_tree.generated.md` má ukazovat:

- hlavní source moduly,
- důležité druhé a třetí úrovně,
- CLI entrypointy,
- indexer oblast,
- context oblast,
- testy podle oblasti,
- config/docs,
- generated/runtime části jako oddělené a nekanonické,
- role složek,
- počet souborů/symbolů/testů na oblast.

### Příklad cílového tvaru

```text
vibecode/
  cli.py                         [CLI entrypoint]
  project.py                     [.vibecode initialization / map display]
  config.py                      [project config loading]
  validation.py                  [generated artifact validation]
  indexer/                       [repository indexing core]
    scanner.py                   [safe file discovery]
    repo_tree.py                 [architecture tree rendering]
    symbols.py                   [Python AST symbols]
    ts_symbols.py                [TS/TSX heuristic symbols]
    dependency_map.py            [import/dependency extraction]
    test_map.py                  [test discovery]
    risk_engine.py               [risk/protected file classification]
  context/                       [agent context generation]
    renderer.py                  [context pack renderer]
    scoring.py                   [relevant-file scoring]
    platform_export.py           [OpenCode prompt export]
    agents_export.py             [AGENTS export]
tests/
  test_vibecode_cli.py
  test_vibecode_context_pack.py
  test_vibecode_repo_tree.py
  test_vibecode_relevant_files.py
```

### Acceptance criteria

- Agent podle mapy najde správný modul bez slepého grepování celého repa.
- `vibecode/context` a `vibecode/indexer` nejsou schované za jedním řádkem.
- `vibecode/` není mylně klasifikované jako tests.
- Generated/runtime složky nejsou prezentované jako source.
- Mapa ukazuje důležité soubory druhé úrovně.
- Existuje test na užitečnou druhou úroveň mapy.

---

## 1.2 Dotáhnout relevant-file scoring

Relevant-file scoring je klíčový, protože určuje, co agent dostane jako pravděpodobně důležité soubory pro konkrétní task.

### Cíl

Scoring má být deterministický. Žádné LLM scoring v této fázi.

### Signály

Scoring má používat:

- task keywords,
- path/filename match,
- architecture docs references,
- source/test pairing,
- recent git changes,
- dependency-map connections,
- handoff references,
- history references,
- protected/risk weight,
- explicit exclusion generated/runtime/vendor/cache souborů.

### Acceptance criteria

Pro task:

```text
Improve repo tree rendering
```

musí top relevant files zahrnout například:

- `vibecode/indexer/repo_tree.py`,
- `tests/test_vibecode_repo_tree.py`,
- relevantní docs/status/PRD soubor.

Pokud scoring vybere hlavně README, pyproject a náhodné testy, scoring je slabý.

---

## 1.3 Zpřísnit kvalitu context packu

Context pack už existuje. Teď je potřeba zajistit, že reálně pomáhá agentovi a není to jen hezký markdown.

### Context pack musí obsahovat

- task,
- konkrétní invarianty,
- architektonické shrnutí,
- relevantní soubory s důvody,
- generated index status,
- required checks,
- risky/protected files,
- do-not-touch sekci,
- handoff expectations.

### Acceptance criteria

- Context pack je použitelný jako úvodní prompt pro OpenCode/Codex bez dalších ručních vysvětlivek.
- Neobsahuje celé dlouhé soubory.
- Neobsahuje generated/runtime šum.
- Varuje při stale indexu.
- Vysvětluje, proč jsou vybrané soubory relevantní.

---

# Fáze 2 — Agent-facing instrukce

## 2.1 Přidat root `AGENTS.md`

Root `AGENTS.md` má být krátký, konkrétní a nesmí se stát druhým README.

### Cíl

Vytvořit root `AGENTS.md`, který agentům řekne, kde je projektová pravda a čemu nemají věřit.

### Navržený obsah

```md
# AGENTS.md

Before making changes:
1. Read `.vibecode/architecture/INVARIANTS.md`.
2. Read `.vibecode/architecture/STRUCTURE.md`.
3. Read `.vibecode/handoff/NOW.md` if present.
4. Use `.vibecode/current/context_pack.md` only if it was generated for the current task.
5. Do not treat `.vibecode/index/*.generated.*` as canonical truth.
6. Do not edit generated/runtime files unless the task is about generator behavior.

Required checks are listed in:
`.vibecode/checks/required_checks.yaml`
```

### Acceptance criteria

- Root `AGENTS.md` neodkazuje na stale runtime soubory jako kanonické.
- Jasně rozlišuje human-maintained pravdu a generated output.
- Je krátký.
- Nezdvojuje celé `.vibecode/architecture` docs.

---

## 2.2 Ujasnit AGENTS export workflow

Export už existuje, ale workflow musí být bezpečné.

### Pravidla

- `export-agents` nesmí bez souhlasu přepsat ručně psaný root `AGENTS.md`.
- Generovaný obsah patří do `.vibecode/generated/`.
- Root `AGENTS.md` je buď Vibecode-managed, nebo human-maintained.
- Pokud je human-maintained, změna vyžaduje explicitní `--force` nebo jiný jasný režim.

### Acceptance criteria

- Export nevytváří bordel v rootu repa.
- Test ověřuje, že ruční `AGENTS.md` není přepsán bez explicitního povolení.

---

# Fáze 3 — Guard layer

Bez guard layer bude VibecodeApp pořád jen context generator. Guard layer je rozdíl mezi „agent dostal dobrý prompt“ a „agent nesmí rozbít pravidla bez zachycení“.

## 3.1 Přidat `guard` command

### Cíl

Příkaz:

```powershell
python -m vibecode.cli guard <repo>
```

zkontroluje aktuální git diff proti projektovým pravidlům.

### Kontroly

- Změny v protected paths.
- Změny v generated/runtime souborech.
- README změněné mimo povolené bloky, pokud budou definované.
- Změny architecture docs bez odpovídajícího handoffu nebo history zápisu.
- Source změny bez relevantních testů.
- Test-only změny označit jako warning, pokud nejsou vysvětlené.

### Acceptance criteria

- Guard vrací non-zero exit code při tvrdém porušení.
- Guard jasně vypíše problém a soubor.
- Guard má testy pro protected paths a generated/runtime edits.

---

## 3.2 Přidat protected paths policy

### Soubor

```text
.vibecode/checks/protected_paths.yaml
```

### Příklad

```yaml
protected_paths:
  - path: ".vibecode/architecture/"
    rule: "human-maintained project truth"
    require_explicit_task: true

  - path: ".vibecode/index/*.generated.*"
    rule: "generated output"
    allow_only_for_generator_tasks: true

  - path: "vibecode/indexer/scanner.py"
    rule: "core scanner; changes require scanner tests"
    required_tests:
      - "python -m pytest tests/test_vibecode_indexer.py"
```

### Acceptance criteria

- Context pack zahrnuje protected paths.
- Guard je umí vyhodnotit.
- Test pokrývá alespoň architecture docs, generated index a core source file.

---

## 3.3 Přidat required checks runner

### Cíl

Příkaz:

```powershell
python -m vibecode.cli check <repo>
```

načte `.vibecode/checks/required_checks.yaml` a spustí konkrétní příkazy.

### Výstup

Výsledek uložit do ignored runtime souboru:

```text
.vibecode/current/check_results.json
```

### Acceptance criteria

- Check runner nespouští vágní “tests”.
- Spouští konkrétní commandy.
- Ukládá exit code, stdout/stderr summary a timestamp.
- Test pokrývá passing i failing command.

---

# Fáze 4 — Handoff enforcement

Handoff soubory existují, ale zatím nejsou tvrdě vynucené.

## 4.1 Přidat handoff validator

### Cíl

Příkaz:

```powershell
python -m vibecode.cli handoff-check <repo>
```

zkontroluje, že handoff není placeholder.

### Kontroly

- `NOW.md` není prázdný.
- `NEXT.md` obsahuje konkrétní další kroky.
- `BLOCKERS.md` říká, jestli blokery jsou nebo nejsou.
- Pokud se mění architecture docs, existuje odpovídající handoff nebo history zápis.

### Acceptance criteria

- Placeholder handoff neprojde.
- Konkrétní handoff projde.
- Výstup jasně říká, co chybí.

---

## 4.2 Přidat history summaries

### Cíl

Po významném runu vznikne komprimovaný history zápis.

### Umístění

```text
.vibecode/history/YYYYMMDD-HHMM-task-summary.md
```

### Obsah

```md
# Task Summary

## Task
...

## Changed files
...

## Behavior changed
...

## Tests run
...

## Decisions
...

## Follow-up
...
```

### Pravidlo commitování

- `.vibecode/history/README.md` commitovat.
- `.vibecode/history/*.md` commitovat jen pokud obsahují projektovou pravdu.
- `.vibecode/runs/*` ignorovat vždy.

### Acceptance criteria

- History není raw log.
- History je stručná a užitečná pro dalšího člověka/agenta.

---

# Fáze 5 — OpenCode adapter

OpenCode integraci nepřidávat dřív, než jsou mapa, scoring, guard a handoff dostatečně pevné.

## 5.1 Přímý OpenCode run adapter

### Cíl

Příkaz:

```powershell
python -m vibecode.cli run <repo> --platform opencode --task "..."
```

### Flow

1. Zkontrolovat git status.
2. Ověřit, že index není stale, nebo ho řízeně regenerovat.
3. Vygenerovat context pack.
4. Vygenerovat OpenCode prompt.
5. Spustit OpenCode.
6. Uložit stdout/stderr/session metadata.
7. Po doběhu spustit guard.
8. Spustit required checks.
9. Ověřit handoff.
10. Ukázat diff summary.

### Acceptance criteria

- VibecodeApp nespustí agenta do špinavého nebo stale stavu bez jasného varování.
- Run metadata jsou uložena do ignored runtime složky.
- Source truth soubory nejsou automaticky měněny bez explicitního důvodu.

---

## 5.2 Permission profiles

### Cíl

Definovat bezpečnostní profily pro externí agenty.

### Příklad

```text
audit
- read only
- no edit
- no write

safe
- read allow
- grep/glob allow
- edit ask
- bash ask
- generated files deny

fast
- edit allow
- bash ask
- guard after run
```

### Acceptance criteria

- Citlivý projekt lze spustit v read-only audit režimu.
- Safe režim nenechá agenta nepozorovaně sahat do protected/generated souborů.

---

# Fáze 6 — CLI UX

CLI má zůstat jednoduché. Nevyrobit 30 příkazů.

## 6.1 Kanonické příkazy

Doporučený set:

```text
vibecode init <repo>
vibecode index <repo>
vibecode map <repo>
vibecode context <repo> --task "..."
vibecode validate <repo>
vibecode guard <repo>
vibecode check <repo>
vibecode handoff-check <repo>
vibecode run <repo> --platform opencode --task "..."
```

### Acceptance criteria

- README, quickstart, CLI help a docs používají stejné názvy.
- Žádné duplicitní aliasy, pokud nejsou výslovně dokumentované.

---

## 6.2 Project registry

### Cíl

Nemuset pořád psát cestu k repu.

### Příkazy

```powershell
vibecode project add STOCKS C:\DATA\PROJECTS\STOCKS
vibecode project use STOCKS
vibecode context --task "..."
```

### Registry

Lokální user-level registry:

```text
~/.vibecode/projects.yaml
```

### Acceptance criteria

- Lze přidat projekt podle jména.
- Lze vybrat aktivní projekt.
- Příkazy umí použít aktivní projekt bez explicitní cesty.

---

# Fáze 7 — GUI / VibecodeApp shell

GUI až po stabilním CLI jádru. Jinak vznikne hezký panel nad nehotovým systémem.

## 7.1 Minimum obrazovek

### Projects

- seznam rep,
- clean/dirty/stale stav,
- poslední handoff,
- poslední index status.

### Project detail

- architecture docs,
- generated map status,
- required checks,
- handoff,
- protected paths.

### Run

- task input,
- platform selector,
- context preview,
- permission profile,
- run button.

### Review

- diff summary,
- guard results,
- tests/checks,
- handoff status,
- approve/reject.

### Acceptance criteria

- GUI nevytváří druhou pravdu.
- GUI používá stejné core funkce jako CLI.
- GUI není editor, ale stavbyvedoucí panel.

---

# Fáze 8 — MCP a code intelligence

Až po stabilním OpenCode flow.

## 8.1 Vibecode MCP server

### Nástroje

```text
get_project_context
get_architecture_map
get_invariants
get_relevant_files
get_required_checks
record_handoff
guard_diff
```

### Acceptance criteria

- MCP čte stejnou projektovou pravdu jako CLI.
- MCP nesmí být bezpečnostní hranice; policy drží VibecodeApp.

---

## 8.2 Serena / symbolické nástroje

Přidat až po jasném use-casu.

Možné použití:

```text
find_symbol
find_references
replace_symbol_body
overview_file
```

### Riziko

Příliš mnoho nástrojů agentovi nepomůže. Ztratí se. Každý tool musí mít jasné pravidlo použití.

---

# Fáze 9 — Memory

Memory až později. Nejdřív musí fungovat mapy, guard, handoff a agent run.

## 9.1 Komprimovaná projektová paměť

Nejdřív jednoduché soubory:

```text
.vibecode/history/
.vibecode/decisions/
.vibecode/memory/known_failures.md
.vibecode/memory/lessons_learned.md
```

Později SQLite/graph.

---

## 9.2 Decision records

Když se změní architektura nebo zásadní pravidlo, vznikne decision record:

```text
.vibecode/decisions/ADR-xxxx-title.md
```

### Acceptance criteria

- Žádná zásadní změna architektury bez decision recordu.
- Decision record je stručný a vysvětluje důvod, ne jen výsledek.

---

# Doporučené pořadí dalších Ralph loop úkolů

## Task 1 — Improve repo tree architecture usefulness

```text
Improve repo_tree.generated.md so it shows useful architecture orientation, important modules, roles, and test/source grouping.
```

Acceptance:

- ukazuje hlavní source moduly,
- ukazuje `vibecode/indexer/`, `vibecode/context/`, tests a config/docs,
- neklasifikuje `vibecode/` jako tests,
- nezahrnuje generated/runtime bordel,
- má test na druhou úroveň mapy.

---

## Task 2 — Align relevant-file scoring with the Architecture Map PRD

```text
Extend deterministic relevant-file scoring using handoff, history, dependency map, architecture references, source/test pairing, and recent git changes.
```

Acceptance:

- scoring vrací správné soubory pro tasky o repo tree, context packu, CLI a checks,
- generated/runtime soubory nejsou preferované,
- testy pokrývají minimálně tři typy tasků.

---

## Task 3 — Add root AGENTS.md safely

```text
Generate or author short root AGENTS.md that points agents to .vibecode project truth without treating generated/current files as canonical.
```

Acceptance:

- root `AGENTS.md` existuje,
- je krátký,
- odkazuje na `.vibecode/architecture/INVARIANTS.md`, `.vibecode/architecture/STRUCTURE.md`, `.vibecode/handoff/NOW.md`, required checks,
- nevaruje falešně ani neodkazuje na stale current soubory jako pravdu.

---

## Task 4 — Add guard command

```text
Implement vibecode guard <repo> to detect protected path violations, generated/runtime edits, stale index state, and missing handoff updates.
```

Acceptance:

- má CLI command,
- vrací non-zero při tvrdém porušení,
- má testy pro protected paths a generated/runtime změny.

---

## Task 5 — Add check runner

```text
Implement vibecode check <repo> to run .vibecode/checks/required_checks.yaml and store ignored check results.
```

Acceptance:

- spouští konkrétní commandy,
- ukládá výsledek do `.vibecode/current/check_results.json`,
- testuje passing i failing command.

---

## Task 6 — Add handoff validation

```text
Implement handoff-check that rejects placeholder handoff files and requires concrete NOW/NEXT/BLOCKERS content after meaningful changes.
```

Acceptance:

- placeholder neprojde,
- konkrétní handoff projde,
- výstup říká, co chybí.

---

## Task 7 — Add OpenCode run adapter

```text
Implement vibecode run <repo> --platform opencode --task "..." using generated context/opencode prompt, guard, checks, and run logs.
```

Acceptance:

- run nezačne bez git/status preflightu,
- uloží run metadata,
- po doběhu spustí guard a checks,
- ukáže diff summary.

---

## Task 8 — Add project registry

```text
Implement local project registry so user can add/use repos by name instead of passing paths every time.
```

Acceptance:

- `project add`, `project use`, `project list`,
- aktivní projekt lze použít pro `context`, `index`, `map`, `run`.

---

## Task 9 — Minimal GUI

```text
Build first VibecodeApp shell: project selector, map status, context preview, task input, platform selector, run output, diff/guard results.
```

Acceptance:

- GUI používá stejné core funkce jako CLI,
- nevytváří vlastní stav pravdy,
- umí zobrazit project status, context preview a run/review stav.

---

# Co teď výslovně nedělat

Teď nedělat:

- swarm,
- multi-agent workflow,
- knowledge graph,
- velké GUI,
- automatickou LLM memory summarizaci,
- vlastní coding agent,
- vlastní editor,
- přímou symbolickou editaci kódu,
- velký refactor architektury.

Tohle všechno může počkat. Pokud se to přidá teď, projekt se rozpadne do šířky dřív, než bude pevný do hloubky.

---

# Nejbližší správný krok

Nejbližší konkrétní úkol:

```text
Improve repo_tree.generated.md so it becomes a real architecture orientation map.
```

Tvrdá acceptance:

- ukazuje hlavní source moduly,
- ukazuje context/indexer/test oblasti,
- neklasifikuje `vibecode/` jako tests,
- ukazuje důležité soubory druhé úrovně,
- nezahrnuje generated/runtime bordel,
- má test na aktuální VibecodeApp repo nebo fixture repo.

Až potom má smysl řešit relevant-file scoring, root `AGENTS.md`, guard layer a OpenCode adapter.

---

# Finální verdikt

VibecodeApp má dobrý základ. Ale základ není produkt.

Momentální stav:

```text
repo scanner + architecture map + context pack generator
```

Cílový stav:

```text
project control layer over coding agents
```

Mezera mezi tím je hlavně:

- užitečnější architektonická mapa,
- přesnější výběr relevantních souborů,
- guardrails,
- handoff enforcement,
- checks runner,
- agent run adapter,
- project registry,
- až nakonec GUI.

Největší riziko teď není technické. Největší riziko je znovu přeskočit disciplínu a začít stavět líbivé vrstvy nad polovičním jádrem. To by byla chyba.
