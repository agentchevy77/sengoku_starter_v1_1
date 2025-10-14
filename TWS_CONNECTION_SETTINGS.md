# TWS Connection Settings - Complete Configuration Guide

## Environment Variables

### Core Connection Settings
```bash
# Host address for TWS/Gateway
export SENGOKU_TWS_HOST="127.0.0.1"  # Default: localhost

# Port number
export SENGOKU_TWS_PORT="7496"  # Paper trading (7497 for live)

# Client ID (must be unique per connection)
export SENGOKU_TWS_CLIENT_ID="107"  # Default: 107

# Connection timeout in seconds
export SENGOKU_TWS_TIMEOUT="10"  # Default: 10 seconds
```

### Rate Limiting Settings
```bash
# Maximum requests per second
export SENGOKU_TWS_MAX_RPS="50"  # Default: 50

# Pacing buffer (seconds between requests)
export SENGOKU_TWS_PACING="0.02"  # Default: 20ms
```

### Cache Settings
```bash
# Enable/disable caching
export SENGOKU_CACHE_ENABLED="true"

# Cache TTL in seconds
export SENGOKU_CACHE_TTL="300"  # Default: 5 minutes

# Cache directory
export SENGOKU_CACHE_DIR="/tmp/sengoku_cache"
```

## Configuration File (Optional)
Create `~/.sengoku/tws.yaml`:
```yaml
connection:
  host: "127.0.0.1"
  port: 7496
  client_id: 107
  timeout: 10

rate_limiting:
  max_rps: 50
  pacing_ms: 20

cache:
  enabled: true
  ttl_seconds: 300
  directory: "/tmp/sengoku_cache"

features:
  enable_historical_data: true
  enable_realtime_quotes: true
  enable_options: false
```

## TWS/Gateway Configuration

### TWS Settings (Interactive Brokers Side)
1. **API Settings**:
   - Enable ActiveX and Socket Clients
   - Socket port: 7496 (paper) or 7497 (live)
   - Master API client ID: Leave blank
   - Allow connections from: 127.0.0.1

2. **Security**:
   - Read-Only API: No (unless only reading)
   - Bypass order precautions: Optional
   - Trusted IP Addresses: 127.0.0.1

3. **Market Data**:
   - Market data subscription required
   - Enable delayed data if no subscription

## Testing Connection

### Basic Test
```bash
# Test connection with environment variables
export SENGOKU_TWS_HOST="127.0.0.1"
export SENGOKU_TWS_PORT="7496"
python -c "
from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher, cfg_from_env
fetcher = RealTwsFetcher(cfg_from_env())
print(fetcher.handshake_test())
"
```

### Expected Output
```json
{
  "handshake": "ok",
  "server_version": 176,
  "connection_time": "20250925 10:30:45 EST"
}
```

## Common Issues and Solutions

### Issue 1: Connection Refused
```
Error: Couldn't connect to TWS. Confirm that API is enabled.
```
**Solution**:
- Ensure TWS/Gateway is running
- Check API is enabled in TWS settings
- Verify port number (7496 vs 7497)

### Issue 2: Client Already Connected
```
Error: Client 107 is already connected
```
**Solution**:
- Change SENGOKU_TWS_CLIENT_ID to different number
- Or disconnect existing client in TWS

### Issue 3: No Market Data
```
Error: No market data permissions
```
**Solution**:
- Subscribe to market data
- Or enable delayed data in TWS

### Issue 4: API Version Mismatch
```
Error: _BaseApp.error() takes from 4 to 5 positional arguments but 6 were given
```
**Solution**:
- Update error handler signature (already fixed in codebase)
- Ensure ibapi>=10.19.1 is installed

## Production Configuration

### High-Performance Settings
```bash
# Optimized for production
export SENGOKU_TWS_HOST="tws-server.internal"
export SENGOKU_TWS_PORT="7496"
export SENGOKU_TWS_CLIENT_ID="1001"
export SENGOKU_TWS_MAX_RPS="100"
export SENGOKU_TWS_PACING="0.01"
export SENGOKU_CACHE_ENABLED="true"
export SENGOKU_CACHE_TTL="60"
```

### Monitoring
```bash
# Enable detailed logging
export SENGOKU_LOG_LEVEL="DEBUG"
export SENGOKU_LOG_DIR="/var/log/sengoku"
```

## Verification Script
```python
#!/usr/bin/env python3
"""Verify TWS connection settings."""

import os
import sys
from pathlib import Path

def check_tws_config():
    config = {
        'host': os.getenv('SENGOKU_TWS_HOST', '127.0.0.1'),
        'port': os.getenv('SENGOKU_TWS_PORT', '7496'),
        'client_id': os.getenv('SENGOKU_TWS_CLIENT_ID', '107'),
    }

    print("Current TWS Configuration:")
    print("-" * 30)
    for key, value in config.items():
        print(f"{key:15} : {value}")

    # Test connection
    try:
        from optipanel.adapters.ibkr.tws_fetcher import RealTwsFetcher, cfg_from_env
        fetcher = RealTwsFetcher(cfg_from_env())
        result = fetcher.handshake_test()
        print("\n✅ Connection successful!")
        print(f"Server version: {result.get('server_version')}")
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(check_tws_config())
```

---
*Generated: 2025-09-25*
*For issues, check logs in $SENGOKU_LOG_DIR*