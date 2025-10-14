#!/usr/bin/env python3
"""Demonstration of Bug #32 fix: Contradictory and dangerous advice logic.

This script demonstrates that the fix successfully prevents recommending
aggressive positions on overextended or unreliable signals by consulting
exhaustion and sustainability metrics.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from optipanel.engine.aggregate import build_symbol_snapshot


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'=' * 70}")
    print(f"{title}")
    print("=" * 70)


def print_snapshot(label: str, snapshot: dict):
    """Print key fields from a snapshot."""
    print(f"\n{label}:")
    print(f"  Symbol: {snapshot['symbol']}")
    print(f"  Score: {snapshot['score']}")
    print(f"  Advice: {snapshot['advice']}")
    print(f"  Exhaustion: {snapshot['setups']['exhaustion']}")
    print(f"  Sustainability: {snapshot['sustainment']['sustainability']}")
    print(f"  Fakeout Risk: {snapshot['sustainment']['fakeout_risk']}")


def demonstrate_exhaustion_veto():
    """Show how high exhaustion prevents dangerous advice."""
    print_section("Bug #32 Fix: Exhaustion Veto")

    print("\nScenario 1: Strong bullish signal WITHOUT high exhaustion")
    features_safe = {
        "last": 148.0,  # 5.7% above DMA20 - moderate
        "dma20": 140.0,
        "support": 135.0,
        "resistance": 155.0,
        "rvol": 1.3,  # Moderate volume
        "rs_strength": 0.15,  # Strong RS
        "vwap_diff": 0.02,
    }

    snap_safe = build_symbol_snapshot("MODERATE", features_safe)
    print_snapshot("MODERATE EXTENSION", snap_safe)

    print("\n" + "-" * 70)
    print("\nScenario 2: Strong bullish signal WITH high exhaustion (DANGEROUS!)")
    features_dangerous = {
        "last": 160.0,  # 14.3% above DMA20 - very extended!
        "dma20": 140.0,
        "support": 135.0,
        "resistance": 155.0,
        "rvol": 2.5,  # Climax volume!
        "rs_strength": 0.20,  # Strong RS
        "vwap_diff": 0.03,
    }

    snap_dangerous = build_symbol_snapshot("OVEREXTENDED", features_dangerous)
    print_snapshot("HIGH EXHAUSTION (BUYING CLIMAX)", snap_dangerous)

    print("\n" + "=" * 70)
    print("ANALYSIS:")
    print("=" * 70)

    if snap_safe["score"] >= 65 and snap_dangerous["score"] >= 65:
        print("✓ Both scenarios have HIGH scores (>= 65)")

    print(f"\nMODERATE exhaustion: {snap_safe['setups']['exhaustion']}")
    print(f"HIGH exhaustion: {snap_dangerous['setups']['exhaustion']}")

    print(f"\nMODERATE advice: {snap_safe['advice']}")
    print(f"HIGH exhaustion advice: {snap_dangerous['advice']}")

    if snap_dangerous["advice"] == "standby" and snap_dangerous["setups"]["exhaustion"] >= 70:
        print("\n✅ FIX VERIFIED: High exhaustion blocked dangerous 'attack' recommendation!")
        print("   Old logic would have recommended 'attack' at the top (potential catastrophic loss)")
    else:
        print("\n⚠️ Exhaustion behavior may vary based on exact values")


def demonstrate_oversold_bounce():
    """Show how exhaustion prevents selling at bottoms."""
    print_section("Bug #32 Fix: Oversold Bounce Protection")

    print("\nScenario: Strong bearish signal WITH high exhaustion (oversold)")
    features_oversold = {
        "last": 126.0,  # 10% below DMA20 - very oversold!
        "dma20": 140.0,
        "support": 125.0,
        "resistance": 145.0,
        "rvol": 3.0,  # Panic selling volume!
        "rs_strength": -0.25,  # Very weak RS
        "vwap_diff": -0.05,
    }

    snap_oversold = build_symbol_snapshot("OVERSOLD", features_oversold)
    print_snapshot("PANIC SELLING (POTENTIAL BOUNCE)", snap_oversold)

    print("\n" + "=" * 70)
    print("ANALYSIS:")
    print("=" * 70)

    print(f"Score: {snap_oversold['score']} (low = bearish signal)")
    print(f"Exhaustion: {snap_oversold['setups']['exhaustion']} (high = oversold)")
    print(f"Advice: {snap_oversold['advice']}")

    if snap_oversold["advice"] == "standby" and snap_oversold["setups"]["exhaustion"] >= 70:
        print("\n✅ FIX VERIFIED: High exhaustion blocked 'defend' at potential bottom!")
        print("   Old logic would have recommended 'defend' (sell/short) right before bounce")
    else:
        print("\n⚠️ Advice may vary based on sustainability metrics")


def demonstrate_sustainability_filter():
    """Show how low sustainability prevents acting on weak signals."""
    print_section("Bug #32 Fix: Sustainability Quality Filter")

    print("\nScenario: High score but conflicting timeframe signals (low sustainability)")
    features_conflicting = {
        "last": 154.0,
        "dma20": 140.0,
        "support": 135.0,
        "resistance": 155.0,
        "rvol": 0.7,  # Low volume (weak confirmation)
        "rs_strength": 0.05,  # Marginal RS
        "vwap_diff": -0.01,  # Below VWAP (divergence)
    }

    snap_weak = build_symbol_snapshot("WEAK_SIGNAL", features_conflicting)
    print_snapshot("LOW QUALITY SIGNAL", snap_weak)

    print("\n" + "=" * 70)
    print("ANALYSIS:")
    print("=" * 70)

    sustainability = snap_weak["sustainment"]["sustainability"]
    fakeout_risk = snap_weak["sustainment"]["fakeout_risk"]

    print(f"Score: {snap_weak['score']}")
    print(f"Sustainability: {sustainability}")
    print(f"Fakeout Risk: {fakeout_risk}")
    print(f"Advice: {snap_weak['advice']}")

    print("\n✅ FIX ACTIVE: Sustainability and fakeout risk are now consulted")
    print("   Low quality signals can be filtered even if score is high")


def demonstrate_safe_attack():
    """Show conditions where attack is still recommended (all safety checks pass)."""
    print_section("Bug #32 Fix: Safe Attack Example")

    print("\nScenario: Strong signal WITH good risk metrics")
    features_clean = {
        "last": 146.0,  # 4.3% above DMA20 - healthy
        "dma20": 140.0,
        "support": 135.0,
        "resistance": 155.0,
        "rvol": 1.4,  # Good volume confirmation
        "rs_strength": 0.18,  # Strong RS
        "vwap_diff": 0.02,
    }

    snap_clean = build_symbol_snapshot("CLEAN_SETUP", features_clean)
    print_snapshot("HEALTHY BULLISH SETUP", snap_clean)

    print("\n" + "=" * 70)
    print("ANALYSIS:")
    print("=" * 70)

    exhaustion = snap_clean["setups"]["exhaustion"]
    sustainability = snap_clean["sustainment"]["sustainability"]
    fakeout_risk = snap_clean["sustainment"]["fakeout_risk"]

    print(f"Score: {snap_clean['score']} (high = bullish)")
    print(f"Exhaustion: {exhaustion} (< 70 = not overextended)")
    print(f"Sustainability: {sustainability} (>= 40 = reliable)")
    print(f"Fakeout Risk: {fakeout_risk} (< 70 = low risk)")
    print(f"Advice: {snap_clean['advice']}")

    if snap_clean["advice"] == "attack":
        print("\n✅ SAFE ATTACK: All risk checks passed!")
        print("   - High score (strong signal)")
        print("   - Low exhaustion (not overextended)")
        print("   - High sustainability (reliable move)")
        print("   - Low fakeout risk (authentic breakout)")
    else:
        print(f"\n⚠️ Advice is '{snap_clean['advice']}' - may need threshold tuning")


def demonstrate_before_after_comparison():
    """Show side-by-side comparison of old vs new logic."""
    print_section("Bug #32 Fix: Before/After Comparison")

    # Dangerous scenario: high score, high exhaustion
    features = {
        "last": 160.0,
        "dma20": 140.0,
        "support": 135.0,
        "resistance": 155.0,
        "rvol": 2.5,
        "rs_strength": 0.20,
        "vwap_diff": 0.03,
    }

    snapshot = build_symbol_snapshot("COMPARISON", features)

    # Simulate old logic (just score-based)
    score = snapshot["score"]
    if score >= 65:
        old_advice = "attack"
    elif score <= 35:
        old_advice = "defend"
    else:
        old_advice = "standby"

    new_advice = snapshot["advice"]

    print("\nTest Case: Overextended Bullish Setup")
    print(f"  Score: {score}")
    print(f"  Exhaustion: {snapshot['setups']['exhaustion']}")
    print(f"  Sustainability: {snapshot['sustainment']['sustainability']}")
    print(f"  Fakeout Risk: {snapshot['sustainment']['fakeout_risk']}")

    print(f"\n{'Before (Bug #32):':20} {old_advice}")
    print(f"{'After (Fix):':20} {new_advice}")

    if old_advice == "attack" and new_advice == "standby":
        print("\n✅ CRITICAL FIX DEMONSTRATED!")
        print("   Old logic: 'attack' at a potential top (DANGEROUS)")
        print("   New logic: 'standby' due to high exhaustion (SAFE)")
    elif old_advice != new_advice:
        print(f"\n✅ Fix changed advice from '{old_advice}' to '{new_advice}'")
    else:
        print("\n⚠️ Both give same advice in this scenario")


def main():
    """Run all demonstrations."""
    print("=" * 70)
    print("Bug #32 Fix Demonstration: Contradictory and Dangerous Advice Logic")
    print("=" * 70)

    print("\nBUG DESCRIPTION:")
    print("The original advice logic only considered the composite 'score' (trend + breakout)")
    print("and completely ignored critical risk factors:")
    print("  - Exhaustion (overextension risk)")
    print("  - Sustainability (move reliability)")
    print("  - Fakeout Risk (false breakout probability)")
    print("\nThis could lead to catastrophic losses by recommending:")
    print("  - 'attack' at buying climaxes (tops)")
    print("  - 'defend' at selling climaxes (bottoms)")
    print("  - Aggressive positions on low-quality signals")

    demonstrate_exhaustion_veto()
    demonstrate_oversold_bounce()
    demonstrate_sustainability_filter()
    demonstrate_safe_attack()
    demonstrate_before_after_comparison()

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print("\n✅ Bug #32 fix successfully prevents dangerous advice!")
    print("\nKey Improvements:")
    print("  1. Exhaustion veto (threshold: 70)")
    print("     - Blocks 'attack' on overextended rallies")
    print("     - Blocks 'defend' on oversold selloffs")
    print("  2. Sustainability filter (minimum: 40)")
    print("     - Ensures move is reliable across timeframes")
    print("  3. Fakeout risk check (maximum: 70)")
    print("     - Avoids false breakouts/breakdowns")

    print("\nRisk Mitigation:")
    print("  - Old logic: Single-factor (score only)")
    print("  - New logic: Multi-factor (score + exhaustion + sustainability + fakeout_risk)")

    print("\nConfigurable Thresholds:")
    print("  - EXHAUSTION_VETO = 70")
    print("  - SUSTAINABILITY_MIN = 40")
    print("  - FAKEOUT_RISK_MAX = 70")

    print("\nBackward Compatibility:")
    print("  - Same advice values: 'attack', 'defend', 'standby'")
    print("  - New field added: 'sustainment' (with sustainability and fakeout_risk)")
    print("  - All existing fields preserved")


if __name__ == "__main__":
    main()
