#!/usr/bin/env python3
"""Render command room panels from recorded feature bundles."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_ticks(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    ticks = data.get("ticks")
    if not isinstance(ticks, list):
        raise ValueError("Input JSON must contain a list under 'ticks'")
    out: list[dict[str, Any]] = []
    for idx, entry in enumerate(ticks):
        if not isinstance(entry, dict):
            raise ValueError(f"Tick {idx} is not a mapping of symbol features")
        # Convert keys to str for consistency
        out.append({str(sym): feats for sym, feats in entry.items() if isinstance(feats, dict)})
    return out


def render_panels(ticks: list[dict[str, Any]], *, width: int, top_n: int) -> list[str]:
    panels: list[str] = []
    from optipanel.runtime.loop import run_once
    from optipanel.ui.command_room import render_command_room

    for idx, features in enumerate(ticks):
        run_out = run_once(features)
        panel = render_command_room(run_out, width=width, top_n=top_n)
        panels.append(f"--- tick {idx} ---\n{panel}")
    return panels


def main() -> None:
    parser = argparse.ArgumentParser(description="Render command room panels from recorded bundles")
    parser.add_argument("--input", required=True, help="Path to JSON file with ticks list")
    parser.add_argument("--output", required=True, help="Path to write the rendered panels log")
    parser.add_argument("--width", type=int, default=22, help="Battlefield bar width (default: 22)")
    parser.add_argument("--top-n", type=int, default=2, help="Number of top symbols to display (default: 2)")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    ticks = load_ticks(input_path)
    panels = render_panels(ticks, width=int(args.width), top_n=int(args.top_n))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n\n".join(panels))


if __name__ == "__main__":
    main()
