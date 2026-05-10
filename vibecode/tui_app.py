"""Textual TUI dashboard for vibecode context cards."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Label, Static
from textual.containers import ScrollableContainer


class DashboardData(NamedTuple):
    cards: list[dict]
    total_files: int
    high_risk_count: int


def load_dashboard_data(repo_root: Path) -> DashboardData:
    """Load context cards and risk data from .vibecode/index/.

    Returns a :class:`DashboardData` with cards, total file count, and
    high-risk item count derived from ``risk_report.json``.
    """
    from vibecode.data_loader import load_project_data

    project = load_project_data(repo_root)
    return DashboardData(
        cards=project.cards,
        total_files=project.total_files,
        high_risk_count=project.high_risk_count,
    )


def _symbols_summary(symbols: list[dict]) -> str:
    """Return a short summary string for the Symbols column."""
    if not symbols:
        return "—"
    counts: dict[str, int] = {}
    for sym in symbols:
        kind = sym.get("kind", "?")
        counts[kind] = counts.get(kind, 0) + 1
    parts = [f"{v} {k}" for k, v in sorted(counts.items())]
    return ", ".join(parts)


class CardDetailScreen(Screen):
    """Full card detail screen pushed on Enter."""

    BINDINGS = [
        Binding("escape,q", "app.pop_screen", "Back"),
    ]

    def __init__(self, card: dict) -> None:
        super().__init__()
        self._card = card

    def compose(self) -> ComposeResult:
        card = self._card
        path = card.get("path", "")
        purpose = card.get("purpose") or "(no docstring)"
        symbols: list[dict] = card.get("symbols", [])
        facts: list[dict] = card.get("facts", [])
        heuristics: list[dict] = card.get("heuristics", [])
        snippet: str = card.get("content_snippet", "")

        with ScrollableContainer(id="detail-container"):
            yield Label(path, id="detail-title")

            yield Label("Purpose", id="detail-purpose-label")
            yield Static(purpose, id="detail-purpose")

            yield Label(f"Symbols ({len(symbols)})", id="detail-symbols-label")
            sym_table = DataTable(id="detail-symbols-table")
            yield sym_table

            yield Label(f"Facts ({len(facts)})", id="detail-facts-label")
            facts_text = "\n".join(
                f"  [{f.get('kind', '?')}] line {f.get('line', 0)}: {f.get('text', '')}"
                for f in facts
            ) or "  (none)"
            yield Static(facts_text, id="detail-facts")

            yield Label(f"Heuristics ({len(heuristics)})", id="detail-heuristics-label")
            heuristics_text = "\n".join(
                f"  [{h.get('severity', '?')}] {h.get('kind', '?')} – {h.get('symbol', '')}: {h.get('detail', '')}"
                for h in heuristics
            ) or "  (none)"
            yield Static(heuristics_text, id="detail-heuristics")

            yield Label("Code Snippet", id="detail-snippet-label")
            yield Static(snippet or "(empty)", id="detail-snippet")

            yield Static("Press Escape or Q to go back.", id="back-hint")

    def on_mount(self) -> None:
        sym_table: DataTable = self.query_one("#detail-symbols-table", DataTable)
        sym_table.add_columns("Name", "Kind", "Line")
        for sym in self._card.get("symbols", []):
            sym_table.add_row(
                str(sym.get("name", "")),
                str(sym.get("kind", "")),
                str(sym.get("line", "")),
            )


class MainScreen(Screen):
    """Main screen showing a DataTable of context cards."""

    BINDINGS = [
        Binding("enter", "select_card", "View Detail"),
        Binding("q", "app.exit", "Quit"),
    ]

    def __init__(self, data: DashboardData) -> None:
        super().__init__()
        self._data = data

    def compose(self) -> ComposeResult:
        yield DataTable(id="main-table")
        yield Footer()

    def on_mount(self) -> None:
        table: DataTable = self.query_one("#main-table", DataTable)
        table.add_columns("File", "Purpose", "Symbols")
        for card in self._data.cards:
            path = card.get("path", "")
            purpose = (card.get("purpose") or "")[:80]
            symbols_summary = _symbols_summary(card.get("symbols", []))
            table.add_row(path, purpose, symbols_summary)

        d = self._data
        self.sub_title = (
            f"Files: {d.total_files}  Cards: {len(d.cards)}  High-Risk: {d.high_risk_count}"
        )

    def action_select_card(self) -> None:
        table: DataTable = self.query_one("#main-table", DataTable)
        if table.cursor_row < 0 or table.cursor_row >= len(self._data.cards):
            return
        card = self._data.cards[table.cursor_row]
        self.app.push_screen(CardDetailScreen(card))


class VibecodeTUI(App):
    """Interactive dashboard for vibecode context cards."""

    CSS_PATH = Path(__file__).with_name("tui_theme.tcss")
    TITLE = "Vibecode Dashboard"

    def __init__(self, repo_root: Path | None = None) -> None:
        super().__init__()
        self._repo_root = repo_root or Path.cwd()
        self._data: DashboardData | None = None

    def on_mount(self) -> None:
        self._data = load_dashboard_data(self._repo_root)
        self.push_screen(MainScreen(self._data))
