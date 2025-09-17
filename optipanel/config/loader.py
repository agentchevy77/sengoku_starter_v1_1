from __future__ import annotations
from typing import Dict, Any
import yaml

def parse_profiles_yaml(text: str) -> Dict[str, Any]:
    data = yaml.safe_load(text) or {}
    wl = data.get("watchlists") or data.get("lists") or {}
    bd = data.get("budgets") or {}
    ui = data.get("ui") or {}
    watchlists = {str(k): list(v or []) for k, v in (wl or {}).items()}
    budgets    = {str(k): dict(v or {}) for k, v in (bd or {}).items()}
    ui_out = {"width": int(ui.get("width", 24)), "top_n": int(ui.get("top_n", 1))}
    return {"watchlists": watchlists, "budgets": budgets, "ui": ui_out}

def parse_features_yaml(text: str) -> Dict[str, Dict[str, Any]]:
    data = yaml.safe_load(text) or {}
    out: Dict[str, Dict[str, Any]] = {}
    for sym, feats in (data or {}).items():
        if isinstance(feats, dict):
            out[str(sym)] = dict(feats)
    return out
