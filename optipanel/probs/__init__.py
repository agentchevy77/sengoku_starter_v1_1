"""Probability chips engine (pure)."""

from .core import compute_chips
from .spec import REQUIRED_KEYS, coerce_features

__all__ = ["compute_chips", "REQUIRED_KEYS", "coerce_features"]
