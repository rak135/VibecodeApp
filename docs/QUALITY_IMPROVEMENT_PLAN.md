# Quality Improvement Plan

Identified gaps in implemented (`completed: true`) PRD tasks, ordered by impact. Each entry describes the current state, why improvement matters, and a concrete step-by-step plan.

---

## 1. Guard CLI neposílá test_map → slabé source/test warningy

### Stav dnes

`cmd_guard` v `guard.py:725` volá:
```python
result = evaluate_project_guard(git_state, vibecode_dir, task="", test_map=None)
```

`test_map=None` způsobí, že `check_source_test_change_balance` vždy použije jen heuristický fallback `_suggested_tests_for_source` (hádej `tests/test_{stem}.py`). Přitom `test_map.json` obsahuje přesná párování source→test z indexu. Guard je tedy v CLI režimu hluchý k datům z indexu.

Důsledek: změníš-li `scoring.py`, guard řekne "source changed, add tests" ale neřekne "spusť `python -m pytest tests/test_vibecode_relevant_files.py`" — i když `DEFAULT_PROTECTED_PATH_RULES` by to věděl a guard rules engine by to uměl (`check_protected_path_changes` vrací `required_tests`).

### Proč zlepšit

- **Ušetří čas** — agent/člověk vidí rovnou exact test command, ne generic warning
- **Konzistence** — guard CLI a post-run guard v `run.py` chování se liší (post-run guard dostane task string, ale stále ne test_map)
- **Důvěryhodnost** — guard má data, ale nepoužívá je; to vytváří falešný dojem, že guard je slabší než ve skutečnosti je

### Plán

1. V `cmd_guard` načíst `test_map.json` z `.vibecode/index/test_map.json` (pokud existuje) a předat ho do `evaluate_project_guard`.
2. Upravit `evaluate_project_guard` signaturu: už bere `test_map` parametr, jen ho CLI neposílá.
3. Přidat unit test pro CLI guard s test_mapem: vytvoř temp repo, spusť `vibecode index`, změň source soubor, zavolej `cmd_guard` — assertion že finding obsahuje konkrétní test command.

**Dotčené soubory:** `vibecode/guard.py`, `tests/test_vibecode_guard.py`, `tests/test_vibecode_guard_cli.py`

---

## 2. Guard dedup maskuje multi-pravidlové nálezy na stejném souboru

### Stav dnes

`_dedupe_findings` v `guard.py:669-683`:
```python
key = (finding.severity, finding.path)
if finding.rule_id in {ARCHITECTURE_TRUTH_RECORD_RULE_ID, SOURCE_TEST_BALANCE_RULE_ID}:
    key = (*key, finding.rule_id)
```

Jen 2 z 5 rule_id jsou zahrnuty do dedup klíče. Ostatní (generated-runtime, protected-path, readme) se deduplikují jen podle `(severity, path)`. Když například smažeš `.vibecode/generated/AGENTS.generated.md`:

- `check_generated_runtime_changes` → finding (rule_id=generated-runtime-files, severity=error)
- `check_protected_path_changes` → finding (rule_id=protected-path-generated, severity=error)

Protože oba mají `(severity="error", path=".vibecode/generated/AGENTS.generated.md")`, druhý finding je tiche zahozen. Uživatel vidí jen "Regenerate generated files" a ne "Generated/runtime protected path changed".

### Proč zlepšit

- **Transparentnost** — každé porušení pravidel by mělo být hlášeno; tiché shazování matou
- **Prediktabilita** — chování závisí na pořadí pravidel v evaluate_guard (první vyhrává)
- **Jen 2 řádky kódu** — oprava je triviální

### Plán

1. Rozšířit dedup klíč na `(finding.severity, finding.path, finding.rule_id)` pro všechna pravidla.
2. Zjednodušit `_dedupe_findings` — odstranit podmíněnou logiku, všechny findings mají unikátní `(severity, path, rule_id)`.
3. Přidat test: vytvoř soubor který je generated AND protected, assertion že guard vrací **2 findings** (ne 1).

**Dotčené soubory:** `vibecode/guard.py`, `tests/test_vibecode_guard.py`

---

## 3. Duplicitní DOMAIN_EXTENSIONS ve scoringu

### Stav dnes

