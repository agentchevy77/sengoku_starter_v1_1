from optipanel.adapters.ibkr import MockFeaturesProvider
from optipanel.config.loader import parse_profiles_yaml
from optipanel.runtime.profiles_live import run_profiles_with_provider


def test_profiles_live_mock_calls_provider_on_scan_ticks(example_profiles, example_features):
    provider = MockFeaturesProvider(example_features)
    out = run_profiles_with_provider(example_profiles, provider, ticks=3)
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


def test_profiles_live_overlapping_lists_share_provider_calls(example_features):
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
    provider = CountingProvider(example_features)
    run_profiles_with_provider(prof, provider, ticks=2)

    # Both lists scan each tick, but provider should be called once per tick
    assert len(provider.calls) == 2
    assert all(set(c) == {"AAA", "BBB"} for c in provider.calls)
    assert all(len(set(c)) == len(c) for c in provider.calls)
