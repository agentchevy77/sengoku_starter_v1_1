from __future__ import annotations
import pathlib, yaml, dataclasses
ROOT = pathlib.Path(__file__).resolve().parents[1]

@dataclasses.dataclass
class Settings:
    allowance_lines: int
    soft_cap_lines: int
    rt_bars_max: int
    snapshot_concurrency_max: int
    backoff_cooldown_sec: int
    prime_interval_sec: int
    secondary_thin_interval_sec: int
    cache_max_items: int
    cache_default_ttl_sec: int

def load_settings() -> Settings:
    ypath = ROOT / "config" / "settings.defaults.yaml"
    cfg = yaml.safe_load(ypath.read_text())
    b = cfg["market_data_budget"]; s = cfg["schedulers"]; c = cfg["cache"]
    return Settings(
        allowance_lines=b["allowance_lines"],
        soft_cap_lines=b["soft_cap_lines"],
        rt_bars_max=b["rt_bars_max"],
        snapshot_concurrency_max=b["snapshot_concurrency_max"],
        backoff_cooldown_sec=b["backoff"]["cooldown_sec"],
        prime_interval_sec=s["prime_interval_sec"],
        secondary_thin_interval_sec=s["secondary_thin_interval_sec"],
        cache_max_items=c["max_items"],
        cache_default_ttl_sec=c["default_ttl_sec"],
    )
