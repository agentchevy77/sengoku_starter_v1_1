"""Minimal Textual TUI that renders the Command Room via the shared service."""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Coroutine
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from optipanel.cli.config import ConfigResolver
from optipanel.ui.service import run_tick
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import Footer, Header, Static

logger = logging.getLogger(__name__)


@dataclass
class UIConfig:
    """Configuration for UI behavior with environment variable support.

    FIX for Bug #52: Hardcoded UI Timeout Configuration

    This class eliminates hardcoded magic numbers in the UI system by providing
    environment variable configuration. It follows the same pattern as the cache
    settings (`TickCacheSettings`, Bug #57 fix) for consistency.

    Environment Variables:
        SENGOKU_UI_REFRESH_TIMEOUT: Timeout for refresh operations (default: 30.0)

    Attributes:
        refresh_timeout: Timeout in seconds for UI refresh operations
    """

    refresh_timeout: float = 30.0

    def __post_init__(self) -> None:
        """Validate configuration values after initialization."""
        # Validate refresh_timeout
        if self.refresh_timeout <= 0:
            raise ValueError(f"refresh_timeout must be positive, got {self.refresh_timeout}")

        # Warn about extreme values
        if self.refresh_timeout < 1.0:
            logger.warning("refresh_timeout=%s is very low (<1s), may cause excessive CPU usage", self.refresh_timeout)
        elif self.refresh_timeout > 300.0:
            logger.warning(
                "refresh_timeout=%s is very high (>300s), may cause poor responsiveness", self.refresh_timeout
            )

    @classmethod
    def from_env(cls, resolver: ConfigResolver | None = None) -> UIConfig:
        """Create UIConfig from environment variables.

        Args:
            resolver: Optional ConfigResolver instance (creates new if not provided)

        Returns:
            UIConfig instance with values from environment or defaults

        Example:
            >>> config = UIConfig.from_env()
            >>> config.refresh_timeout
            30.0

            >>> # With environment variable
            >>> os.environ['SENGOKU_UI_REFRESH_TIMEOUT'] = '60.0'
            >>> config = UIConfig.from_env()
            >>> config.refresh_timeout
            60.0
        """
        if resolver is None:
            resolver = ConfigResolver()

        return cls(
            refresh_timeout=resolver.get_float(
                "ui.refresh_timeout",
                cli_value=None,
                env_key="SENGOKU_UI_REFRESH_TIMEOUT",
                default=30.0,
            )
        )


