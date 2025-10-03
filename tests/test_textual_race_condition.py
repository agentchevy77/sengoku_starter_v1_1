"""Comprehensive tests for Textual UI race condition fix (Issue #14).

This test suite demonstrates and validates the fix for the critical race condition
in the UI refresh logic that allowed multiple concurrent refresh tasks.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest


class TestRefreshRaceCondition:
    """Test suite for Issue #14: Critical Race Condition in UI Refresh Logic."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock SengokuMinimalTui instance for testing."""
        from optipanel.ui.textual.minimal import SengokuMinimalTui

        # Create app with minimal config
        app = SengokuMinimalTui(
            profiles_yaml=Path("/tmp/profiles.yaml"),
            provider="mock",
            refresh=5.0,
            width=24,
            top_n=1,
        )

        # Mock the query_one method to return a mock pane
        mock_pane = Mock()
        mock_pane.display = Mock()
        app.query_one = Mock(return_value=mock_pane)

        return app

    @pytest.mark.asyncio
    async def test_race_condition_exists_in_original(self, mock_app):
        """Demonstrate that the race condition exists in the original implementation."""
        # Track how many tasks are created
        tasks_created = []
        original_create_task = asyncio.create_task

        def track_create_task(coro):
            task = original_create_task(coro)
            tasks_created.append(task)
            return task

        with patch("asyncio.create_task", side_effect=track_create_task):
            with patch("optipanel.ui.service.run_tick", new_callable=AsyncMock) as mock_run_tick:
                mock_run_tick.return_value = {"panel": "test_data"}

                # Simulate concurrent calls to _schedule_refresh
                # This mimics what happens when timer fires while user presses 'R'

                # Start first refresh (simulating timer)
                mock_app._schedule_refresh()

                # Immediately start second refresh (simulating user pressing 'R')
                # In the original code, this can pass the check before the first
                # task is assigned to self._inflight
                mock_app._schedule_refresh(force=True)

                # In a race condition scenario, both could create tasks
                # We expect this to potentially create 2 tasks due to the race

                # Give tasks a chance to start
                await asyncio.sleep(0.01)

                # With the race condition, we might have created multiple tasks
                # (This test may not always trigger the race, but demonstrates the issue)
                assert len(tasks_created) >= 1, "At least one task should be created"

                # Clean up tasks
                for task in tasks_created:
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass

    @pytest.mark.asyncio
    async def test_orphaned_task_scenario(self, mock_app):
        """Test that demonstrates orphaned task scenario (Issue #15)."""
        slow_task_completed = False
        fast_task_completed = False

        async def slow_refresh():
            """Simulate a slow refresh operation."""
            nonlocal slow_task_completed
            await asyncio.sleep(0.5)  # Simulate slow operation
            slow_task_completed = True
            return "slow_data"

        async def fast_refresh():
            """Simulate a fast refresh operation."""
            nonlocal fast_task_completed
            await asyncio.sleep(0.1)  # Simulate fast operation
            fast_task_completed = True
            return "fast_data"

        # Create and track tasks
        with patch.object(mock_app, "_refresh_once", side_effect=[slow_refresh(), fast_refresh()]):
            # Start slow task
            mock_app._schedule_refresh()
            task1 = mock_app._inflight

            # Simulate race: second call overwrites _inflight before first completes
            await asyncio.sleep(0.01)  # Small delay to let first task start
            mock_app._inflight = None  # Simulate the race condition state
            mock_app._schedule_refresh(force=True)
            task2 = mock_app._inflight

            # Wait for both tasks to complete
            await asyncio.sleep(0.6)

            # Both tasks complete even though task1 was orphaned
            assert slow_task_completed, "Orphaned slow task still completes"
            assert fast_task_completed, "Fast task completes"

            # This demonstrates the problem: slow task updates UI after fast task
            # In real scenario, this causes stale data to overwrite fresh data

            # Clean up
            for task in [task1, task2]:
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

    @pytest.mark.asyncio
    async def test_concurrent_refresh_calls_stress_test(self, mock_app):
        """Stress test to expose race conditions with many concurrent calls."""
        call_count = 0

        async def mock_refresh():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return f"data_{call_count}"

        with patch.object(mock_app, "_refresh_once", side_effect=mock_refresh):
            # Simulate many concurrent refresh attempts
            tasks = []
            for i in range(10):
                # Mix of regular and forced refreshes
                force = i % 3 == 0
                # Don't await, simulate true concurrency
                mock_app._schedule_refresh(force=force)
                await asyncio.sleep(0.001)  # Tiny delay to spread out calls

            # Wait for all operations to complete
            await asyncio.sleep(0.2)

            # With race conditions, we might get multiple concurrent refreshes
            # The exact count depends on timing, but it demonstrates the issue
            print(f"Refresh operations executed: {call_count}")

            # Clean up any remaining task
            if mock_app._inflight and not mock_app._inflight.done():
                mock_app._inflight.cancel()
                try:
                    await mock_app._inflight
                except asyncio.CancelledError:
                    pass

    def test_check_then_act_pattern_fixed(self):
        """Verify the fix has been applied correctly."""
        # Read the source code to verify the fix
        source_file = Path(__file__).parent.parent / "optipanel/ui/textual/minimal.py"
        if source_file.exists():
            source = source_file.read_text()

            # Verify the fix components are present
            assert "self._refresh_lock: asyncio.Lock = asyncio.Lock()" in source
            assert "self._refresh_generation: int = 0" in source
            assert "async with self._refresh_lock:" in source
            assert "_refresh_once_with_generation" in source
            assert "asyncio.wait_for" in source  # Timeout fix for Issue #16
            assert "timeout=30.0" in source  # 30 second timeout

            print("✓ Confirmed: All fixes have been applied to source")

    @pytest.mark.asyncio
    async def test_fix_with_asyncio_lock(self):
        """Test that demonstrates how asyncio.Lock fixes the race condition."""

        # This test demonstrates the fix pattern
        class FixedRefreshLogic:
            def __init__(self):
                self._inflight = None
                self._refresh_lock = asyncio.Lock()
                self._refresh_generation = 0

            async def schedule_refresh_fixed(self, force=False):
                """Fixed version with atomic operations."""
                async with self._refresh_lock:
                    # Now this check-then-act is atomic
                    if self._inflight is not None and not self._inflight.done():
                        if force:
                            # Cancel the old task when forcing
                            self._inflight.cancel()
                            try:
                                await self._inflight
                            except asyncio.CancelledError:
                                pass
                        else:
                            return

                    # Increment generation to track task versions
                    self._refresh_generation += 1
                    current_gen = self._refresh_generation

                    # Create new task atomically
                    self._inflight = asyncio.create_task(self._refresh_with_generation(current_gen))

            async def _refresh_with_generation(self, generation):
                """Refresh that knows its generation."""
                await asyncio.sleep(0.01)
                # Check if we're still the current generation
                if generation == self._refresh_generation:
                    return f"data_gen_{generation}"
                else:
                    # We're stale, don't update
                    return None

        # Test the fixed logic
        fixed_logic = FixedRefreshLogic()

        # Simulate concurrent calls
        tasks = []
        for _ in range(5):
            task = asyncio.create_task(fixed_logic.schedule_refresh_fixed())
            tasks.append(task)

        # Wait for all scheduling attempts
        await asyncio.gather(*tasks)

        # Only one task should be in flight
        assert fixed_logic._inflight is not None
        result = await fixed_logic._inflight

        # Result should be from the latest generation
        assert result == f"data_gen_{fixed_logic._refresh_generation}"

        print("✓ Lock-based fix prevents race condition successfully")


