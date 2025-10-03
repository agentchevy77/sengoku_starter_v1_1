#!/usr/bin/env python3
"""
Demonstration of Bug #41 Fix: Insecure File Permissions on Secrets File

This script demonstrates how the fixed SecretResolver now:
1. Detects and rejects insecure file permissions
2. Provides clear security warnings
3. Offers configurable strict/warn modes
"""

import json
import os
import tempfile
from pathlib import Path

from optipanel.security import SecretResolver, SecretSource


def demo_insecure_permissions_rejected():
    """Demonstrate that insecure permissions are rejected by default."""
    print("\n=== Demo 1: Insecure Permissions Rejected (Strict Mode) ===\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a secrets file with sensitive data
        secrets_file = Path(tmpdir) / "api_keys.json"
        secrets = {
            "API_KEY": "sk-secret-1234567890",
            "DATABASE_PASSWORD": "super-secret-password",
            "AWS_SECRET_KEY": "AKIAIOSFODNN7EXAMPLE",
        }
        secrets_file.write_text(json.dumps(secrets, indent=2))

        # Set INSECURE permissions (world-readable)
        secrets_file.chmod(0o644)  # rw-r--r--
        print(f"Created secrets file: {secrets_file}")
        print(f"Current permissions: {oct(secrets_file.stat().st_mode)[-3:]} (INSECURE - world-readable!)")

        # Try to load with default strict mode
        try:
            print("\nAttempting to load secrets with insecure permissions...")
            resolver = SecretResolver(
                source=SecretSource.FILE, file_path=str(secrets_file), strict_permissions=True  # Default behavior
            )
            print("❌ SHOULD NOT REACH HERE - insecure permissions should be rejected!")
        except PermissionError as e:
            print(f"✅ Security check successful! Error raised:\n{e}")

        # Fix permissions and retry
        print("\n--- Fixing permissions ---")
        secrets_file.chmod(0o600)  # rw-------
        print(f"Fixed permissions: {oct(secrets_file.stat().st_mode)[-3:]} (SECURE)")

        print("\nRetrying with secure permissions...")
        resolver = SecretResolver(source=SecretSource.FILE, file_path=str(secrets_file), strict_permissions=True)
        api_key = resolver.get_str("API_KEY")
        print("✅ Successfully loaded secrets!")
        print(f"API_KEY = {api_key[:10]}... (truncated for security)")


def demo_warn_mode():
    """Demonstrate warn mode for non-production environments."""
    print("\n=== Demo 2: Warn Mode (Non-Strict) ===\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        secrets_file = Path(tmpdir) / "dev_secrets.json"
        secrets = {"DEV_API_KEY": "dev-key-12345"}
        secrets_file.write_text(json.dumps(secrets))

        # Set group-readable permissions
        secrets_file.chmod(0o640)  # rw-r-----
        print(f"Created secrets file: {secrets_file}")
        print(f"Current permissions: {oct(secrets_file.stat().st_mode)[-3:]} (group-readable)")

        print("\nLoading with strict_permissions=False (warn mode)...")
        resolver = SecretResolver(
            source=SecretSource.FILE, file_path=str(secrets_file), strict_permissions=False  # Only warn, don't fail
        )

        # Should load despite insecure permissions
        dev_key = resolver.get_str("DEV_API_KEY")
        print(f"✅ Loaded successfully (with warning): {dev_key}")
        print("⚠️  Check logs for security warnings!")


def demo_environment_variable_control():
    """Demonstrate environment variable override for strict mode."""
    print("\n=== Demo 3: Environment Variable Control ===\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        secrets_file = Path(tmpdir) / "env_test.json"
        secrets = {"TEST_SECRET": "env-test-value"}
        secrets_file.write_text(json.dumps(secrets))
        secrets_file.chmod(0o644)  # Insecure

        # Save current env
        old_source = os.environ.get("SENGOKU_SECRETS_SOURCE")
        old_file = os.environ.get("SENGOKU_SECRETS_FILE")
        old_strict = os.environ.get("SENGOKU_SECRETS_STRICT_PERMISSIONS")

        try:
            # Configure via environment variables
            os.environ["SENGOKU_SECRETS_SOURCE"] = "file"
            os.environ["SENGOKU_SECRETS_FILE"] = str(secrets_file)

            # Test with strict mode disabled via env var
            print("Setting SENGOKU_SECRETS_STRICT_PERMISSIONS=false")
            os.environ["SENGOKU_SECRETS_STRICT_PERMISSIONS"] = "false"

            resolver = SecretResolver.from_environment()
            value = resolver.get_str("TEST_SECRET")
            print(f"✅ Loaded with env var override: {value}")

            # Test with strict mode enabled
            print("\nSetting SENGOKU_SECRETS_STRICT_PERMISSIONS=true")
            os.environ["SENGOKU_SECRETS_STRICT_PERMISSIONS"] = "true"

            try:
                resolver = SecretResolver.from_environment()
                print("❌ SHOULD NOT REACH HERE!")
            except PermissionError:
                print("✅ Strict mode enforced via env var!")

        finally:
            # Restore env
            if old_source is None:
                os.environ.pop("SENGOKU_SECRETS_SOURCE", None)
            else:
                os.environ["SENGOKU_SECRETS_SOURCE"] = old_source

            if old_file is None:
                os.environ.pop("SENGOKU_SECRETS_FILE", None)
            else:
                os.environ["SENGOKU_SECRETS_FILE"] = old_file

            if old_strict is None:
                os.environ.pop("SENGOKU_SECRETS_STRICT_PERMISSIONS", None)
            else:
                os.environ["SENGOKU_SECRETS_STRICT_PERMISSIONS"] = old_strict


def demo_various_permissions():
    """Show which permission modes are secure vs insecure."""
    print("\n=== Demo 4: Permission Security Matrix ===\n")

    test_cases = [
        (0o777, "rwxrwxrwx", "CRITICAL - Everyone can read/write/execute"),
        (0o666, "rw-rw-rw-", "CRITICAL - Everyone can read/write"),
        (0o644, "rw-r--r--", "HIGH - World-readable"),
        (0o640, "rw-r-----", "MEDIUM - Group-readable"),
        (0o600, "rw-------", "SECURE - Owner only"),
        (0o400, "r--------", "SECURE - Owner read-only"),
        (0o700, "rwx------", "SECURE - Owner with execute"),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        for mode, mode_str, security_level in test_cases:
            test_file = Path(tmpdir) / f"test_{mode:o}.json"
            test_file.write_text('{"key": "value"}')
            test_file.chmod(mode)

            try:
                resolver = SecretResolver(source=SecretSource.FILE, file_path=str(test_file), strict_permissions=True)
                result = "✅ ACCEPTED"
            except PermissionError:
                result = "🚫 REJECTED"

            print(f"{mode_str} ({mode:o}): {result:<15} | {security_level}")


if __name__ == "__main__":
    print(
        """
╔══════════════════════════════════════════════════════════════════╗
║        Bug #41 Fix: File Permission Security Demonstration       ║
║                                                                  ║
║  This fix prevents secrets from being exposed to unauthorized   ║
║  users by enforcing secure file permissions.                    ║
╚══════════════════════════════════════════════════════════════════╝
    """
    )

    demo_insecure_permissions_rejected()
    demo_warn_mode()
    demo_environment_variable_control()
    demo_various_permissions()

    print("\n" + "=" * 70)
    print("Security Recommendations:")
    print("=" * 70)
    print("1. Always use permissions 600 (rw-------) or 400 (r--------) for secrets")
    print("2. Enable strict mode in production (default behavior)")
    print("3. Use warn mode only in development environments")
    print("4. Regularly audit file permissions with: ls -la /path/to/secrets")
    print("5. Never commit secrets files to version control")
    print("\n✅ Bug #41 has been successfully fixed!")
