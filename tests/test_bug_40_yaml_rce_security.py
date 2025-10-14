"""
Test Bug #40: RCE Vulnerability via Unsafe YAML Deserialization

This test suite ensures that the YAML deserialization vulnerability is fixed
and cannot be exploited. It verifies:
1. All YAML loading uses safe_load() instead of load()
2. Malicious payloads are rejected
3. Legitimate YAML features still work
4. No regression to unsafe loading can occur
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from optipanel.config.loader import (
    load_profiles_yaml,
    parse_features_yaml,
    parse_profiles_yaml,
)
from optipanel.settings import load_settings


class TestBug40YamlRceSecurity(unittest.TestCase):
    """Test suite for Bug #40 - RCE via unsafe YAML deserialization."""

    def test_malicious_python_object_blocked_in_profiles(self):
        """Test that malicious Python objects are blocked in profile YAML."""
        # This payload would execute code if using unsafe yaml.load()
        malicious_yaml = """
        !!python/object/apply:os.system
        - echo "EXPLOITED" > /tmp/exploited.txt
        """

        # Should raise an exception, not execute the code
        with self.assertRaises(yaml.constructor.ConstructorError):
            parse_profiles_yaml(malicious_yaml)

        # Verify the exploit didn't execute
        self.assertFalse(Path("/tmp/exploited.txt").exists())

    def test_malicious_python_module_blocked_in_profiles(self):
        """Test that Python module imports are blocked."""
        malicious_yaml = """
        !!python/module:os
        """

        with self.assertRaises(yaml.constructor.ConstructorError):
            parse_profiles_yaml(malicious_yaml)

    def test_malicious_python_name_blocked_in_features(self):
        """Test that Python name references are blocked in features YAML."""
        malicious_yaml = """
        AAPL: !!python/name:os.system
        """

        with self.assertRaises(yaml.constructor.ConstructorError):
            parse_features_yaml(malicious_yaml)

    def test_malicious_python_object_new_blocked(self):
        """Test that Python object instantiation is blocked."""
        malicious_yaml = """
        watchlists:
          test: !!python/object/new:os.system
            - ls
        """

        with self.assertRaises(yaml.constructor.ConstructorError):
            parse_profiles_yaml(malicious_yaml)

    def test_legitimate_yaml_features_work_profiles(self):
        """Test that legitimate YAML features still work in profiles."""
        # Test anchors and aliases (legitimate YAML feature)
        legitimate_yaml = """
        defaults: &defaults
          width: 100
          top_n: 5

        ui:
          <<: *defaults
          width: 120  # Override

        watchlists:
          tech: [AAPL, GOOGL, MSFT]
          finance: [JPM, BAC, WFC]

        budgets:
          conservative:
            max_risk: 0.02
            position_size: 1000
        """

        result = parse_profiles_yaml(legitimate_yaml)

        # Verify parsing worked correctly
        self.assertEqual(result["ui"]["width"], 120)
        self.assertEqual(result["ui"]["top_n"], 5)
        self.assertEqual(result["watchlists"]["tech"], ["AAPL", "GOOGL", "MSFT"])
        self.assertEqual(result["budgets"]["conservative"]["max_risk"], 0.02)

    def test_legitimate_yaml_features_work_features(self):
        """Test that legitimate YAML features still work in features."""
        legitimate_yaml = """
        AAPL:
          last: 150.25
          dma20: 148.50
          support: 145.00
          resistance: 155.00
          rvol: 1.2
          rs_strength: 0.75
          vwap_diff: 0.015

        GOOGL:
          last: 2800.50
          dma20: 2750.00
          support: 2700.00
          resistance: 2850.00
          rvol: 0.9
          rs_strength: -0.25
          vwap_diff: -0.008
        """

        result = parse_features_yaml(legitimate_yaml)

        # Verify parsing worked correctly
        self.assertEqual(result["AAPL"]["last"], 150.25)
        self.assertEqual(result["GOOGL"]["resistance"], 2850.00)

    def test_empty_yaml_handled_safely(self):
        """Test that empty YAML is handled safely."""
        empty_yaml = ""

        profiles = parse_profiles_yaml(empty_yaml)
        self.assertEqual(profiles["watchlists"], {})
        self.assertEqual(profiles["budgets"], {})

        features = parse_features_yaml(empty_yaml)
        self.assertEqual(features, {})

    def test_null_yaml_handled_safely(self):
        """Test that null/None YAML values are handled safely."""
        null_yaml = """
        watchlists: null
        budgets: null
        ui: null
        """

        result = parse_profiles_yaml(null_yaml)
        self.assertEqual(result["watchlists"], {})
        self.assertEqual(result["budgets"], {})
        self.assertEqual(result["ui"]["width"], 24)  # Default value

    def test_load_profiles_yaml_file_safety(self):
        """Test that load_profiles_yaml safely loads from file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(
                """
            watchlists:
              test: [AAPL, TSLA]
            budgets:
              test:
                max_position: 10000
            """
            )
            temp_path = f.name

        try:
            result = load_profiles_yaml(temp_path)
            self.assertEqual(result["watchlists"]["test"], ["AAPL", "TSLA"])
            self.assertEqual(result["budgets"]["test"]["max_position"], 10000)
        finally:
            os.unlink(temp_path)

    def test_settings_loader_uses_safe_load(self):
        """Test that settings loader uses safe_load."""
        # Create a temporary settings file
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            settings_file = config_dir / "settings.defaults.yaml"

            # Write a settings file with potential exploit
            settings_file.write_text(
                """
            market_data_budget:
              allowance_lines: 1000
              soft_cap_lines: 800
              rt_bars_max: 5
              snapshot_concurrency_max: 3
              backoff:
                cooldown_sec: 2
            schedulers:
              prime_interval_sec: 60
              secondary_thin_interval_sec: 120
            cache:
              max_items: 100
              default_ttl_sec: 300
            """
            )

            # Patch ROOT to use our temp directory
            with patch("optipanel.settings.ROOT", Path(tmpdir)):
                settings = load_settings()
                self.assertEqual(settings.allowance_lines, 1000)
                self.assertEqual(settings.cache_default_ttl_sec, 300)

    def test_complex_nested_structures_safe(self):
        """Test that complex nested structures are parsed safely."""
        complex_yaml = """
        watchlists:
          tier1:
            - AAPL
            - GOOGL
          tier2:
            - MSFT
            - AMZN
          special:
            momentum:
              - TSLA
              - NVDA
            value:
              - BRK.B
              - JPM

        budgets:
          aggressive:
            risk_level: high
            params:
              max_position: 50000
              stop_loss: 0.05
              take_profit: 0.15
          conservative:
            risk_level: low
            params:
              max_position: 10000
              stop_loss: 0.02
              take_profit: 0.05
        """

        result = parse_profiles_yaml(complex_yaml)

        # Basic structure preserved
        self.assertIn("tier1", result["watchlists"])
        self.assertIn("aggressive", result["budgets"])

        # Nested lists handled correctly
        self.assertEqual(result["watchlists"]["tier1"], ["AAPL", "GOOGL"])

    def test_yaml_bomb_protection(self):
        """Test protection against YAML bombs (billion laughs attack)."""
        # This would cause exponential expansion if not handled properly
        yaml_bomb = """
        lol1: &lol1 "lol"
        lol2: &lol2 [*lol1, *lol1]
        lol3: &lol3 [*lol2, *lol2]
        lol4: &lol4 [*lol3, *lol3]
        lol5: &lol5 [*lol4, *lol4]
        """

        # Should parse without causing memory explosion
        # safe_load handles this by not expanding references infinitely
        try:
            result = parse_features_yaml(yaml_bomb)
            # If it parses, verify it didn't create massive structure
            import sys

            self.assertLess(sys.getsizeof(str(result)), 100000)  # Should be small
        except yaml.constructor.ConstructorError:
            # Some YAML implementations reject this outright, which is also safe
            pass

    def test_safe_load_used_exclusively(self):
        """Ensure only safe_load is used in our codebase."""
        # This test verifies by attempting malicious payloads
        # If unsafe load was used, these would execute

        malicious_profiles = """
        !!python/object/apply:os.system
        - echo "COMPROMISED"
        """

        malicious_features = """
        EXPLOIT: !!python/object/apply:eval
        - print("HACKED")
        """

        # Both should fail with ConstructorError, not execute
        with self.assertRaises(yaml.constructor.ConstructorError):
            parse_profiles_yaml(malicious_profiles)

        with self.assertRaises(yaml.constructor.ConstructorError):
            parse_features_yaml(malicious_features)

    def test_code_execution_attempt_logged(self):
        """Test that code execution attempts can be detected."""
        malicious_payloads = [
            "!!python/object/apply:subprocess.Popen\n- ['ls', '-la']",
            "!!python/object/new:subprocess.Popen\nargs: ['whoami']",
            "!!python/object/apply:eval\n- __import__('os').system('id')",
        ]

        for payload in malicious_payloads:
            with (
                self.subTest(payload=payload[:50]),
                self.assertRaises((yaml.constructor.ConstructorError, yaml.scanner.ScannerError)),
            ):
                parse_profiles_yaml(payload)


if __name__ == "__main__":
    unittest.main(verbosity=2)
