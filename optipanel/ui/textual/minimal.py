"""Minimal Textual TUI that renders the Command Room via the shared service."""

from __future__ import annotations

import argparse
import asyncio
from contextlib import suppress
from pathlib import Path

from optipanel.ui.service import run_tick
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import Footer, Header, Static


class CommandRoomPane(Static):
    """Simple wrapper to update the rendered Command Room text."""

    def display(self, text: str) -> None:
        self.update(text)


class SengokuMinimalTui(App):
    """Lean Textual cockpit that polls `run_tick` on an interval."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #body {
        height: 1fr;
        padding: 0 1;
    }
    """

    BINDINGS = [
        ("space", "toggle_pause", "Pause/Resume"),
        ("r", "refresh_now", "Refresh"),
        ("q", "quit", "Quit"),
    ]

    refresh_interval = reactive(5.0)

    def __init__(
        self,
        profiles_yaml: Path,
        provider: str,
        *,
        features_yaml: Path | None = None,
        refresh: float = 5.0,
        width: int = 24,
        top_n: int = 1,
    ) -> None:
        super().__init__()
        self._profiles_yaml = Path(profiles_yaml)
        self._provider = provider
        self._features_yaml = Path(features_yaml) if features_yaml else None
        self.refresh_interval = max(1.0, float(refresh))
        self._width = int(width)
        self._top_n = int(top_n)

        self._paused = False
        self._timer: Timer | None = None
        self._inflight: asyncio.Task[str] | None = None

    def compose(self) -> ComposeResult:  # pragma: no cover - UI composition
        yield Header(show_clock=True)
        with Vertical(id="body"), Horizontal():
            yield CommandRoomPane(id="command-pane")
        yield Footer()

    async def on_mount(self) -> None:  # pragma: no cover - UI runtime
        self._schedule_refresh(force=True)
        self._timer = self.set_interval(self.refresh_interval, self._schedule_refresh)

    async def on_unmount(self) -> None:  # pragma: no cover
        if self._timer is not None:
            self._timer.stop()
        if self._inflight is not None:
            self._inflight.cancel()
            with suppress(asyncio.CancelledError):
                await self._inflight

    def _schedule_refresh(self, force: bool = False) -> None:
        if self._paused and not force:
            return
        if self._inflight is not None and not self._inflight.done():
            return
        self._inflight = asyncio.create_task(self._refresh_once())

    async def _refresh_once(self) -> str:
        pane = self.query_one(CommandRoomPane)
        try:
            result = await asyncio.to_thread(
                run_tick,
                self._profiles_yaml,
                self._provider,
                features_yaml_path=self._features_yaml,
                width=self._width,
                top_n=self._top_n,
            )
            panel_text = str(result.get("panel", ""))
        except Exception as exc:  # pragma: no cover - defensive
            panel_text = f"[ERROR] {exc!r}"
        pane.display(panel_text)
        return panel_text

    def action_toggle_pause(self) -> None:  # pragma: no cover - bound action
        self._paused = not self._paused
        if not self._paused:
            self._schedule_refresh(force=True)

    def action_refresh_now(self) -> None:  # pragma: no cover - bound action
        self._paused = False
        self._schedule_refresh(force=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m optipanel.ui.textual.minimal")
    parser.add_argument("--profiles-yaml", required=True, type=Path)
    parser.add_argument("--provider", default="mock")
    parser.add_argument("--features-yaml", type=Path)
    parser.add_argument("--refresh", type=float, default=5.0)
    parser.add_argument("--width", type=int, default=24)
    parser.add_argument("--top-n", type=int, default=1)
    args = parser.parse_args(argv)

    app = SengokuMinimalTui(
        profiles_yaml=args.profiles_yaml,
        provider=args.provider,
        features_yaml=args.features_yaml,
        refresh=args.refresh,
        width=args.width,
        top_n=args.top_n,
    )
    app.run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