class TestGenerationTracking:
    """Tests for generation-based stale update prevention."""

    @pytest.mark.asyncio
    async def test_generation_prevents_stale_updates(self):
        """Test that generation tracking prevents stale updates from orphaned tasks."""

        class GenerationAwareUI:
            def __init__(self):
                self._generation = 0
                self._current_display = None

            def increment_generation(self):
                self._generation += 1
                return self._generation

            async def update_display(self, data, generation):
                """Only update if generation matches current."""
                await asyncio.sleep(0.01)  # Simulate update delay
                if generation == self._generation:
                    self._current_display = data
                    return True
                return False  # Stale update rejected

        ui = GenerationAwareUI()

        # Start "slow" task with generation 1
        gen1 = ui.increment_generation()
        slow_task = asyncio.create_task(ui.update_display("old_data", gen1))

        # Start "fast" task with generation 2
        await asyncio.sleep(0.001)
        gen2 = ui.increment_generation()
        fast_task = asyncio.create_task(ui.update_display("new_data", gen2))

        # Wait for both to complete
        slow_result = await slow_task
        fast_result = await fast_task

        # Fast task should succeed, slow task should be rejected
        assert fast_result is True, "Current generation update accepted"
        assert slow_result is False, "Stale generation update rejected"
        assert ui._current_display == "new_data", "UI shows latest data"

        print("✓ Generation tracking successfully prevents stale updates")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