`scoring.py:108-140`:
```python
_DOMAIN_EXTENSIONS: dict[str, frozenset[str]] = {
    "agent": frozenset({".py", ".md"}),
    "agents": frozenset({".py", ".md"}),          # duplicitní
    "check": frozenset({".py", ".yaml", ".yml"}),
    "checks": frozenset({".py", ".yaml", ".yml"}), # duplicitní
    "doc": frozenset({".md"}),
    "docs": frozenset({".md"}),                     # duplicitní
    "render": frozenset({".py", ".ts", ".tsx"}),
    "renderer": frozenset({".py", ".ts", ".tsx"}),  # duplicitní
    "rendering": frozenset({".py", ".ts", ".tsx"}), # duplicitní
    "scan": frozenset({".py"}),
    "scanner": frozenset({".py"}),                  # duplicitní
    "score": frozenset({".py"}),
    "scoring": frozenset({".py"}),                  # duplicitní
    "symbol": frozenset({".py", ".json"}),
    "symbols": frozenset({".py", ".json"}),         # duplicitní
    "test": frozenset({".py", ".ts", ".tsx", ".js", ".jsx"}),
    "tests": frozenset({".py", ".ts", ".tsx", ".js", ".jsx"}), # duplicitní
    # ... zbytek OK
}
```

_DOMAIN_EXTENSIONS mapuje task keyword → přípony souborů, které dostanou +2 boost. Klíče "agent" a "agents" mapují na stejnou hodnotu, protože tokenizace v `_task_keywords` generuje oba tvary. Není to bug — boost se aplikuje stejně. Ale udržovat duplicity je zbytečné.

### Proč zlepšit

- **Údržba** — přidání nové přípony vyžaduje změnu na 2 místech místo 1, snadno se udělá chyba
- **Čistota kódu** — codebase je jinak velmi čistá, tahle duplicita je outlier
- **Riziko divergence** — někdo přidá ".css" k "render" ale zapomene na "renderer" a "rendering"

### Plán

1. Odstranit singular/plural duplicity — ponechat jen plurálové tvary (nebo jen základní). Tokenizace v `_task_keywords` (ř. 515-527) již řeší že "rendering" → ["rendering", "render", "ring"] a "render" → ["render"]. Každý keyword je samostatně matchován proti _DOMAIN_EXTENSIONS, takže:
   - Pokud task obsahuje "rendering" a _DOMAIN_EXTENSIONS má jen "render" → boost se neaplikuje
   - **Nutno vyřešit:** tokenizace "rendering" vyrobí ["rendering", "render"] — tyto tokeny pak matchují proti klíčům. Musíme se ujistit, že "render" je v _DOMAIN_EXTENSIONS.
2. Algoritmus: zachovat nejdelší tvar, smazat kratší duplicity:
   - Zachovat: "agents", "checks", "docs", "renderer" (nebo "rendering"), "scanner", "scoring", "symbols", "tests"
   - Smazat: "agent", "check", "doc", "render", "rendering" (nebo "renderer"), "scan", "score", "symbol", "test"
3. Ověřit že testy pro scoring stále passují (zejména compound phrase routing testy).

**Dotčené soubory:** `vibecode/context/scoring.py`, `tests/test_vibecode_relevant_files.py`

---

## 4. Arch doc funkce divergentní mezi guardem a scoringem

### Stav dnes

**Guard** (`guard.py:536-539`):
```python
def _is_architecture_doc_path(path: str) -> bool:
    if not path.startswith(".vibecode/architecture/") or not path.endswith(".md"):
        return False
    return "/" not in path.removeprefix(".vibecode/architecture/")
```
Pouze `.vibecode/architecture/*.md`.

**Scoring** (`scoring.py:778-785`):
```python
def _is_architecture_doc(path: str) -> bool:
    lower = path.lower()
    return (
        lower.startswith(".vibecode/architecture/")
        or "/architecture/" in lower
        or (lower.startswith("docs/") and "architecture" in name and name.endswith(".md"))
    )
```
`.vibecode/architecture/*`, `*/architecture/*`, `docs/*architecture*.md`.

Dvě funkce se stejným účelem ale jinou implementací. Guard je striktnější (jen `.vibecode/architecture/`), scoring je benevolentnější. To může vést k situaci, kdy scoring boostne soubor jako architecture doc, ale guard ho nechrání.

### Proč zlepšit

- **Bezpečnost** — guard by měl chránit vše, co scoring považuje za architecture doc
- **Konzistence** — stejný koncept by měl mít stejnou definici napříč kódem
- **DRY** — duplicitní kód = duplicitní údržba

### Plán

1. Extrahovat sdílenou funkci `is_architecture_doc(path: str) -> bool` do nového pomocného modulu `vibecode/_path_classify.py` (nebo přidat do `vibecode/paths.py`).
2. Použít guardí definici jako canonical — striktní `".vibecode/architecture/"` je bezpečnější.
   - Zdůvodnění: `docs/` adresář může obsahovat cokoliv; scoring by neměl boostovat cokoliv v `docs/` jako architecture doc.
   - Pokud je potřeba širší definice pro scoring, zdokumentovat proč a sjednotit obě funkce pod jednu s parametrem.
