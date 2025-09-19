def compute_units(features: dict) -> dict[str, dict[str, int]]:
    """
    Compute battlefield units with bull vs bear intensity 0..100.

    features keys: last, dma20, support, resistance, rvol, rs_strength
    returns: {"dma20":{"bull":int,"bear":int}, ...} (each 0..100)
    """
    last = features["last"]
    dma20 = features["dma20"]
    support = features["support"]
    resistance = features["resistance"]
    rvol = features["rvol"]
    rs_strength = features["rs_strength"]

    units = {}

    # DMA20: bull if last >= dma20
    if last >= dma20:
        units["dma20"] = {"bull": 70, "bear": 30}
    else:
        units["dma20"] = {"bull": 30, "bear": 70}

    # Support: broken if last < support, defending if within 1%
    if last < support:
        units["support"] = {"bull": 25, "bear": 75}
    # near support if price is above support and within ~1%
    elif last >= support and ((last - support) / last if last else 0.0) <= 0.01:
        units["support"] = {"bull": 75, "bear": 25}
    else:
        units["support"] = {"bull": 50, "bear": 50}

    # Resistance: bear if within 1% above last
    if (resistance - last) / last <= 0.01:
        units["resistance"] = {"bull": 25, "bear": 75}
    else:
        units["resistance"] = {"bull": 60, "bear": 40}

    # RVOL: bull if >= 1.2, bear if <= 0.8
    if rvol >= 1.2:
        units["rvol"] = {"bull": 60, "bear": 40}
    elif rvol <= 0.8:
        units["rvol"] = {"bull": 40, "bear": 60}
    else:
        units["rvol"] = {"bull": 50, "bear": 50}

    # RS: bull if >= 0.1, bear if <= -0.1
    if rs_strength >= 0.1:
        units["rs"] = {"bull": 60, "bear": 40}
    elif rs_strength <= -0.1:
        units["rs"] = {"bull": 40, "bear": 60}
    else:
        units["rs"] = {"bull": 50, "bear": 50}

    return units
