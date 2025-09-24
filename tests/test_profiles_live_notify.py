from optipanel.adapters.ibkr import MockFeaturesProvider
from optipanel.runtime.profiles_live import run_profiles_with_provider


def test_profiles_live_includes_notify_with_events(example_profiles, example_features):
    provider = MockFeaturesProvider(example_features)

    out = run_profiles_with_provider(example_profiles, provider, ticks=3)
    prime = out["lists"]["prime"]
    sec = out["lists"]["secondary"]

    assert "notify" in prime and "events" in prime["notify"] and "counts" in prime["notify"]
    assert isinstance(prime["notify"]["events"], list)
    assert isinstance(prime["notify"]["counts"], dict)
    # Since prime scans twice, at least some repeated alert should show count >= 2
    assert any(e.get("count", 0) >= 2 for e in prime["notify"]["events"])

    assert "notify" in sec and "events" in sec["notify"] and "counts" in sec["notify"]
    assert len(sec["notify"]["events"]) >= 1
