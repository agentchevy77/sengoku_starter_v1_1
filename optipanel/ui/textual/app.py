"""Interactive Textual cockpit for the Sengoku Decision panel."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from optipanel.ui.service import (
    DEFAULT_FEATURES_PATH,
    DEFAULT_PROFILES_PATH,
    PanelSnapshot,
    Profiles,
    ProviderConfig,
    budget_status,
    combine_watchlists,
    compute_panel,
    fetch_features,
    load_profiles,
)

try:  # Optional dependency
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal
    from textual.message import Message
    from textual.reactive import reactive
    from textual.timer import Timer
    from textual.widgets import Button, DataTable, Footer, Header, Input, Select, Static
except Exception as exc:  # pragma: no cover - only hit when textual is absent
    raise RuntimeError("Textual extras are required: pip install optipanel[ui]") from exc


@dataclass
class UIConfig:
    profiles_path: Path = DEFAULT_PROFILES_PATH
    features_path: Path = DEFAULT_FEATURES_PATH
    provider: str = "mock"
    tick_interval: float = 5.0
    top_n: int | None = None
    include_supply: bool = True


class RefreshNow(Message):
    """Message dispatched when the user requests an immediate refresh."""


class SengokuTui(App):
    """Textual implementation of the Sengoku Decision cockpit."""

    CSS = """
    Screen {
        layout: vertical;
    }
    #controls {
        height: 3;
        min-height: 3;
        padding: 0 1;
        background: $surface;
    }
    #controls > * {
        margin: 0 1;
    }
    #content {
        layout: horizontal;
        height: 1fr;
    }
    #watchlist {
        width: 1fr;
    }
    #detail {
        width: 1fr;
        padding: 1 1;
    }
    DataTable {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("r", "request_refresh", "Refresh now"),
        ("q", "quit", "Quit"),
    ]

    refresh_interval = reactive(5.0)

    def __init__(self, config: UIConfig | None = None) -> None:
        super().__init__()
        self.config = config or UIConfig()
        self._profiles: Profiles | None = None
        self._panels: dict[str, PanelSnapshot] = {}
        self._refresh_lock = asyncio.Lock()
        self._timer: Timer | None = None

    def compose(self) -> ComposeResult:  # pragma: no cover - UI composition
        yield Header(show_clock=True)
        with Horizontal(id="controls"):
            yield Select(
                options=[("Mock fixtures", "mock"), ("IBKR TWS (live)", "tws-live")],
                value=self.config.provider,
                id="provider",
            )
            yield Input(value=str(self.config.tick_interval), placeholder="Tick seconds", id="interval")
            top_n_value = "" if self.config.top_n is None else str(self.config.top_n)
            yield Input(value=top_n_value, placeholder="Top N", id="top_n")
            yield Input(value=str(self.config.features_path), placeholder="Features YAML (mock)", id="features_path")
            yield Button("Refresh", id="refresh")
            yield Static("Budget: --", id="budget")
        with Horizontal(id="content"):
            self.table = DataTable(id="watchlist")
            yield self.table
            self.detail = Static(id="detail")
            yield self.detail
        yield Footer()

    async def on_mount(self) -> None:  # pragma: no cover - UI runtime
        try:
            self._profiles = load_profiles(self.config.profiles_path)
        except Exception as exc:  # surfacing file issues nicely
            self.detail.update(Panel(Text(f"Failed to load profiles: {exc}"), title="Error", style="red"))
            return

        self.refresh_interval = float(self.config.tick_interval)
        self.table.add_columns("Symbol", "List", "Advice", "Recon", "Attack", "Defense", "Sustain", "Supply")
        self.table.cursor_type = "row"
        self.table.zebra_stripes = True

        await self.refresh_data(force=True)
        self._timer = self.set_interval(self.refresh_interval, self._auto_refresh, pause=False)

    async def action_request_refresh(self) -> None:  # pragma: no cover - binder
        await self.post_message(RefreshNow())

    async def on_refresh_now(self, _: RefreshNow) -> None:  # pragma: no cover
        await self.refresh_data(force=True)

    async def _auto_refresh(self) -> None:  # pragma: no cover
        await self.refresh_data()

    async def refresh_data(self, *, force: bool = False) -> None:
        if self._profiles is None:
            return

        if self._refresh_lock.locked() and not force:
            return

        async with self._refresh_lock:
            provider_cfg = ProviderConfig(
                name=self._provider_name,
                features_path=str(self.config.features_path),
            )
            try:
                features = await asyncio.to_thread(
                    fetch_features,
                    self._requested_symbols,
                    provider=provider_cfg,
                )
            except Exception as exc:
                self.detail.update(Panel(Text(f"Fetch failed: {exc}"), title="Provider error", style="red"))
                return

            panels: list[PanelSnapshot] = []
            for sym in self._requested_symbols:
                feats = features.get(sym)
                if not feats:
                    continue
                try:
                    panel = compute_panel(
                        sym,
                        feats,
                        include_supply=self.config.include_supply,
                        battlefield_width=self._profiles.ui_width,
                    )
                except Exception as exc:
                    self.detail.update(
                        Panel(Text(f"Panel build failed for {sym}: {exc}"), title="Panel error", style="red")
                    )
                    continue
                panels.append(panel)

            panels.sort(key=lambda p: p.recon_score, reverse=True)
            self._panels = {panel.symbol: panel for panel in panels}
            self._update_watchlist(panels)
            if panels:
                self._update_detail(panels[0].symbol)
            self._update_budget_indicator()

    @property
    def _provider_name(self) -> str:
        return self.query_one("Select#provider", Select).value or "mock"

    @property
    def _requested_symbols(self) -> list[str]:
        if self._profiles is None:
            return []
        ordered = combine_watchlists(self._profiles)
        top_n = self.config.top_n or self._profiles.top_n
        return ordered[: max(1, top_n)]

    def _update_watchlist(self, panels: Iterable[PanelSnapshot]) -> None:
        self.table.clear()
        prime_set: set[str] = set(self._profiles.prime if self._profiles else [])
        for panel in panels:
            list_name = "prime" if panel.symbol in prime_set else "secondary"
            sustain = panel.sustainment.get("sustainability", 0)
            readiness = panel.readiness or {}
            supply_flag = "yes" if panel.supply else "-"
            self.table.add_row(
                panel.symbol,
                list_name,
                panel.advice,
                str(panel.recon_score),
                str(readiness.get("attack", "-")),
                str(readiness.get("defense", "-")),
                str(sustain),
                supply_flag,
                key=panel.symbol,
            )

    def _update_detail(self, symbol: str) -> None:
        panel = self._panels.get(symbol)
        if not panel:
            return

        recon_table = Table.grid(expand=True)
        recon_table.add_row("Recon", str(panel.recon_score), "Advice", panel.advice)
        sustain = panel.sustainment
        recon_table.add_row(
            "Sustain", str(sustain.get("sustainability", "-")), "Fakeout", str(sustain.get("fakeout_risk", "-"))
        )
        readiness = panel.readiness
        recon_table.add_row(
            "Ready (A/D)",
            f"{readiness.get('attack', '-')} / {readiness.get('defense', '-')}",
            "Mode",
            str(panel.recon.get("mode", "prob")),
        )

        supply_lines = panel.supply or {}
        supply_table = Table.grid(padding=(0, 1))
        for key, factors in supply_lines.items():
            if isinstance(factors, Iterable) and not isinstance(factors, str | bytes):
                joined = ", ".join(map(str, factors))
            else:
                joined = str(factors) if factors is not None else "-"
            supply_table.add_row(f"{key}", joined)

        group = Group(
            Panel(Text(panel.battlefield, justify="left"), title="Battlefield", border_style="cyan", expand=False),
            Panel(recon_table, title="Recon", border_style="magenta", expand=False),
            Panel(supply_table if supply_lines else Text("n/a"), title="Supply", border_style="yellow", expand=False),
        )
        self.detail.update(Panel(group, title=panel.symbol, border_style="green"))

    def _update_budget_indicator(self) -> None:
        if self._profiles is None:
            return
        prime_budget = self._profiles.budgets.get("prime")
        status = budget_status("prime", prime_budget)
        text = f"Budget: {status.emoji} {status.status} (used {status.used:.0f}/{status.soft_cap:.0f})"
        self.query_one("Static#budget", Static).update(Text(text))

    async def on_button_pressed(self, event: Button.Pressed) -> None:  # pragma: no cover
        if event.button.id == "refresh":
            await self.refresh_data(force=True)

    async def on_select_changed(self, event: Select.Changed) -> None:  # pragma: no cover
        if event.select.id == "provider":
            self.config.provider = event.value
            await self.refresh_data(force=True)

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:  # pragma: no cover
        symbol = event.row_key
        self._update_detail(str(symbol))

    async def on_input_submitted(self, event: Input.Submitted) -> None:  # pragma: no cover
        if event.input.id == "interval":
            self._update_interval(event.value)
        elif event.input.id == "top_n":
            self._update_top_n(event.value)
        elif event.input.id == "features_path":
            self.config.features_path = Path(event.value)
            await self.refresh_data(force=True)

    def _update_interval(self, value: str) -> None:
        try:
            seconds = max(1.0, float(value))
        except ValueError:
            return
        self.refresh_interval = seconds
        self.config.tick_interval = seconds
        if self._timer is not None:
            self._timer.reset(self.refresh_interval)

    def _update_top_n(self, value: str) -> None:
        try:
            top_n = max(1, int(value))
        except ValueError:
            return
        self.config.top_n = top_n
        asyncio.create_task(self.refresh_data(force=True))


def run(config: UIConfig | None = None) -> None:
    """Entry point for embedding in other processes."""

    SengokuTui(config).run()


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m optipanel.ui.textual.app")
    ap.add_argument("--profiles-yaml", default=str(DEFAULT_PROFILES_PATH))
    ap.add_argument("--features-yaml", default=str(DEFAULT_FEATURES_PATH))
    ap.add_argument("--provider", choices=["mock", "tws-live"], default="mock")
    ap.add_argument("--tick-interval", type=float, default=5.0)
    ap.add_argument("--top-n", type=int, default=None)
    ap.add_argument("--no-supply", action="store_true", help="Disable supply computation for the panel")
    args = ap.parse_args(argv)

    config = UIConfig(
        profiles_path=Path(args.profiles_yaml),
        features_path=Path(args.features_yaml),
        provider=args.provider,
        tick_interval=float(args.tick_interval),
        top_n=args.top_n,
        include_supply=not args.no_supply,
    )
    run(config)
    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution only
    raise SystemExit(main())
