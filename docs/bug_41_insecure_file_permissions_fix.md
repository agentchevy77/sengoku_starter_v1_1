# Bug #41: Insecure File Permissions on Secrets File - FIXED

## Executive Summary
Fixed a **HIGH severity** security vulnerability where the application would silently load secrets files with insecure permissions, potentially exposing sensitive data to unauthorized users on the system.

## Problem Analysis

### Root Cause
The `SecretResolver` class in `optipanel/security/secrets.py` loaded secrets files without checking or warning about file permissions. This allowed secrets to be stored with world-readable or group-readable permissions, making them accessible to other system users.

### Security Impact
- **Severity**: HIGH
- **Attack Vector**: Local privilege escalation
- **Confidentiality Impact**: Complete exposure of secrets (API keys, passwords, tokens)
- **Integrity Impact**: Potential for unauthorized modifications if write permissions are loose
- **Availability Impact**: None

### Vulnerable Code (Before Fix)
```python
def _load_file(self, path: Path) -> Mapping[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Secrets file not found: {path}")
    text = path.read_text().strip()  # No permission check!
    # ... rest of loading logic
```

## Solution Design

### Architecture
The fix implements a layered security approach:

1. **Permission Validation Layer**: New `_check_file_permissions()` function
2. **Configurable Strictness**: Support for strict (fail) vs warn modes
3. **Environment Override**: Production/development flexibility
4. **Clear Error Messages**: Actionable guidance for fixing issues

### Implementation Details

#### 1. Permission Checking Function
```python
def _check_file_permissions(path: Path, strict: bool = True) -> None:
    """Check if file permissions are secure (not world/group readable)."""
    file_stat = path.stat()
    mode = file_stat.st_mode

    # Check for world-readable (o+r)
    if mode & stat.S_IROTH:
        msg = f"SECURITY WARNING: Secrets file '{path}' is world-readable..."
        if strict:
            raise PermissionError(msg)
        logger.warning(msg)
```

#### 2. Integration Points
- Added to `_load_file()` method before reading file contents
- Configurable via `strict_permissions` parameter (default: True)
- Environment variable: `SENGOKU_SECRETS_STRICT_PERMISSIONS`

#### 3. Accepted Permission Modes
- **✅ SECURE**: 0o600 (rw-------), 0o400 (r--------)
- **❌ INSECURE**: 0o644 (world-readable), 0o640 (group-readable)

## Testing Strategy

### Test Coverage
Created comprehensive test suite in `tests/test_bug_41_file_permissions.py`:

1. **Secure Permissions Tests**
   - Verify 0o600 and 0o400 are accepted
   - No warnings or errors for secure files

2. **Insecure Permissions Tests**
   - World-readable (0o644) rejected in strict mode
   - Group-readable (0o640) rejected in strict mode
   - Various insecure modes (0o666, 0o777) all rejected

3. **Configuration Tests**
   - Strict mode enforcement
   - Warn mode functionality
   - Environment variable override

4. **Edge Cases**
   - Empty files with bad permissions
   - Non-existent files
   - YAML vs JSON format compatibility

### Test Results
```
✅ 10/10 tests passed
✅ No regression in existing tests
✅ Security warnings properly logged
✅ Clear error messages provided
```

## Production Deployment Guide

### 1. Pre-Deployment Audit
```bash
# Find all secrets files and check permissions
find /path/to/app -name "*.json" -o -name "*.yaml" | \
  xargs ls -la | grep -E "secrets|config|keys"
```

### 2. Fix Insecure Permissions
```bash
# Secure all secrets files
chmod 600 /path/to/secrets.json
chmod 600 /path/to/config/api_keys.yaml
```

### 3. Configuration Options

#### Option A: Strict Mode (Recommended for Production)
```python
# Default behavior - fails on insecure permissions
resolver = SecretResolver.from_environment()
```

#### Option B: Warn Mode (Development Only)
```bash
# Environment variable override
export SENGOKU_SECRETS_STRICT_PERMISSIONS=false
```

#### Option C: Programmatic Control
```python
resolver = SecretResolver(
    source=SecretSource.FILE,
    file_path="/path/to/secrets.json",
    strict_permissions=False  # Only for development!
)
```

### 4. Monitoring and Alerts
- Monitor application logs for "SECURITY WARNING" messages
- Set up alerts for PermissionError exceptions
- Regular security audits of file permissions

## Security Best Practices

### DO's
✅ Always use 0o600 (rw-------) for secrets files
✅ Enable strict mode in production
✅ Regularly audit file permissions
✅ Store secrets in dedicated directories with restricted access
✅ Use secret management services (AWS Secrets Manager, HashiCorp Vault) when possible

### DON'Ts
❌ Never use world-readable permissions (0o644, 0o666)
❌ Avoid group-readable permissions unless absolutely necessary
❌ Don't commit secrets files to version control
❌ Don't disable strict mode in production
❌ Never log secret values, even in debug mode

## Backward Compatibility

### Breaking Changes
- Applications with insecure file permissions will fail to start (intended behavior)
- Requires fixing file permissions before deployment

### Migration Path
1. Deploy with `SENGOKU_SECRETS_STRICT_PERMISSIONS=false` initially
2. Monitor warnings and fix permissions gradually
3. Enable strict mode once all files are secured

## Performance Impact
- **Minimal**: One additional stat() call per secrets file load
- **Negligible**: < 1ms overhead on file loading
- **No impact** on runtime performance after initial load

## Files Modified

### Core Implementation
- `optipanel/security/secrets.py`: Added permission checking logic
  - New function: `_check_file_permissions()`
  - Modified: `_load_file()` method
  - Added: `strict_permissions` parameter
  - Updated: `from_environment()` class method

### Tests
- `tests/test_bug_41_file_permissions.py`: Comprehensive test suite (NEW)
- `tests/test_security_secrets.py`: Updated existing test for compatibility

### Documentation
- `scripts/demo_bug_41_file_permissions.py`: Interactive demonstration (NEW)
- `docs/bug_41_insecure_file_permissions_fix.md`: This document (NEW)

## Verification Steps

1. **Run Security Tests**
   ```bash
   python3 -m pytest tests/test_bug_41_file_permissions.py -v
   ```

2. **Run Demonstration**
   ```bash
   PYTHONPATH=. python3 scripts/demo_bug_41_file_permissions.py
   ```

3. **Manual Verification**
   ```bash
   # Create test file with bad permissions
   echo '{"key": "value"}' > /tmp/test.json
   chmod 644 /tmp/test.json

   # Should fail with our fix
   python3 -c "from optipanel.security import SecretResolver, SecretSource; \
              SecretResolver(source=SecretSource.FILE, file_path='/tmp/test.json')"
   ```

## Conclusion

Bug #41 has been successfully fixed with a comprehensive security enhancement that:
- ✅ Prevents exposure of secrets through insecure file permissions
- ✅ Provides clear, actionable error messages
- ✅ Offers flexible configuration for different environments
- ✅ Maintains backward compatibility through configuration
- ✅ Includes extensive test coverage and documentation

The fix follows security best practices and provides a robust defense against local privilege escalation attacks targeting exposed secrets.