3. Nahradit obě původní funkce voláním canonical.
4. Přidat test: `assert is_architecture_doc(".vibecode/architecture/DATA_FLOW.md")`, `assert not is_architecture_doc("docs/architecture.md")`.

**Dotčené soubory:** `vibecode/paths.py` (nová funkce), `vibecode/guard.py`, `vibecode/context/scoring.py`, `tests/test_vibecode_paths.py`, `tests/test_vibecode_guard.py`, `tests/test_vibecode_relevant_files.py`

---

## 5. diff_summary importuje privátní funkce z guardu

### Stav dnes

`diff_summary.py:14-20`:
```python
from vibecode.guard import (
    _is_documentation_path,    # private!
    _is_generated_runtime_path, # private!
    _is_source_path,            # private!
    _is_test_path,              # private!
    _normalise_path,            # private!
)
```

Importuje 5 funkcí označených konvencí `_` jako interní. To je dependency anti-pattern. Změna v guardu (např. přejmenování `_is_generated_runtime_path`) rozbije `diff_summary` bez varování. Python to nekontroluje — `_` je jen konvence.

### Proč zlepšit

- **Stabilita** — diff_summary by se neměl rozbít při refactoringu guardu
- **Architektura** — guard a diff_summary jsou na stejné vrstvě, neměly by záviset jedna na druhé; měly by záviset na společném modulu
- **Testování** — nelze snadno mockovat privátní funkce

### Plán

1. Vytvořit `vibecode/_file_classifier.py` (nebo rozšířit `vibecode/paths.py`) s veřejnými funkcemi:
   - `is_source_path(path: str) -> bool`
   - `is_test_path(path: str) -> bool`  
   - `is_documentation_path(path: str) -> bool`
   - `is_generated_runtime_path(path: str) -> bool`
   - `normalise_path(path: str) -> str`
2. Přesunout implementace z `guard.py` do nového modulu.
3. Nechat `guard.py` re-exportovat nebo importovat z nového modulu (backward compat).
4. Upravit `diff_summary.py` aby importoval z nového modulu.
5. Odstranit privátní prefix `_` z funkcí v novém modulu.
6. Přidat testy pro nový modul.

**Dotčené soubory:** `vibecode/_file_classifier.py` (nový), `vibecode/guard.py`, `vibecode/diff_summary.py`, `tests/test_vibecode_guard.py` (aktualizovat importy), `tests/test_vibecode_diff_summary.py`, `tests/test_vibecode_file_classifier.py` (nový)

---

## 6. HUMAN_MAINTAINED_PATHS je hardcodovaný frozenset

### Stav dnes

`write_rules.py:18-34`:
```python
HUMAN_MAINTAINED_PATHS: frozenset[str] = frozenset({
    ".vibecode/project.yaml",
    ".vibecode/checks/required_checks.yaml",
    ".vibecode/architecture/OVERVIEW.md",
    ".vibecode/architecture/INVARIANTS.md",
    # ... 10 dalších explicitních cest
})
```

Seznam 14 pevně zadaných cest. Když `vibecode init` vytvoří nový architecture doc nebo agent profil, musí se tento seznam ručně updatovat. Pokud se zapomene, `safe_write` v `write_rules.py:58-71` nepovolí zápis do nové cesty (PermissionError) nebo naopak povolí přepsání lidského souboru.

### Proč zlepšit

- **Autom concatenation** — přidání nového template souboru by mělo automaticky aktualizovat seznam chráněných cest
- **Bezpečnost** — hardcodovaný seznam je křehký; snadno vznikne mezera (nový soubor není chráněný) nebo false positive (starý smazaný soubor stále blokuje zápis)
- **Zdroj pravdy** — definice "co je human-maintained" by měla být v configu/templatech, ne v izolovaném frozensetu

### Plán

1. Definovat canonical seznam human-maintained cest v `vibecode/project.py` (kde jsou definovány arch template soubory a agent profily).
2. V `write_rules.py` dynamicky sestavit `HUMAN_MAINTAINED_PATHS` z:
   - Template arch souborů z `project.py`
   - Agent profilových cest z `permissions.py`
   - Explicitních cest (project.yaml, required_checks.yaml, handoff files, history/README.md)
3. Zachovat možnost přidat extra cesty přes `project.yaml` (human-maintained-extra field).
4. Ověřit, že `write_rules` testy stále passují a že init/index nevyhazují PermissionError.

**Dotčené soubory:** `vibecode/write_rules.py`, `vibecode/project.py`, `vibecode/config.py` (volitelně), `tests/test_vibecode_write_rules.py`

---

## 7. Stale index detection necítí untracked/nové soubory

### Stav dnes

`indexer/__init__.py:60-109` — `check_index_freshness` používá 2 kritéria:
1. Stáří indexu (>5 minut → stale)
2. Git commit se změnil od doby indexování

