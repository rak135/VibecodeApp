"""MCP server for vibecode – exposes file inventory and risk report as tools."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


class VibecodeServer:
    """Reads ``file_inventory.json`` and ``risk_report.json`` and answers MCP tool calls.

    The two JSON files are loaded once at construction time.  If a file is
    missing the server starts with an empty dataset and returns friendly error
    messages rather than crashing.

    Parameters
    ----------
    event_sink:
        Optional sink that receives :class:`~vibecode.events.VibecodeEvent` objects.
        When provided, each tool call emits ``McpToolCalled``, ``McpToolReturned``,
        or ``McpToolFailed`` events with a compact result summary.  No large
        response blobs are stored — only counts, booleans, and ``result_chars``.
    session_id:
        Session identifier embedded in emitted events.  Falls back to the
        ``VIBECODE_SESSION_ID`` environment variable, then ``"mcp-server"``.
    """

    def __init__(
        self,
        inventory_path: Path,
        risk_report_path: Path,
        *,
        event_sink: Any | None = None,
        session_id: str | None = None,
    ) -> None:
        self._inventory = self._load_json(inventory_path, "file_inventory.json")
        self._risk_report = self._load_json(risk_report_path, "risk_report.json")
        self._sink = event_sink
        self._session_id = session_id or os.environ.get("VIBECODE_SESSION_ID") or "mcp-server"

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
        from vibecode.data_loader import _load_json as _shared_load

        data, missing = _shared_load(path)
        if missing:
            print(f"Warning: {label} not found at {path}", file=sys.stderr)
        return data

    # ------------------------------------------------------------------
    # Logging helper
    # ------------------------------------------------------------------

    def _emit(self, message: str, data: dict | None = None, *, error: bool = False) -> None:
        """Emit an MCP event to the configured sink.  No-op when no sink is set."""
        if self._sink is None:
            return
        from vibecode.events import EVENT_MCP, EventLevel, create_event

        level = EventLevel.ERROR if error else EventLevel.INFO
        event = create_event(
            session_id=self._session_id,
            type_=EVENT_MCP,
            level=level,
            message=message,
            data=data,
        )
        self._sink.emit(event)

    # ------------------------------------------------------------------
    # Private tool implementations (pure logic, no side effects)
    # ------------------------------------------------------------------

    def _get_file_card(self, file_path: str) -> str:
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

    def _find_symbol(self, symbol_name: str) -> tuple[str, int]:
        """Return (result_markdown, match_count)."""
        canonical = symbol_name
        matches = self._symbols.get(symbol_name)
        if not matches:
            lower = symbol_name.lower()
            for name, items in self._symbols.items():
                if name.lower() == lower:
                    matches = items
                    canonical = name
                    break
        if not matches:
            return f"Symbol not found: `{symbol_name}`", 0

        lines: list[str] = [f"## Symbol: `{canonical}`", ""]
        lines.append(f"Found in {len(matches)} file(s):")
        lines.append("")
        for m in matches:
            kind = m.get("kind", "?")
            line_no = m.get("line", "?")
            fp = m.get("file_path", "?")
            lines.append(f"- **{fp}** — {kind} at line {line_no}")
        return "\n".join(lines), len(matches)

    def _list_high_risk(self) -> tuple[str, int]:
        """Return (result_markdown, risk_count)."""
        results: list[dict] = []
        for item in self._risk_report.get("files", []):
            high_h = [h for h in item.get("heuristics", []) if h.get("severity") == "high"]
            if item.get("risk_level") == "high" or high_h:
                results.append(
                    {
                        "path": item["path"],
                        "risk_level": item.get("risk_level"),
                        "reasons": item.get("reasons", []),
                        "high_severity_heuristics": high_h,
                    }
                )
        if not results:
            return "No high-risk files found in the risk report.", 0

        lines: list[str] = [f"## High-Risk Files ({len(results)})", ""]
        for r in results:
            lines.append(f"### {r['path']}")
            if r.get("risk_level"):
                lines.append(f"**Risk level:** {r['risk_level']}")
            reasons = r.get("reasons", [])
            if reasons:
                lines.append(f"**Reasons:** {'; '.join(reasons)}")
            high_h = r.get("high_severity_heuristics", [])
            if high_h:
                lines.append("")
                lines.append("**Heuristics:**")
                for h in high_h:
                    lines.append(
                        f"  - [{h.get('severity', '?')}] {h.get('kind', '?')}:"
                        f" `{h.get('symbol', '?')}` — {h.get('detail', '')}"
                    )
            lines.append("")
        return "\n".join(lines), len(results)

    # ------------------------------------------------------------------
    # Public tool methods (emit events, delegate to private impls)
    # ------------------------------------------------------------------

    def get_file_card(self, file_path: str) -> str:
        """Return a human-readable card for *file_path*.

        Fields rendered: purpose, symbols, snippet, facts, heuristics.
        """
        self._emit("McpToolCalled: get_file_card", {"tool": "get_file_card", "path": file_path})
        try:
            result = self._get_file_card(file_path)
        except Exception as e:
            self._emit(
                "McpToolFailed: get_file_card",
                {"tool": "get_file_card", "path": file_path, "error": str(e), "error_type": type(e).__name__},
                error=True,
            )
            raise
        self._emit(
            "McpToolReturned: get_file_card",
            {
                "tool": "get_file_card",
                "path": file_path,
                "found": not result.startswith("No context card"),
                "result_chars": len(result),
            },
        )
        return result

    def find_symbol(self, symbol_name: str) -> str:
        """Return a markdown-formatted list of locations for *symbol_name*.

        Falls back to a case-insensitive match when the exact name is not found.
        Returns a plain-text error message when nothing matches.
        """
        self._emit("McpToolCalled: find_symbol", {"tool": "find_symbol", "symbol": symbol_name})
        try:
            result, match_count = self._find_symbol(symbol_name)
        except Exception as e:
            self._emit(
                "McpToolFailed: find_symbol",
                {"tool": "find_symbol", "symbol": symbol_name, "error": str(e), "error_type": type(e).__name__},
                error=True,
            )
            raise
        self._emit(
            "McpToolReturned: find_symbol",
            {"tool": "find_symbol", "symbol": symbol_name, "match_count": match_count, "result_chars": len(result)},
        )
        return result

    def list_high_risk(self) -> str:
        """Return high-risk files from the risk report as markdown.

        A file is considered high-risk when its ``risk_level`` is ``"high"``
        or when it contains at least one heuristic with ``severity == "high"``.
        Both conditions are checked so that files classified high at the
        project level (but without specific heuristics) are still surfaced.
        """
        self._emit("McpToolCalled: list_high_risk", {"tool": "list_high_risk"})
        try:
            result, risk_count = self._list_high_risk()
        except Exception as e:
            self._emit(
                "McpToolFailed: list_high_risk",
                {"tool": "list_high_risk", "error": str(e), "error_type": type(e).__name__},
                error=True,
            )
            raise
        self._emit(
            "McpToolReturned: list_high_risk",
            {"tool": "list_high_risk", "risk_count": risk_count, "result_chars": len(result)},
        )
        return result


def build_mcp_server(  # type: ignore[return]
    inventory_path: Path,
    risk_report_path: Path,
    *,
    log_path: Path | None = None,
    session_id: str | None = None,
):
    """Build and return a :class:`~mcp.server.fastmcp.FastMCP` instance with vibecode tools.

    Parameters
    ----------
    log_path:
        When provided, tool events are appended as JSONL to this file.
        Typical value: ``<repo_root>/.vibecode/logs/mcp_events.jsonl``.
    session_id:
        Session identifier forwarded to :class:`VibecodeServer`.  ``None``
        falls through to the ``VIBECODE_SESSION_ID`` environment variable.
    """
    from mcp.server.fastmcp import FastMCP

    event_sink: Any = None
    if log_path is not None:
        from vibecode.events import JsonlEventSink

        event_sink = JsonlEventSink(log_path)

    vs = VibecodeServer(inventory_path, risk_report_path, event_sink=event_sink, session_id=session_id)
    mcp = FastMCP("vibecode")

    @mcp.tool()
    def get_file_card(file_path: str) -> str:
        """Return a markdown card for a file: purpose, symbols, snippet, facts, and heuristics."""
        return vs.get_file_card(file_path)

    @mcp.tool()
    def find_symbol(symbol_name: str) -> str:
        """Return a markdown list of locations for a symbol name (case-insensitive fallback)."""
        return vs.find_symbol(symbol_name)

    @mcp.tool()
    def list_high_risk() -> str:
        """Return a markdown report of high-risk files and high-severity heuristics."""
        return vs.list_high_risk()

    return mcp


def cmd_serve(args) -> int:
    """Start the vibecode MCP server with stdio transport.

    Prints a ready-to-paste OpenCode MCP configuration snippet to *stderr*
    before entering the blocking server loop.

    Tool events are written to ``<repo_root>/.vibecode/logs/mcp_events.jsonl``
    by default.  When the ``VIBECODE_MCP_EVENTS_LOG`` environment variable is
    set, events are written to that path instead — this allows ``RunController``
    to route MCP events into the per-run artifact directory by injecting the
    variable into the agent child process environment.

    Set ``VIBECODE_SESSION_ID`` to correlate events with an enclosing run
    session.  ``RunController`` injects this variable automatically.
    """
    from vibecode.data_loader import load_project_data
    from vibecode.paths import normalise_root

    raw = getattr(args, "repo_root", ".")
    repo_root = raw if isinstance(raw, Path) else normalise_root(raw)
    index_dir = repo_root / ".vibecode" / "index"
    inventory_path = index_dir / "file_inventory.json"
    risk_report_path = index_dir / "risk_report.json"

    project = load_project_data(repo_root)
    if project.inventory_missing or project.risk_report_missing:
        print(
            "Hint: index files are missing. Run 'vibecode inventory' to generate them.",
            file=sys.stderr,
        )

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

    log_path_env = os.environ.get("VIBECODE_MCP_EVENTS_LOG")
    if log_path_env:
        log_path = Path(log_path_env)
    else:
        log_path = repo_root / ".vibecode" / "logs" / "mcp_events.jsonl"
    session_id = os.environ.get("VIBECODE_SESSION_ID")
    mcp = build_mcp_server(inventory_path, risk_report_path, log_path=log_path, session_id=session_id)
    mcp.run(transport="stdio")
    return 0