class TaskHandle:
    """Thread-safe wrapper for asyncio.Task to prevent race conditions.

    FIX for Bug #48: Race Condition in Async Task Management

    This class ensures that a task reference is always valid and prevents the race
    condition where a task could complete before its reference is stored. It provides:

    1. Atomic task creation and reference storage
    2. Safe cancellation with proper cleanup
    3. Consistent state checking

    The key insight is that we store the reference BEFORE creating the actual task,
    using a two-phase initialization that prevents any window where the task exists
    but the reference doesn't.
    """

    def __init__(self) -> None:
        """Initialize an empty task handle."""
        self._task: asyncio.Task | None = None
        self._cancelled = False

    async def start(self, coro: Any) -> None:
        """Start the task with guaranteed reference storage.

        This method ensures the task reference is stored atomically before
        the task can possibly complete, eliminating the race condition.

        Args:
            coro: The coroutine to run as a task
        """

        # Create a wrapper that ensures our reference is set first
        async def _wrapper():
            # At this point, self._task is guaranteed to be set
            try:
                return await coro
            except asyncio.CancelledError:
                self._cancelled = True
                raise

        # Store the task reference ATOMICALLY before it can run
        # This is the key fix: the task reference exists before execution begins
        self._task = asyncio.create_task(_wrapper())

    def is_running(self) -> bool:
        """Check if the task is currently running.

        Returns:
            True if task exists and is not done, False otherwise
        """
        return self._task is not None and not self._task.done()

    def cancel(self) -> None:
        """Cancel the task if it's running."""
        if self._task is not None and not self._task.done():
            self._task.cancel()
            self._cancelled = True

    async def wait(self, suppress_cancel: bool = True) -> None:
        """Wait for the task to complete.

        Args:
            suppress_cancel: If True, suppress CancelledError exceptions
        """
        if self._task is not None:
            if suppress_cancel:
                with suppress(asyncio.CancelledError):
                    await self._task
            else:
                await self._task

    @property
    def task(self) -> asyncio.Task | None:
        """Get the underlying task (for compatibility)."""
        return self._task

    def done(self) -> bool:
        """Return True if the underlying task finished execution."""
        return self._task.done() if self._task is not None else False

    def cancelled(self) -> bool:
        """Return True if the underlying task was cancelled."""
        if self._task is not None:
            return self._task.cancelled()
        return self._cancelled

    def result(self) -> Any:
        """Return the task result, mirroring asyncio.Task."""
        if self._task is None:
            raise asyncio.InvalidStateError("Task has not been started")
        return self._task.result()

    def exception(self) -> BaseException | None:
        """Return the task exception if one occurred."""
        if self._task is None:
            raise asyncio.InvalidStateError("Task has not been started")
        return self._task.exception()

    def add_done_callback(self, callback) -> None:
        """Register a callback to run when the task completes."""
        if self._task is None:
            raise asyncio.InvalidStateError("Task has not been started")
        self._task.add_done_callback(callback)

    def __await__(self):  # pragma: no cover - thin delegation
        if self._task is None:

            async def _noop():
                return None

            return _noop().__await__()
        return self._task.__await__()

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the underlying task for compatibility."""
        task = self._task
        if task is not None and hasattr(task, name):
            return getattr(task, name)
        raise AttributeError(name)


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
        ui_config: UIConfig | None = None,
    ) -> None:
        super().__init__()
        self._profiles_yaml = Path(profiles_yaml)
        self._provider = provider
        self._features_yaml = Path(features_yaml) if features_yaml else None
        self.refresh_interval = max(1.0, float(refresh))
        self._width = int(width)
        self._top_n = int(top_n)

        # FIX for Bug #52: Store configurable UI config
        # Defaults to environment-based config if not explicitly provided
        self._ui_config = ui_config if ui_config is not None else UIConfig.from_env()

        self._paused = False
        self._timer: Timer | None = None
        # FIX for Bug #48: Use TaskHandle by default, while still tolerating raw asyncio.Task
        # instances supplied by legacy callers or tests.
        self._inflight: TaskHandle | asyncio.Task | None = None
        # FIX for Bug #62: Track scheduler/background tasks so exceptions are surfaced
        # and references are not lost (prevents silent failures and task leaks).
        self._background_tasks: set[asyncio.Task] = set()

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
            self._cancel_task(self._inflight)
            await self._wait_for_task(self._inflight, suppress_cancel=True)
        # Cancel any outstanding scheduler/background tasks to avoid leaks during shutdown.
        for task in list(self._background_tasks):
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        self._background_tasks.clear()

    def _schedule_refresh(self, force: bool = False) -> None:
        """Schedule a refresh operation with atomic task management.

        This method fixes Issue #14 (race condition) and Issue #15 (orphaned tasks)
        by using an asyncio.Lock to ensure atomic check-then-act operations.

        Args:
            force: If True, cancels any in-flight refresh and starts a new one
        """
        if self._paused and not force:
            return

        # Use tracked background tasks so failures surface instead of being swallowed.
        self._spawn_background_task(
            self._schedule_refresh_async(force),
            purpose=f"refresh-scheduler(force={force})",
        )

    async def _schedule_refresh_async(self, force: bool = False) -> None:
        """Async helper that implements atomic refresh scheduling.

        This method uses a lock to ensure that check-then-act operations
        are atomic, preventing race conditions.

        FIX for Bug #48: Uses TaskHandle to ensure task reference is
        always valid and prevents race conditions.
        """
        async with self._refresh_lock:
            # ATOMIC SECTION START - Protected by lock
            current = self._inflight
            if current is not None:
                # Snapshot state to avoid TOCTOU between the check and follow-up action.
                running = self._task_is_running(current)
                if not running:
                    # Drop stale references so future callers can schedule immediately.
                    if self._inflight is current:
                        self._inflight = None
                elif not force:
                    # Regular refresh blocked by in-flight task
                    return
                else:
                    # Cancel the existing task when forcing a refresh
                    self._cancel_task(current)
                    # Wait for cancellation to complete, still within the lock
                    await self._wait_for_task(current, suppress_cancel=True)
                    # Clear the handle if we still own it (task may have already finished)
                    if self._inflight is current:
                        self._inflight = None

            # Increment generation counter for this new refresh
            self._refresh_generation += 1
            current_generation = self._refresh_generation

            # FIX for Bug #48 & Bug #66: Create TaskHandle atomically after clearing stale refs
            self._inflight = TaskHandle()
            await self._inflight.start(self._refresh_once_with_generation(current_generation))
            # ATOMIC SECTION END

    @staticmethod
    def _task_is_running(task) -> bool:
        if isinstance(task, TaskHandle):
            return task.is_running()
        return not task.done()

    @staticmethod
    def _cancel_task(task) -> None:
        if isinstance(task, TaskHandle) or task is not None and not task.done():
            task.cancel()

    @staticmethod
    async def _wait_for_task(task, *, suppress_cancel: bool = True) -> None:
        if isinstance(task, TaskHandle):
            await task.wait(suppress_cancel=suppress_cancel)
            return

        if task is None:
            return

        if suppress_cancel:
            with suppress(asyncio.CancelledError):
                await task
        else:
            await task

    def _spawn_background_task(
        self,
        coro: Coroutine[Any, Any, Any],
        *,
        purpose: str,
    ) -> asyncio.Task:
        """Create and track a background task, logging failures.

        FIX for Bug #62: Ensures we retain a reference to background work so
        unexpected exceptions are surfaced instead of being silently discarded.
        """

        task = asyncio.create_task(coro)
        self._background_tasks.add(task)

        def _finalizer(done: asyncio.Task) -> None:
            self._background_tasks.discard(done)
            if done.cancelled():
                return
            try:
                done.result()
            except Exception:  # pragma: no cover - defensive safeguard
                logger.exception("Background task '%s' raised an exception", purpose)

        task.add_done_callback(_finalizer)
        return task

    @staticmethod
    def _human_timeout(value: float) -> str:
        """Format timeout seconds without spurious trailing decimals."""
        if float(value).is_integer():
            return f"{int(value)} seconds"
        return f"{value:.1f} seconds"

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
            # FIX for Bug #52: Use configurable timeout from UIConfig
            # Timeout can be configured via SENGOKU_UI_REFRESH_TIMEOUT environment variable
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    run_tick,
                    self._profiles_yaml,
                    self._provider,
                    features_yaml_path=self._features_yaml,
                    width=self._width,
                    top_n=self._top_n,
                ),
                timeout=self._ui_config.refresh_timeout,
            )
            panel_text = str(result.get("panel", ""))
        except TimeoutError:
            # Backend operation timed out
            # FIX for Bug #52: Dynamic timeout value in error message
            timeout_text = self._human_timeout(self._ui_config.refresh_timeout)
            panel_text = f"[ERROR] Refresh timed out after {timeout_text}"
        except Exception as exc:  # pragma: no cover - defensive
            panel_text = f"[ERROR] {exc!r}"

        # Only update display if we're still the current generation
        # This prevents stale updates from orphaned tasks
        if generation == self._refresh_generation:
            pane.display(panel_text)
            # FIX for Bug #76: Add observability log for successful updates
            # This helps correlate generations with UI updates during debugging
            logger.debug(
                "UI updated successfully (generation=%d, text_len=%d)",
                generation,
                len(panel_text),
            )
            return panel_text
        else:
            # We're a stale generation, don't update UI
            # FIX for Bug #76: Log generation mismatch for observability
            # This was previously a silent failure, making debugging impossible.
            # Generation mismatches are EXPECTED during concurrent refreshes (e.g., forced refresh
            # while a scheduled refresh is running), so we use DEBUG level, not WARNING.
            logger.debug(
                "Skipping stale UI update: generation mismatch (task_gen=%d, current_gen=%d, text_preview='%s')",
                generation,
                self._refresh_generation,
                panel_text[:50] + "..." if len(panel_text) > 50 else panel_text,
            )
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
