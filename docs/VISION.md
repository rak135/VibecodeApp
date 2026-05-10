# Vize VibecodeApp – Inteligentní vývojové prostředí řízené agenty

## Severní hvězda
Vytvořit aplikaci, která změní způsob, jakým programátoři spolupracují s AI agenty. Místo chaotického předávání promptů a náhodných výsledků chceme deterministické, strukturované a vizuálně řízené pracovní postupy. Agent dostane do kontextu přesně to, co potřebuje, nic víc, nic míň. Výstupem je kód, který odpovídá tvému stylu, prošel kontrolami a je okamžitě připravený k nasazení.

## Základní principy

| Princip | Popis |
|---|---|
| **Kontext na prvním místě** | Před každou akcí agent získá strukturovanou mapu repa, včetně symbolů, závislostí, testů a chráněných oblastí. Nikdy nehledá naslepo. |
| **Determinismus** | Stejný vstup + stejná pravidla = stejný výstup. Agenti dodržují definované šablony, stylové konvence a architektonická rozhodnutí. |
| **Orchestrace, ne chaos** | Multi-agentní týmy s jasnými rolemi (Architekt, Stavitel, Recenzent) pracují paralelně podle Kanban boardu. |
| **Transparentnost** | Vše, co agent dělá, je vidět v reálném čase v GUI – diffy, logy, rozhodnutí. |
| **Kontinuální kvalita** | Automatické testy, linting, formátování, aktualizace dokumentace – vše probíhá jako součást cyklu. |

## Architektura systému
┌──────────────────────────────────────┐
│ GUI (VibecodeSpace) │
│ Kanban board | Multi-agent terminál | Inspekce difů │
└──────────────────┴───────────────────┘
┌──────────────────────────────────────┐
│ Orchestrátor (Swarm) │
│ Architekt | Stavitelé (1..n) | Recenzent │
└──────────────────┴───────────────────┘
┌──────────────────────────────────────┐
│ Kontextová vrstva (MCP) │
│ Index repa | Sdílená paměť | Automatické aktualizace │
└──────────────────┴───────────────────┘
┌──────────────────────────────────────┐
│ CLI jádro (Vibecode) │
│ Init | Context | Guard | Check | Docs | Style │
└──────────────────────────────────────┘

text

## Kontextová vrstva – Úplná mapa repa

Inspirováno BridgeMind a jeho Modelem kontextového protokolu (MCP), VibecodeApp udržuje **perzistentní znalostní bázi projektu**, která se automaticky aktualizuje při každé změně kódu.

### Součásti kontextu

| Komponenta | Význam |
|---|---|
| **Inventář souborů** | Kompletní strom repozitáře, klasifikace souborů podle typu a role (zdrojový, testovací, konfigurační…) |
| **Mapa symbolů** | Všechny třídy, funkce, metody i s jejich umístěním |
| **Mapa závislostí** | Importy a vazby mezi moduly |
| **Vstupní body** | Hlavní spustitelné soubory, API endpointy |
| **Rizikové soubory** | Chráněné oblasti, generovaný kód, do kterých se nesmí zasahovat |
| **Sdílená paměť (memories)** | Poznatky agentů o architektuře, rozhodnutích, pastích – aby další agent nezačínal od nuly |

### Jak se kontext dostane k agentovi

1. Agent dostane úkol v přirozeném jazyce.
2. **Context pack** automaticky vybere relevantní soubory podle dvouprůchodového scoringu (nejprve přímá relevance, poté spárované testy).
3. Agent může také použít nástroje pro vyhledávání v indexu (fulltext i sémantické).
4. Po skončení práce agent zapíše nové poznatky do sdílené paměti.

## Orchestrace agentů – Swarm

Každý úkol není vyřizován jedním monolitickým agentem. Místo toho **Orchestrátor** rozdělí úkol na podúkoly a přidělí je specializovaným agentům.

### Role v týmu

| Role | Odpovědnost |
|---|---|
| **Architekt** | Analyzuje požadavek, navrhne řešení, rozdělí práci na podúkoly, vytvoří plán. Zakázáno psát kód. |
| **Stavitel** (1..n) | Implementuje přidělené podúkoly podle plánu a stylových konvencí. Může vytvářet další subagenty pro izolované části. |
| **Recenzent** | Kontroluje diffy, spouští testy, linting, kontrolu stylu. Schvaluje nebo vrací k přepracování. |

### Pracovní postup (workflow)

1. **Plánování** – Architekt vytvoří plán a karty v Kanbanu.
2. **Stavba** – Stavitelé paralelně pracují na kartách. Vytváří pull requesty (nebo přímé commity).
3. **Revize** – Recenzent každou změnu prověří. Pokud najde chybu, vrátí kartu zpět do „In Progress“.
4. **Dokončení** – Po schválení se aktualizuje dokumentace a kontextová vrstva.

## GUI – VibecodeSpace

GUI je vizuální pracovní plocha, která umožňuje řídit celý proces bez dotyku příkazové řádky. Inspiruje se BridgeSpace od BridgeMind, ale je plně open-source.

### Rozložení obrazovky
┌────────────────────────────────────────────────────────────────────┐
│ Toolbar: Projekt | Nastavení | Spustit agenty | Aktuální uloha │
┌───────────────────────────────────────┬──────────────────────────────┐
│ Kanban board │ Terminálový panel │
│ To Do | In Progress | Review | Done │ │
│ ┌──────────┐ | ┌──────────┐ | ┌──────────┐ | ┌──────────┐ │ [Agent: Architekt] │
│ │ Karta 1 │ | │ Karta 2 │ | │ Karta 3 │ | │ Karta 4 │ │ Plánuji architekturu a zakládám tasky.│
│ └──────────┘ | └──────────┘ | └──────────┘ | └──────────┘ │ ──────────────────────────────────│
│ │ [Agent: Stavitel 1] │
│ │ Implementuji funkci X, přidávám testy. │
│ ┌──────────┐ | ┌──────────┐ | | │
│ │ T5: Testy │ | │ T3: úprava README │ | | │
│ └──────────┘ | └──────────┘ | | │
└───────────────────────────────┴──────────────────────────────────────┘

