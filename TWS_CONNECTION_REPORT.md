# TWS Connection Error Report for Codex

## Executive Summary
The TWS connection was failing due to an API signature mismatch in the error handler. The ibapi library version 10.37.2 sends 5 parameters to the error() method, but our override only expected 4.

## Error Details

### Error Message
```
TypeError: _BaseApp.error() takes from 4 to 5 positional arguments but 6 were given
```

### Location
File: `optipanel/adapters/ibkr/tws_fetcher.py`
Line: 99
Method: `error()`

### Root Cause
The Interactive Brokers API (ibapi) version 10.37.2 has changed the error handler signature compared to earlier versions (9.81.1).

#### Old Signature (ibapi < 10.25)
```python
def error(self, reqId: int, code: int, msg: str, advancedOrderRejectJson: str = ""):
```

#### New Signature (ibapi >= 10.25)
```python
def error(self, reqId: int, errorTime: str, code: int, msg: str, advancedOrderRejectJson: str = ""):
```

Note the addition of `errorTime` as the second parameter.

## The Fix

### Original Code (Line 99)
```python
def error(self, reqId, code, msg, advancedOrderRejectJson=""):
    self.errors.append((reqId, code, msg))
    super().error(reqId, code, msg, advancedOrderRejectJson)
```

### Fixed Code
```python
def error(self, reqId, errorTime, code, msg, advancedOrderRejectJson=""):
    _ = errorTime  # parameter retained for ibapi>=10.25 compatibility
    self.errors.append((reqId, code, msg))
    super().error(reqId, errorTime, code, msg, advancedOrderRejectJson)
```

## Why I Could Connect But Codex Couldn't

The error occurs at different stages:

1. **Initial Connection**: Works for both of us
   - Socket connection established
   - Handshake initiated

2. **During Handshake**: Where the error occurs
   - TWS sends various status messages
   - Some trigger the error() callback
   - Our old signature couldn't handle the new format

3. **My Debugging Advantage**:
   - I could see the full stack trace immediately
   - I identified the signature mismatch from the TypeError
   - I checked the ibapi version and documentation

## Version Information

### Currently Installed
```
ibapi==10.37.2
```

### pyproject.toml Requirement
```toml
# Was: "ibapi>=9.81.1"
# Now: "ibapi>=10.19.1"
```

## Testing After Fix

### Test Command
```python
from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher, cfg_from_env

config = cfg_from_env()
fetcher = RealTwsFetcher(config)
result = fetcher.handshake_test()
print(result)
```

### Successful Output
```json
{
  "handshake": "ok",
  "features": {
    "SPY": {"last": 661.10, "dma20": 559.84, ...},
    "AAPL": {"last": 252.31, "dma20": 224.68, ...},
    "MSFT": {"last": 510.15, "dma20": 426.37, ...}
  }
}
```

## Recommendations for Codex

1. **Always check ibapi version compatibility**:
   ```bash
   pip show ibapi
   ```

2. **When debugging connection issues**:
   - Check the full stack trace
   - Look for TypeError in error handlers
   - Verify method signatures match the installed version

3. **Future-proof the code**:
   - Use *args, **kwargs for better compatibility
   - Or explicitly check ibapi version and use appropriate signature

## Alternative Future-Proof Implementation

```python
def error(self, *args, **kwargs):
    """Handle errors with version compatibility."""
    # Extract what we need regardless of signature
    if len(args) >= 4:
        reqId = args[0]
        # Skip errorTime if present (ibapi >= 10.25)
        if len(args) == 5:
            code = args[2]
            msg = args[3]
        else:
            code = args[1]
            msg = args[2]
        self.errors.append((reqId, code, msg))

    # Pass through to parent
    super().error(*args, **kwargs)
```

## Conclusion

The issue was a simple API version incompatibility. The ibapi library evolved its error handler signature, and our code needed to match. This is a common issue when working with third-party APIs that evolve over time.

---
*Report Generated: 2025-09-25*
*For: Codex Debugging Team*
*Issue Status: RESOLVED*