Ani jedno nezachytí scénář: "přidal jsem nový `src/feature.py` ale ještě jsem necommitnul". Index je považován za fresh (commit je stejný, age je v pořádku), ale inventory neobsahuje nový soubor. Context pack pak neví o `feature.py`.

Podobně: smazal jsem soubor, přejmenoval jsem soubor (git detekuje rename až po commitu), změnil jsem .gitignore.

### Proč zlepšit

- **Přesnost** — index by měl být označen jako stale kdykoliv se změní sada sledovaných souborů, nejen když se změní commit
- **Agent safety** — agent dostane nekompletní context pack a může dělat špatná rozhodnutí
- **User experience** — "index is fresh" je zavádějící, když chybí nové soubory

### Plán

1. Do `last_index.json` přidat pole `source_file_set_hash`:
   - Při indexaci: spočítat hash ze seznamu všech sledovaných source/test/doc/config souborů (relativní cesty, seřazené)
   - Při kontrole freshness: spočítat hash aktuálního seznamu a porovnat
2. Použít lehký hash (např. SHA256 ze sorted joinu cest) — nečíst obsah souborů, jen cesty.
3. Ignorovat generated/runtime cesty v obou haších (už jsou v .gitignore).
4. Přidat warning: "Index file set has changed (N files added, M removed, K renamed) — run 'vibecode index'."
5. Upravit `run_plan.py` i `indexer/__init__.py` — oba používají `check_index_freshness`.

**Dotčené soubory:** `vibecode/indexer/__init__.py`, `vibecode/indexer/run_record.py`, `vibecode/run_plan.py`, `vibecode/context/__init__.py` (pokud volá check_index_freshness), `tests/test_vibecode_stale_index.py`

---

## 8. Run preflight neověřuje že inventory není prázdné

### Stav dnes

`run.py:376-414` — preflight kontroluje jen jestli `last_index.json` existuje a není stale. Neověřuje, že `file_inventory.json`:
- existuje
- není prázdný (má alespoň nějaké files)
- má validní JSON strukturu

Scénář: `vibecode index` selže tiše (např. YAML chyba v project.yaml způsobí že load_config spadne, ale cmd_index chytí výjimku a vrátí 1 — ale run.py:407-410 kontroluje jen `rc != 0` a skončí). OK, to je ošetřeno.

Jiný scénář: index proběhne ale naskenuje 0 souborů (např. include pattern je příliš restriktivní). `file_inventory.json` bude mít `"files": []`. Run preflight to neodhalí.

### Proč zlepšit

- **Early failure** — lepší selhat hned s "Inventory is empty, check your include/exclude patterns" než po 5 minutách agent runu s prázdným context packem
- **Debugging** — uživatel hned ví že problém je v konfiguraci indexování

### Plán

1. V `cmd_run` přidat kontrolu: načíst `file_inventory.json`, zkontrolovat že `len(data.get("files", [])) > 0`.
2. Pokud je prázdný, vypsat warning (nebo error) s návodem: "Run 'vibecode index' and verify include/exclude patterns in .vibecode/project.yaml."
3. Přidat stejnou kontrolu do `build_run_plan` v `run_plan.py` (preflight).
4. Test: vytvoř repo s include patternem který nic nematchuje, spusť `vibecode index`, pak `vibecode run-plan` — assertion že preflight error obsahuje "empty inventory".

**Dotčené soubory:** `vibecode/run.py`, `vibecode/run_plan.py`, `tests/test_vibecode_run.py`, `tests/test_vibecode_run_plan.py`

---

## Souhrnná tabulka

| # | Gap | Files affected | New tests | Priorita |
|---|---|---|---|---|
| 1 | Guard CLI bez test_map | `guard.py`, test_guard*.py | 1–2 | Střední |
| 2 | Dedup maskuje findings | `guard.py`, test_guard.py | 1 | Střední |
| 3 | Duplicitní DOMAIN_EXTENSIONS | `scoring.py`, test_relevant_files.py | 0 (stávají) | Nízká |
| 4 | Arch doc funkce divergentní | `paths.py`(new), `guard.py`, `scoring.py`, testy | 2–3 | Střední |
| 5 | diff_summary importuje private API | `_file_classifier.py`(new), `guard.py`, `diff_summary.py`, testy | 5–8 | Střední |
| 6 | HUMAN_MAINTAINED_PATHS hardcoded | `write_rules.py`, `project.py`, testy | 1–2 | Nízká |
| 7 | Stale index necítí untracked | `indexer/__init__.py`, `run_record.py`, `run_plan.py`, testy | 2–3 | Střední |
| 8 | Run preflight neověřuje inventory | `run.py`, `run_plan.py`, testy | 1–2 | Nízká |