Legend: [A1] = Stavitel 1, [A2] = Stavitel 2, [A3] = Stavitel 3, [sub] = subagent

text

### Klíčové vlastnosti GUI

- **Kanban board** – vizualizace všech úkolů s drag & drop, přiřazováním agentům.
- **Multi-panel terminál** – každý agent běží ve vlastním panelu (s možností až 16 paralelních sezení). Uživatel vidí, co agent právě dělá.
- **Inspektor difů** – před schválením změn si uživatel může prohlédnout všechny diffy.
- **Správa subagentů** – agent může vytvořit subagenta pro izolovaný úkol, který se objeví jako další panel.
- **Hlasové ovládání** – volitelně lze zadávat příkazy hlasem (BridgeVoice inspirace).

## Automatická kvalita a styl

Cílem je, aby každý nový projekt vypadal jako od stejného vývojáře. Proto VibecodeApp poskytuje:

| Nástroj | Účel |
|---|---|
| **Projektové šablony** | `vibecode new python-cli myproject` vytvoří kompletní kostru včetně testů, CI, lintingu, dokumentace a kontextové vrstvy. |
| **Stylové konvence** | Definované v souboru, automaticky vynucované lintem (ruff, eslint). Agent je dostane do kontextu jako Tier 1. |
| **Automatická dokumentace** | Po každé změně se aktualizuje README, API dokumentace a další generované soubory. |
| **Kontinuální testování** | Testy se spouští automaticky před každým commitem. |

## Vývojový cyklus projektu

1. **Inicializace**: `vibecode new python-cli myapp` – vytvoří se projekt, indexuje se repo.
2. **Definice úkolu**: V GUI vytvořím kartu v Kanbanu s popisem.
3. **Provedení**: Architekt naplánuje, Stavitelé implementují, Recenzent zkontroluje.
4. **Aktualizace**: Po schválení se automaticky aktualizuje README, dokumentace, index repa a sdílená paměť.
5. **Release**: Vygeneruje se changelog, bump verze, tag.

## Kanban znázornění (detail)
╔════════════════════════════════════════════════════════════════════╗
║ KANBAN BOARD – Aktuální úloha: Přidej login stránku ║
╠══════════════════════════╦══════════════════════════╦══════════════════════════╦══════════════════════════╗
║ To Do ║ In Progress ║ Review ║ Done ║
╠══════════════════════════╬══════════════════════════╬══════════════════════════╬══════════════════════════╣
║ ┌──────────────────────┐ ║ ┌──────────────────────┐ ║ ┌──────────────────────┐ ║ ┌──────────────────────┐ ║
║ │ T1: Návrh API │ ║ │ T2: Impl. backend [A1] │ ║ │ T4: Frontend [A3] │ ║ │ T0: Init repo [done] │ ║
║ │ │ ║ │ │ ║ │ │ ║ │ │ ║
║ │ [Architekt] │ ║ │ │ ║ │ [Recenzent] │ ║ │ │ ║
║ └──────────────────────┘ ║ └──────────────────────┘ ║ └──────────────────────┘ ║ └──────────────────────┘ ║
║ ║ ║ ║ ║
║ ┌──────────────────────┐ ║ ┌──────────────────────┐ ║ ║ ║
║ │ T5: Testy [sub] │ ║ │ T3: úprava README [A2] │ ║ ║ ║
║ └──────────────────────┘ ║ └──────────────────────┘ ║ ║ ║
╚══════════════════════════╩══════════════════════════╩══════════════════════════╩══════════════════════════╝

Legenda: [A1] = Stavitel 1, [A2] = Stavitel 2, [A3] = Stavitel 3, [sub] = subagent

text

## Plánovaný harmonogram (roadmap)

| Fáze | Cíl |
|---|---|
| **Fáze 1 🔵** (nyní) | Stabilní CLI jádro, indexace, context packy, guard, check, handoff. (HOTOVO) |
| **Fáze 2 🟡** | Sdílená paměť a sémantické vyhledávání (BridgeMind inspirace). Aktualizace indexu na základě diffu. |
| **Fáze 3 🟢** | Orchestrátor a multi-agentní role (Architekt, Stavitel, Recenzent). |
| **Fáze 4 🟣** | GUI – VibecodeSpace s Kanban boardem a multi-panel terminálem. |
| **Fáze 5 🔴** |  Projektové šablony, stylové konvence, automatická dokumentace, hlasové ovládání. |

## Proč je to jiné než aider a BridgeMind

- **Aider** je skvělý pair-programmer, ale chybí mu orchestrace více agentů a strukturovaný kontext. VibecodeApp je nadstavba, která mu tento kontext dodá.
- **BridgeMind** je komerční a uzavřený. VibecodeApp přebírá jeho nejlepší myšlenky, ale zůstává open-source a rozšiřitelný.

## Závěr

VibecodeApp se mění z pouhého CLI nástroje na kompletní vývojové prostředí, které z tebe dělá dirigenta, ne překladače promptů. Místo abys řešil, co agentovi říct, aby nekazil kód, budeš mít jistotu, že dodržuje tvůj styl, prošel kontrolami a zapadá do architektury.

Chceš se soustředit na vizi, ne na syntax. A přesně to VibecodeApp umožní.