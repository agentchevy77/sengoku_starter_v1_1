from optipanel.adapters.ibkr import MockFeaturesProvider
from optipanel.config.loader import parse_features_yaml, parse_profiles_yaml
from optipanel.runtime.profiles_live import run_profiles_with_provider

PROF_YAML = """
watchlists:
  prime: [AAA]
  secondary: [BBB]
budgets:
  prime: {soft_cap: 10, cooldown: 1, used_lines: [20,5,5], scan_stride_backoff: 2}
  secondary: {soft_cap: 100, cooldown: 1, used_lines: 1}
ui: {width: 20, top_n: 1}
"""

FEAT_YAML = """
AAA: {last: 105.0, dma20: 100.0, support: 101.0, resistance: 106.0, rvol: 1.6, rs_strength: 0.3, vwap_diff: 0.012}
BBB: {last:  95.0, dma20: 100.0, support:  96.0, resistance: 100.0, rvol: 1.5, rs_strength: -0.25, vwap_diff: -0.012}
"""


def test_profiles_live_mock_calls_provider_on_scan_ticks():
    prof = parse_profiles_yaml(PROF_YAML)
    feats = parse_features_yaml(FEAT_YAML)
    provider = MockFeaturesProvider(feats)
    out = run_profiles_with_provider(prof, provider, ticks=3)
    assert "lists" in out and "prime" in out["lists"] and "secondary" in out["lists"]
    # prime: backoff first tick -> scan at tick 0 and 2 (stride=2), total 2 scans
    assert out["lists"]["prime"]["provider_calls"] == out["lists"]["prime"]["scanned_count"] == 2
    # secondary: always under cap -> scan each tick
    assert out["lists"]["secondary"]["provider_calls"] == out["lists"]["secondary"]["scanned_count"] == 3
    # panels render battlefield bars
    panel = "\n".join(out["lists"]["prime"]["panels"])
    assert "COMMAND ROOM" in panel and "dma20" in panel.lower()


class CountingProvider(MockFeaturesProvider):
    def __init__(self, data):
        super().__init__(data)
        self.calls = []

    def features_for_symbols(self, symbols):
        self.calls.append(tuple(symbols))
        return super().features_for_symbols(symbols)


def test_profiles_live_overlapping_lists_share_provider_calls():
    prof = parse_profiles_yaml(
        """
        watchlists:
          prime: [AAA, BBB]
          secondary: [BBB]
        budgets:
          prime: {soft_cap: 10, cooldown: 0, used_lines: 1}
          secondary: {soft_cap: 10, cooldown: 0, used_lines: 1}
        ui: {width: 20, top_n: 1}
        """
    )
    feats = parse_features_yaml(FEAT_YAML)
    provider = CountingProvider(feats)
    run_profiles_with_provider(prof, provider, ticks=2)

    # Both lists scan each tick, but provider should be called once per tick
    assert len(provider.calls) == 2
    assert all(set(c) == {"AAA", "BBB"} for c in provider.calls)
    assert all(len(set(c)) == len(c) for c in provider.calls)
