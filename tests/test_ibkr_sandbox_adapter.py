import pytest

from optipanel.adapters.ibkr.sandbox import SandboxAdapter


@pytest.mark.asyncio
async def test_sandbox_adapter_seed_stability():
    adapter_a = SandboxAdapter(seed=123)
    adapter_b = SandboxAdapter(seed=123)

    snap_a = await adapter_a.get_underlying_snapshot("AAPL")
    snap_b = await adapter_b.get_underlying_snapshot("AAPL")

    assert snap_a["symbol"] == "AAPL"
    assert snap_b["symbol"] == "AAPL"
    assert snap_a["last"] == snap_b["last"]
    assert isinstance(snap_a["as_of"], float)


@pytest.mark.asyncio
async def test_sandbox_option_chain_slice_is_consistent():
    primary = SandboxAdapter(seed=77)
    control = SandboxAdapter(seed=77)

    chain_a = await primary.get_option_chain_slice("MSFT")
    chain_b = await control.get_option_chain_slice("MSFT")

    assert chain_a["symbol"] == "MSFT"
    assert chain_b["symbol"] == "MSFT"
    assert chain_a["atm"]["call"] == chain_a["atm"]["put"]
    assert chain_a["atm"] == chain_b["atm"]
