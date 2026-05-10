"""MCP server for vibecode – exposes file inventory and risk report as tools."""

from __future__ import annotations

import json
import sys
from pathlib import Path


class VibecodeServer:
    """Reads ``file_inventory.json`` and ``risk_report.json`` and answers MCP tool calls.

    The two JSON files are loaded once at construction time.  If a file is
    missing the server starts with an empty dataset and returns friendly error
    messages rather than crashing.
    """

    def __init__(self, inventory_path: Path, risk_report_path: Path) -> None:
        self._inventory = self._load_json(inventory_path, "file_inventory.json")
        self._risk_report = self._load_json(risk_report_path, "risk_report.json")

        # card index: normalised path → card dict
        self._cards: dict[str, dict] = {}
        for card in self._inventory.get("context_cards", []):
            self._cards[card["path"].replace("\\", "/")] = card

        # symbol index: symbol name → list of {file_path, name, kind, line}
        self._symbols: dict[str, list[dict]] = {}
        for card in self._inventory.get("context_cards", []):
            fp = card["path"]
            for sym in card.get("symbols", []):
                name = sym.get("name", "")
                if name:
                    entry = {"file_path": fp, **sym}
                    self._symbols.setdefault(name, []).append(entry)

        # risk index: normalised path → risk item dict
        self._risks: dict[str, dict] = {}
        for item in self._risk_report.get("files", []):
            self._risks[item["path"].replace("\\", "/")] = item

    @staticmethod
    def _load_json(path: Path, label: str) -> dict:
        if not path.exists():
            print(f"Warning: {label} not found at {path}", file=sys.stderr)
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"Warning: failed to load {label}: {exc}", file=sys.stderr)
            return {}

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def get_file_card(self, file_path: str) -> str:
        """Return a human-readable card for *file_path*.

        Fields rendered: purpose, symbols, snippet, facts, heuristics.
        """
        key = file_path.replace("\\", "/")
        card = self._cards.get(key)
        if card is None:
            return f"No context card found for: {file_path}"

        lines: list[str] = [f"# {card['path']}", ""]

        purpose = card.get("purpose")
        if purpose:
            lines += [f"**Purpose:** {purpose}", ""]

        symbols = card.get("symbols", [])
        if symbols:
            lines.append("**Symbols:**")
            for sym in symbols:
                lines.append(
                    f"  - {sym.get('kind', '?')} `{sym.get('name', '?')}` (line {sym.get('line', '?')})"
                )
            lines.append("")

        snippet = card.get("content_snippet", "")
        if snippet:
            lines += ["**Snippet:**", "```", snippet, "```", ""]

        facts = card.get("facts", [])
        if facts:
            lines.append("**Facts:**")
            for fact in facts:
                line_ref = f" (line {fact['line']})" if fact.get("line") else ""
                lines.append(f"  - [{fact.get('kind', '?')}]{line_ref} {fact.get('text', '')}")
            lines.append("")

        heuristics = card.get("heuristics", [])
        if heuristics:
            lines.append("**Heuristics:**")
            for h in heuristics:
                lines.append(
                    f"  - [{h.get('severity', '?')}] {h.get('kind', '?')}:"
                    f" `{h.get('symbol', '?')}` — {h.get('detail', '')}"
                )
            lines.append("")

        return "\n".join(lines)

    def find_symbol(self, symbol_name: str) -> str:
        """Return a JSON array of file paths and symbol details for *symbol_name*.

        Falls back to a case-insensitive match when the exact name is not found.
        Returns a JSON object with an ``error`` key when nothing matches.
        """
        matches = self._symbols.get(symbol_name)
        if not matches:
            lower = symbol_name.lower()
            for name, items in self._symbols.items():
                if name.lower() == lower:
                    matches = items
                    break
        if not matches:
            return json.dumps({"error": f"Symbol not found: {symbol_name}", "matches": []})
        return json.dumps(matches, indent=2)

    def list_high_risk(self) -> str:
        """Return high-severity heuristics from the risk report.

        Collects every file that has at least one heuristic with
        ``severity == "high"`` and returns them as a JSON array.
        """
        results: list[dict] = []
        for item in self._risk_report.get("files", []):
            high = [h for h in item.get("heuristics", []) if h.get("severity") == "high"]
            if high:
                results.append(
                    {
                        "path": item["path"],
                        "risk_level": item.get("risk_level"),
                        "high_severity_heuristics": high,
                    }
                )
        if not results:
            return "No high-severity heuristics found in the risk report."
        return json.dumps(results, indent=2)


def build_mcp_server(inventory_path: Path, risk_report_path: Path):  # type: ignore[return]
    """Build and return a :class:`~mcp.server.fastmcp.FastMCP` instance with vibecode tools."""
    from mcp.server.fastmcp import FastMCP

    vs = VibecodeServer(inventory_path, risk_report_path)
    mcp = FastMCP("vibecode")

    @mcp.tool()
    def get_file_card(file_path: str) -> str:
        """Return a human-readable card for a file: purpose, symbols, snippet, facts, heuristics."""
        return vs.get_file_card(file_path)

    @mcp.tool()
    def find_symbol(symbol_name: str) -> str:
        """Return a JSON array of locations and details for a symbol name."""
        return vs.find_symbol(symbol_name)

    @mcp.tool()
    def list_high_risk() -> str:
        """Return files with high-severity heuristics from the risk report."""
        return vs.list_high_risk()

    return mcp


def cmd_serve(args) -> int:
    """Start the vibecode MCP server with stdio transport.

    Prints a ready-to-paste OpenCode MCP configuration snippet to *stderr*
    before entering the blocking server loop.
    """
    from vibecode.paths import normalise_root

    repo_root = normalise_root(getattr(args, "repo_root", "."))
    index_dir = repo_root / ".vibecode" / "index"
    inventory_path = index_dir / "file_inventory.json"
    risk_report_path = index_dir / "risk_report.json"

    config_snippet = {
        "mcpServers": {
            "vibecode": {
                "command": "vibecode",
                "args": ["serve", str(repo_root).replace("\\", "/")],
            }
        }
    }
    print(
        "\nAdd to your OpenCode MCP configuration:\n"
        + json.dumps(config_snippet, indent=2)
        + "\n",
        file=sys.stderr,
    )

    mcp = build_mcp_server(inventory_path, risk_report_path)
    mcp.run(transport="stdio")
    return 0
