import os

import pytest

from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcherConfig


@pytest.mark.skipif(os.getenv("IBKR_LIVE") != "1", reason="IBKR live disabled")
def test_real_tws_fetcher_import_only():
    # If you really want to run live, set IBKR_LIVE=1 and ensure ibapi/TWS is available.
    from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher  # noqa: F401

    cfg = RealTwsFetcherConfig()
    assert cfg.port in (7496, 7497)
