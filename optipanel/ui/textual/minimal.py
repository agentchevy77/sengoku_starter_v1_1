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

        # Fix for Issue #14: Add lock to make refresh scheduling atomic
        self._refresh_lock: asyncio.Lock = asyncio.Lock()
        # Fix for Issue #15: Track task generation to prevent stale updates
        self._refresh_generation: int = 0

    def compose(self) -> ComposeResult:  # pragma: no cover - UI composition
        yield Header(show_clock=True)
        with Vertical(id="body"), Horizontal():
            yield CommandRoomPane(id="command-pane")
        yield Footer()

    async def on_mount(self) -> None:  # pragma: no cover - UI runtime
        self._schedule_refresh(force=True)
        self._timer = self.set_interval(self.refresh_interval, self._schedule_refresh)

    async def on_unmount(self) -> None:  # pragma: no cover
        """Clean shutdown handler with improved error handling.

        This fixes Issue #17 by suppressing all exceptions during shutdown,
        not just CancelledError, ensuring clean application termination.
        """
        if self._timer is not None:
            self._timer.stop()
        if self._inflight is not None:
            self._inflight.cancel()
            # Fix for Issue #17: Suppress all exceptions during shutdown
            with suppress(Exception):
                await self._inflight

    def _schedule_refresh(self, force: bool = False) -> None:
        """Schedule a refresh operation with atomic task management.

        This method fixes Issue #14 (race condition) and Issue #15 (orphaned tasks)
        by using an asyncio.Lock to ensure atomic check-then-act operations.

        Args:
            force: If True, cancels any in-flight refresh and starts a new one
        """
        if self._paused and not force:
            return

        # Use asyncio.create_task to schedule the async operation
        asyncio.create_task(self._schedule_refresh_async(force))

    async def _schedule_refresh_async(self, force: bool = False) -> None:
        """Async helper that implements atomic refresh scheduling.

        This method uses a lock to ensure that check-then-act operations
        are atomic, preventing race conditions.
        """
        async with self._refresh_lock:
            # ATOMIC SECTION START - Protected by lock
            if self._inflight is not None and not self._inflight.done():
                if force:
                    # Cancel the existing task when forcing a refresh
                    self._inflight.cancel()
                    # Wait for cancellation to complete
                    with suppress(asyncio.CancelledError):
                        await self._inflight
                else:
                    # Regular refresh blocked by in-flight task
                    return

            # Increment generation counter for this new refresh
            self._refresh_generation += 1
            current_generation = self._refresh_generation

            # Create new task (atomically, within the lock)
            self._inflight = asyncio.create_task(self._refresh_once_with_generation(current_generation))
            # ATOMIC SECTION END

    async def _refresh_once_with_generation(self, generation: int) -> str:
        """Perform a refresh operation with generation checking.

        This method fixes Issue #15 (stale updates) by checking the generation
        before updating the UI. If this task's generation is stale (because a
        newer refresh was started), it will skip the UI update.

        Args:
            generation: The generation number when this refresh was scheduled

        Returns:
            The panel text, or empty string if generation is stale
        """
        pane = self.query_one(CommandRoomPane)
        try:
            # Fix for Issue #16: Add timeout to prevent permanent freeze
            # Wrap the blocking call in asyncio.wait_for with 30 second timeout
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    run_tick,
                    self._profiles_yaml,
                    self._provider,
                    features_yaml_path=self._features_yaml,
                    width=self._width,
                    top_n=self._top_n,
                ),
                timeout=30.0,  # 30 second timeout prevents permanent freeze
            )
            panel_text = str(result.get("panel", ""))
        except TimeoutError:
            # Backend operation timed out
            panel_text = "[ERROR] Refresh timed out after 30 seconds"
        except Exception as exc:  # pragma: no cover - defensive
            panel_text = f"[ERROR] {exc!r}"

        # Only update display if we're still the current generation
        # This prevents stale updates from orphaned tasks
        if generation == self._refresh_generation:
            pane.display(panel_text)
            return panel_text
        else:
            # We're a stale generation, don't update UI
            return ""

    async def _refresh_once(self) -> str:
        """Legacy refresh method for backward compatibility.

        This method is kept for compatibility but now delegates to
        the generation-aware version.
        """
        return await self._refresh_once_with_generation(self._refresh_generation)

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
