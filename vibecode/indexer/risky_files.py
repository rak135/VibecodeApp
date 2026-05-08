"""Write .vibecode/index/risky_files.md."""

from __future__ import annotations

from pathlib import Path

from vibecode.indexer.risk_engine import RiskResult


def render_risky_files(risk_index: dict[str, RiskResult]) -> str:
    """Return the markdown content for *risky_files.md*."""
    results = list(risk_index.values())
    high = sorted(
        [r for r in results if r.risk_level == "high"], key=lambda r: r.path
    )
    medium = sorted(
        [r for r in results if r.risk_level == "medium"], key=lambda r: r.path
    )

    lines: list[str] = ["# Risky Files\n"]

    if not high and not medium:
        lines.append("No files with elevated risk detected.\n")
        return "\n".join(lines)

    if high:
        lines.append("## High Risk\n")
        for r in high:
            lines.append(f"- `{r.path}`")
            for reason in r.reasons:
                lines.append(f"  - {reason}")
        lines.append("")

    if medium:
        lines.append("## Medium Risk\n")
        for r in medium:
            lines.append(f"- `{r.path}`")
            for reason in r.reasons:
                lines.append(f"  - {reason}")
        lines.append("")

    return "\n".join(lines)


def write_risky_files(risk_index: dict[str, RiskResult], output_path: Path) -> None:
    """Write *risky_files.md* to *output_path*, creating parent dirs as needed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_risky_files(risk_index), encoding="utf-8")
