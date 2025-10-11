from __future__ import annotations

import ipaddress
import json
import logging
import os
import re
import threading
import time
from collections import OrderedDict, deque
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from ibapi.client import EClient
from ibapi.contract import Contract

try:
    from optipanel.obs.metrics import record, timer
except Exception:  # pragma: no cover

    def record(name: str, inc: int = 1) -> None:
        pass

    from contextlib import contextmanager

    @contextmanager
    def timer(name: str):
        yield


from ibapi.wrapper import EWrapper

from optipanel.security import SecretResolver
from optipanel.services.ratelimit import RateLimiter
from optipanel.utils.safe_error_handler import SafeErrorHandler

logger = logging.getLogger(__name__)

# Initialize safe error handler for TWS operations
_error_handler = SafeErrorHandler(logger=logger, context="tws_fetcher")


_HOST_PATTERN = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(?:\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$")
_DEFAULT_TWS_HOST = "127.0.0.1"
_DEFAULT_TWS_PORT = 7496


def _sanitize_host(value: Any, source: str, *, default: str | None = None) -> str:
    """Validate and sanitize a hostname or IP address string."""

    if value is None:
        if default is not None:
            return default
        raise ValueError(f"{source} is required")

    host = str(value).strip()
    if not host:
        if default is not None:
            return default
        raise ValueError(f"{source} cannot be empty")

    if len(host) > 253:
        raise ValueError(f"{source} is too long (max 253 characters)")

    if any(ord(ch) < 32 for ch in host):
        raise ValueError(f"{source} contains control characters")

    if "//" in host:
        raise ValueError(f"{source} must not include URL schemes")

    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass

    stripped = host[:-1] if host.endswith(".") else host
    if not _HOST_PATTERN.fullmatch(stripped):
        raise ValueError(f"{source} must be a valid hostname or IP address")

    return stripped


def _sanitize_port(value: Any, source: str, *, default: int | None = None) -> int:
    """Validate and sanitize a TCP port number."""

    if value is None:
        if default is not None:
            return default
        raise ValueError(f"{source} is required")

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped and default is not None:
            return default
        if not re.fullmatch(r"[0-9]+", stripped):
            raise ValueError(f"{source} must be an integer between 1 and 65535")
        port = int(stripped, 10)
    elif isinstance(value, bool):
        raise ValueError(f"{source} must not be boolean")
    elif isinstance(value, int):
        port = value
    elif isinstance(value, float):
        if not value.is_integer():
            raise ValueError(f"{source} must be an integer between 1 and 65535")
        port = int(value)
    else:
        raise ValueError(f"{source} must be an integer between 1 and 65535")

    if not 1 <= port <= 65535:
        raise ValueError(f"{source} must be between 1 and 65535")

    return port


def _default_host() -> str:
    raw = os.getenv("SENGOKU_TWS_HOST")
    return _sanitize_host(raw, "env:SENGOKU_TWS_HOST", default=_DEFAULT_TWS_HOST)


def _default_port() -> int:
    raw = os.getenv("SENGOKU_TWS_PORT")
    return _sanitize_port(raw, "env:SENGOKU_TWS_PORT", default=_DEFAULT_TWS_PORT)


@dataclass
class OrderRejectionDetails:
    """Structured storage for advanced order rejection information.

    Bug #56 FIX: Capture and parse advancedOrderRejectJson from IB API
    for comprehensive order rejection debugging and monitoring.

    Attributes:
        request_id: Request ID associated with the rejected order
        error_code: IB API error code
        error_message: Human-readable error message
        timestamp: Unix timestamp when error occurred
        rejection_data: Parsed JSON data with rejection details
        raw_json: Original JSON string for reference
    """

    request_id: int
    error_code: int
    error_message: str
    timestamp: float
    rejection_data: dict[str, Any] = field(default_factory=dict)
    raw_json: str = ""


@dataclass(frozen=True)
class TwsConfig:
    host: str = field(default_factory=_default_host)
    port: int = field(default_factory=_default_port)
    client_id: int = int(os.getenv("SENGOKU_TWS_CLIENT_ID", "107"))
    ref_symbol: str | None = os.getenv("SENGOKU_TWS_REF", "SPY")

    # timeouts
    handshake_timeout: float = float(os.getenv("SENGOKU_TWS_HANDSHAKE", "7.0"))
    hist_timeout: float = float(os.getenv("SENGOKU_TWS_HIST_TIMEOUT", "15.0"))

    # caching (seconds)
    daily_ttl_sec: float = float(os.getenv("SENGOKU_TWS_DAILY_TTL", str(23 * 60 * 60)))  # off-hours
    intraday_ttl_sec: float = float(os.getenv("SENGOKU_TWS_INTRADAY_TTL", "300"))  # during market
    dynamic_ttl: bool = bool(int(os.getenv("SENGOKU_TWS_DYNAMIC_TTL", "1")))
    stale_ok_sec: float = float(os.getenv("SENGOKU_TWS_STALE_OK", "900"))  # fallback window

    # cache size
    daily_max_entries: int = int(os.getenv("SENGOKU_TWS_DAILY_MAX_ENTRIES", "100"))

    # pacing
    pacing_interval_sec: float = float(os.getenv("SENGOKU_TWS_PACING_INTERVAL", "5.0"))
    pacing_max_requests: int = int(os.getenv("SENGOKU_TWS_PACING_MAX_REQS", "40"))
    pacing_min_delay_sec: float = float(os.getenv("SENGOKU_TWS_PACING_MIN_DELAY", "0.2"))
    pacing_error_delay_sec: float = float(os.getenv("SENGOKU_TWS_PACING_ERROR_DELAY", "2.0"))

    # global rate limiting
    global_rate_max_requests: int = int(os.getenv("SENGOKU_TWS_GLOBAL_MAX_REQS", "120"))
    global_rate_interval_sec: float = float(os.getenv("SENGOKU_TWS_GLOBAL_INTERVAL", "60.0"))

    def __post_init__(self) -> None:
        host = _sanitize_host(self.host, "TwsConfig.host", default=_DEFAULT_TWS_HOST)
        port = _sanitize_port(self.port, "TwsConfig.port", default=_DEFAULT_TWS_PORT)
        object.__setattr__(self, "host", host)
        object.__setattr__(self, "port", port)


def cfg_from_env(resolver: SecretResolver | None = None) -> TwsConfig:
    if resolver is None:
        try:
            resolver = SecretResolver.from_environment()
        except PermissionError as exc:
            logger.warning("Secrets file permissions warning: %s", exc)
            os.environ.setdefault("SENGOKU_SECRETS_STRICT_PERMISSIONS", "false")
            resolver = SecretResolver.from_environment()
    host_raw = resolver.get_str("SENGOKU_TWS_HOST", default=_DEFAULT_TWS_HOST)
    port_raw = resolver.get_str("SENGOKU_TWS_PORT", default=str(_DEFAULT_TWS_PORT))
    host = _sanitize_host(host_raw, "resolver:SENGOKU_TWS_HOST", default=_DEFAULT_TWS_HOST)
    port = _sanitize_port(port_raw, "resolver:SENGOKU_TWS_PORT", default=_DEFAULT_TWS_PORT)
    return TwsConfig(
        host=host,
        port=port,
        client_id=resolver.get_int("SENGOKU_TWS_CLIENT_ID", default=107) or 107,
        ref_symbol=resolver.get_str("SENGOKU_TWS_REF", default="SPY"),
        handshake_timeout=resolver.get_float("SENGOKU_TWS_HANDSHAKE", default=7.0) or 7.0,
        hist_timeout=resolver.get_float("SENGOKU_TWS_HIST_TIMEOUT", default=15.0) or 15.0,
        daily_ttl_sec=resolver.get_float("SENGOKU_TWS_DAILY_TTL", default=float(23 * 60 * 60)) or float(23 * 60 * 60),
        intraday_ttl_sec=resolver.get_float("SENGOKU_TWS_INTRADAY_TTL", default=300.0) or 300.0,
        dynamic_ttl=resolver.get_bool("SENGOKU_TWS_DYNAMIC_TTL", default=True),
        stale_ok_sec=resolver.get_float("SENGOKU_TWS_STALE_OK", default=900.0) or 900.0,
        daily_max_entries=resolver.get_int("SENGOKU_TWS_DAILY_MAX_ENTRIES", default=100) or 100,
        pacing_interval_sec=resolver.get_float("SENGOKU_TWS_PACING_INTERVAL", default=5.0) or 5.0,
        pacing_max_requests=resolver.get_int("SENGOKU_TWS_PACING_MAX_REQS", default=40) or 40,
        pacing_min_delay_sec=resolver.get_float("SENGOKU_TWS_PACING_MIN_DELAY", default=0.2) or 0.2,
        pacing_error_delay_sec=resolver.get_float("SENGOKU_TWS_PACING_ERROR_DELAY", default=2.0) or 2.0,
        global_rate_max_requests=resolver.get_int("SENGOKU_TWS_GLOBAL_MAX_REQS", default=120) or 120,
        global_rate_interval_sec=resolver.get_float("SENGOKU_TWS_GLOBAL_INTERVAL", default=60.0) or 60.0,
    )


class _BaseApp(EWrapper, EClient):
    # Bug #43 FIX: Comprehensive IB API error code classification
    # Based on official IB API documentation and empirical testing
    _ERROR_CLASSIFICATIONS = {
        # Informational messages (1000-1999) - System status, not errors
        1100: "info",  # Connectivity between IB and TWS has been lost
        1101: "info",  # Connectivity between IB and TWS has been restored - data lost
        1102: "info",  # Connectivity between IB and TWS has been restored - data maintained
        1300: "info",  # TWS socket port has been reset
        # Market data farm connection messages (2100-2199) - Non-fatal warnings
        2100: "warning",  # API client has been unsubscribed from account data
        2101: "warning",  # API client has been subscribed to account data
        2102: "warning",  # ActiveX API client has been unsubscribed from account data
        2103: "warning",  # Market data farm connection is OK
        2104: "warning",  # Market data farm connection is OK (alternate farm)
        2105: "warning",  # HMDS data farm connection is OK
        2106: "warning",  # HMDS data farm connection is OK (alternate farm)
        2107: "warning",  # HMDS data farm connection is inactive but should be available
        2108: "warning",  # Market data farm connection is inactive but should be available
        2109: "warning",  # HMDS data farm connection is inactive but should be available
        2110: "warning",  # Connectivity between TWS and server is broken
        2119: "warning",  # Market data farm is connecting
        2137: "warning",  # Cross connect feature is enabled
        2158: "warning",  # Sec-def data farm connection is OK
        # Request-specific errors (200-599) - Generally fatal
        200: "error",  # No security definition found
        201: "error",  # Order rejected - Reason provided
        202: "error",  # Order cancelled
        203: "error",  # Security not available for short sale
        320: "error",  # Invalid ticker action
        321: "error",  # Invalid action
        322: "error",  # Invalid quantity
        323: "error",  # Invalid order
        324: "error",  # Invalid account
        325: "error",  # Invalid operation
        326: "error",  # Request not supported
        354: "error",  # Requested market data is not subscribed
        357: "error",  # Requested market data is not available
        365: "error",  # No historical data query found
        366: "error",  # No historical data available
        383: "error",  # Invalid contract
        384: "error",  # Contract not visible
        399: "error",  # Order message error
        # System/Connection errors (500-599) - Fatal
        501: "critical",  # Already connected
        502: "critical",  # Couldn't connect to TWS
        503: "critical",  # The TWS is out of date
        504: "critical",  # Not connected to TWS
        505: "critical",  # Fatal error
        506: "critical",  # Unsupported version
        507: "critical",  # Bad message length
        508: "critical",  # Bad message
        509: "critical",  # Exception caught
        510: "critical",  # Unexpected error
        511: "critical",  # Request parsing error
        512: "critical",  # Response parsing error
        513: "critical",  # Socket exception
        514: "critical",  # Failure creating socket
        515: "critical",  # Verification failed
        516: "critical",  # Hash doesn't match
        517: "critical",  # Unexpected incoming message
        # Misc warnings (10000+) - Non-fatal
        10167: "warning",  # Requested market data is delayed
        10168: "warning",  # Requested delayed market data is not available
        10197: "warning",  # No market data permissions
    }

    # Backward compatibility: Keep NON_FATAL for existing code
    _NON_FATAL = {code for code, level in _ERROR_CLASSIFICATIONS.items() if level in ("info", "warning")}

    # Bug #1 FIX: Bounded error accumulation to prevent memory leak
    _MAX_ERRORS = int(os.getenv("SENGOKU_TWS_MAX_ERRORS", "100"))

    # Bug #56 FIX: Storage for advanced order rejection details
    _MAX_REJECTIONS = int(os.getenv("SENGOKU_TWS_MAX_REJECTIONS", "50"))

    def __init__(self):
        EClient.__init__(self, self)
        self.ready = threading.Event()
        # Bug #1 FIX: Use deque with maxlen to automatically evict oldest errors
        # This prevents unbounded memory growth in long-running processes
        self.errors: deque[tuple[int, str]] = deque(maxlen=self._MAX_ERRORS)
        # Bug #56 FIX: Bounded storage for order rejection details
        self.rejection_details: deque[OrderRejectionDetails] = deque(maxlen=self._MAX_REJECTIONS)

    def error(self, reqId: int, *args, **kwargs):
        """Handle errors from TWS API.

        Supports both legacy and modern ibapi error signatures.
        Bug #43 FIX: Enhanced error classification and handling.
        Bug #56 FIX: Parse and store advancedOrderRejectJson for comprehensive debugging.

        Args:
            reqId: Request ID that caused the error
            *args: Positional arguments supplied by ibapi (varies by version)
            **kwargs: Optional keyword args supplied by ibapi
        """
        import logging
        from contextlib import suppress

        logger = logging.getLogger(__name__)

        error_time: float
        error_code: int
        error_string: str
        advanced_order_reject_json: str

        if len(args) == 4:
            # ibapi >= 10.19 adds errorTime ahead of errorCode
            error_time, error_code, error_string, advanced_order_reject_json = args
        elif len(args) == 3:
            # Legacy form: errorCode, errorString, advanced JSON
            error_code, error_string, advanced_order_reject_json = args
            error_time = kwargs.pop("errorTime", time.time())
        elif len(args) == 2:
            # Very old form: only errorCode and errorString
            error_code, error_string = args
            advanced_order_reject_json = kwargs.pop("advancedOrderRejectJson", "")
            error_time = kwargs.pop("errorTime", time.time())
        elif not args and {"errorCode", "errorString"}.issubset(kwargs.keys()):
            # Some ibapi builds (and certain mocks/tests) invoke the callback exclusively
            # with keyword arguments.  Accept that signature to preserve backwards
            # compatibility and to keep defensive coverage intact.
            error_code = kwargs.pop("errorCode")
            error_string = kwargs.pop("errorString")
            advanced_order_reject_json = kwargs.pop("advancedOrderRejectJson", "")
            error_time = kwargs.pop("errorTime", time.time())
        else:
            logger.error(
                "Unexpected TWS error signature: reqId=%s args=%r kwargs=%r",
                reqId,
                args,
                kwargs,
            )
            return

        # Determine error classification
        error_level = self._ERROR_CLASSIFICATIONS.get(error_code, "error")

        # Record metric
        with suppress(Exception):
            record(f"ibkr.error.{error_code}")
            record(f"ibkr.error_level.{error_level}")

        # Bug #58 FIX: Use %-formatting for lazy evaluation (logging standards)
        log_msg = "TWS Error [%s] Code=%d, ReqId=%d: %s"

        if error_level == "info":
            logger.info(log_msg, error_level.upper(), error_code, reqId, error_string)
        elif error_level == "warning":
            logger.warning(log_msg, error_level.upper(), error_code, reqId, error_string)
        elif error_level == "critical":
            logger.critical(log_msg, error_level.upper(), error_code, reqId, error_string)
        else:  # error
            logger.error(log_msg, error_level.upper(), error_code, reqId, error_string)

        # Bug #56 FIX: Parse and store advanced order rejection JSON
        if advanced_order_reject_json and advanced_order_reject_json.strip():
            rejection_data = self._parse_rejection_json(advanced_order_reject_json)

            # Create structured rejection record
            rejection = OrderRejectionDetails(
                request_id=reqId,
                error_code=error_code,
                error_message=str(error_string),
                timestamp=error_time if error_time else time.time(),
                rejection_data=rejection_data,
                raw_json=advanced_order_reject_json,
            )

            # Store for later retrieval
            self.rejection_details.append(rejection)

            # Log structured rejection data with proper formatting
            if rejection_data:
                # Extract key fields for logging
                reason = rejection_data.get("reason", "unknown")
                order_id = rejection_data.get("orderId", "N/A")
                logger.error(
                    "Order rejection: reqId=%d, orderId=%s, reason=%s, details=%s",
                    reqId,
                    order_id,
                    reason,
                    rejection_data,
                )
            else:
                # Fallback if parsing failed
                logger.error("Order rejection (unparsed): reqId=%d, json=%s", reqId, advanced_order_reject_json)

        # Only append fatal errors to the errors list
        if error_level in ("error", "critical"):
            self.errors.append((error_code, str(error_string)))

    def _parse_rejection_json(self, json_str: str) -> dict[str, Any]:
        """Parse advanced order rejection JSON safely.

        Bug #56 FIX: Safe JSON parsing with error handling.

        Args:
            json_str: JSON string from IB API

        Returns:
            Parsed dictionary or empty dict on failure
        """
        if not json_str or not json_str.strip():
            return {}

        try:
            data = json.loads(json_str)
            if isinstance(data, dict):
                return data
            else:
                # JSON parsed but not a dict (unusual)
                _error_handler.safe_exception("Rejection JSON parsed to non-dict type: %s", type(data).__name__)
                return {"raw_value": data}
        except json.JSONDecodeError as e:
            # Log parse failure but don't crash
            _error_handler.safe_exception(
                "Failed to parse rejection JSON: %s (error: %s)", json_str[:200], str(e)  # Truncate for safety
            )
            return {}
        except Exception:
            # Unexpected error during parsing
            _error_handler.safe_exception("Unexpected error parsing rejection JSON")
            return {}

    def get_rejection_details(self, request_id: int | None = None) -> list[OrderRejectionDetails]:
        """Retrieve stored order rejection details.

        Bug #56 FIX: Public API to access advanced rejection information.

        Args:
            request_id: Optional filter by request ID (None returns all)

        Returns:
            List of OrderRejectionDetails matching the filter
        """
        if request_id is None:
            return list(self.rejection_details)
        else:
            return [r for r in self.rejection_details if r.request_id == request_id]

    def nextValidId(self, orderId):
        self.ready.set()


class _HistApp(_BaseApp):
    def __init__(self):
        super().__init__()
        self._bars: dict[int, list[tuple[str, float, float, float, float, int]]] = {}
        self._done: dict[int, threading.Event] = {}
        self._lock = threading.Lock()
        self._results: dict[int, list[tuple[str, float, float, float, float, int]]] = {}
        self._thread: threading.Thread | None = None  # Track the run thread

    # ---- request bookkeeping -------------------------------------------------
    def register_request(self, req_id: int) -> threading.Event:
        evt = threading.Event()
        with self._lock:
            self._done[req_id] = evt
            # ensure containers exist so data handlers can append without key checks
            self._bars.setdefault(req_id, [])
        return evt

    def wait_for(self, req_id: int, timeout: float) -> bool:
        with self._lock:
            evt = self._done.get(req_id)
        if evt is None:
            return False
        return evt.wait(timeout)

    # ibapi BarData: date, open, high, low, close, volume, average, barCount
    def historicalData(self, reqId, bar):
        with self._lock:
            if reqId in self._results:
                # Late-arriving data after completion; escalate to surface potential pacing drift.
                logger.warning("TWS received late historical bar for req %s after completion", reqId)
                self._results[reqId].append(
                    (str(bar.date), float(bar.open), float(bar.high), float(bar.low), float(bar.close), int(bar.volume))
                )
                return
            self._bars.setdefault(reqId, []).append(
                (str(bar.date), float(bar.open), float(bar.high), float(bar.low), float(bar.close), int(bar.volume))
            )

    def historicalDataEnd(self, reqId, start, end):
        with self._lock:
            bars = list(self._bars.pop(reqId, []))
            self._results[reqId] = bars
            evt = self._done.get(reqId)
            if evt is None:
                evt = threading.Event()
                self._done[reqId] = evt
            evt.set()

    def take_bars(self, reqId: int) -> list[tuple[str, float, float, float, float, int]]:
        with self._lock:
            bars = self._results.pop(reqId) if reqId in self._results else list(self._bars.pop(reqId, []))
            done_evt = self._done.get(reqId)
            if done_evt is not None and not done_evt.is_set():
                done_evt.set()
            return list(bars)

    def cleanup(self) -> None:
        """Properly disconnect and clean up the thread."""
        self.disconnect()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            if self._thread.is_alive():
                logger.warning("TWS thread failed to terminate gracefully during cleanup")

    def release(self, reqId: int) -> None:
        with self._lock:
            self._bars.pop(reqId, None)
            self._results.pop(reqId, None)
            done_evt = self._done.pop(reqId, None)
            if done_evt is not None and not done_evt.is_set():
                done_evt.set()


def _stock_contract(symbol: str) -> Contract:
    c = Contract()
    c.symbol = symbol
    c.secType = "STK"
    c.exchange = "SMART"
    c.currency = "USD"
    return c


class RealTwsFetcher:
    """Real TWS fetcher: stable handshake + minimal daily-bars features with LRU cache and dynamic TTL."""

    def __init__(self, cfg: TwsConfig | None = None):
        self.cfg = cfg or cfg_from_env()
        self._req_id = 1000
        # LRU: maps symbol -> (last_access_ts, bars)
        self._daily_cache: OrderedDict[str, tuple[float, list[tuple[str, float, float, float, float, int]]]] = (
            OrderedDict()
        )
        self._last_ok: float = 0.0
        self._last_error: str | None = None
        self._request_window: deque[float] = deque()
        self._last_request_ts: float = 0.0
        self._last_latency: float = 0.0
        self._fresh_requests: int = 0
        self._global_rate_limiter = RateLimiter(
            max_calls=int(self.cfg.global_rate_max_requests),
            interval_sec=float(self.cfg.global_rate_interval_sec),
            name="tws-global",
        )
        # Thread-safe pacing metrics (Issue #3 fix: race condition)
        self._rate_metrics_lock = threading.Lock()
        self._rate_wait_total: float = 0.0
        self._rate_wait_events: deque[tuple[float, float]] = deque()
        self._rate_wait_last: float = 0.0
        self._rate_warn_threshold = max(0.5, float(self.cfg.global_rate_interval_sec) * 0.1)
        self._rate_warn_interval = max(30.0, float(self.cfg.global_rate_interval_sec))
        self._rate_warn_last_ts = 0.0

    # ---------- time / ttl helpers ----------
    def _current_ttl(self) -> float:
        if not self.cfg.dynamic_ttl:
            return self.cfg.daily_ttl_sec
        # naive local time check; good enough for our use
        t = time.localtime()
        # treat 09:00–15:59 as "market hours"; tune via env if needed
        intraday = 9 <= t.tm_hour < 16
        return self.cfg.intraday_ttl_sec if intraday else self.cfg.daily_ttl_sec

    # ---------- pacing helpers ----------
    def _pace_request(self) -> None:
        now = time.time()
        interval = max(0.0, float(self.cfg.pacing_interval_sec))
        max_reqs = max(0, int(self.cfg.pacing_max_requests))
        min_delay = max(0.0, float(self.cfg.pacing_min_delay_sec))

        # respect minimum spacing between consecutive requests
        if self._last_request_ts and min_delay > 0:
            elapsed = now - self._last_request_ts
            if elapsed < min_delay:
                sleep_for = min_delay - elapsed
                logger.debug("TWS pacing: sleeping %.3fs to respect min delay", sleep_for)
                time.sleep(sleep_for)
                now = time.time()

        if interval > 0 and max_reqs > 0:
            window = self._request_window
            while window and (now - window[0]) > interval:
                window.popleft()
            if len(window) >= max_reqs:
                sleep_for = interval - (now - window[0]) + 0.01
                if sleep_for > 0:
                    logger.debug("TWS pacing: sleeping %.3fs (requests=%d limit=%d)", sleep_for, len(window), max_reqs)
                    time.sleep(sleep_for)
                    now = time.time()
                    while window and (now - window[0]) > interval:
                        window.popleft()

        if self._global_rate_limiter.enabled:
            waited = self._global_rate_limiter.acquire()
            # Thread-safe metric updates (Issue #3 fix)
            with self._rate_metrics_lock:
                self._rate_wait_last = waited
                if waited:
                    now = time.time()
                    self._rate_wait_events.append((now, waited))
                    self._rate_wait_total += waited
                    cutoff = now - float(self.cfg.global_rate_interval_sec)
                    while self._rate_wait_events and self._rate_wait_events[0][0] < cutoff:
                        _, duration = self._rate_wait_events.popleft()
                        self._rate_wait_total = max(0.0, self._rate_wait_total - duration)
                    # Check warning threshold inside lock to ensure consistent metrics
                    should_warn = (
                        waited >= self._rate_warn_threshold
                        and now - self._rate_warn_last_ts >= self._rate_warn_interval
                    )
                    if should_warn:
                        # Cache values for logging outside lock
                        total_wait = self._rate_wait_total
                        interval = self.cfg.global_rate_interval_sec
                        max_requests = self.cfg.global_rate_max_requests
                        self._rate_warn_last_ts = now
            # Log warning outside lock to avoid holding it during I/O
            if waited and should_warn:
                logger.warning(
                    "TWS pacing: global limiter slept %.3fs (total %.3fs / %.1fs, limit=%d)",
                    waited,
                    total_wait,
                    interval,
                    max_requests,
                )
        else:
            with self._rate_metrics_lock:
                self._rate_wait_last = 0.0

        self._last_request_ts = time.time()
        self._request_window.append(self._last_request_ts)
        self._fresh_requests += 1

    # ---------- connectivity ----------
    def _connect(self) -> _HistApp:
        record("ibkr.connect.attempts")
        with timer("ibkr.handshake.ms"):
            app = _HistApp()
            thread = None
            try:
                app.connect(self.cfg.host, self.cfg.port, clientId=self.cfg.client_id)
                # Use non-daemon thread to ensure proper cleanup
                thread = threading.Thread(target=app.run, name="tws-run", daemon=False)
                thread.start()

                if not app.ready.wait(self.cfg.handshake_timeout):
                    # Handshake timeout - clean up thread properly
                    logger.debug("TWS handshake timeout, disconnecting and cleaning up thread")
                    app.disconnect()

                    # Wait for thread to terminate with timeout
                    if thread and thread.is_alive():
                        thread.join(timeout=1.0)
                        if thread.is_alive():
                            logger.warning("TWS thread failed to terminate gracefully after disconnect")

                    self._last_error = (
                        f"handshake timeout host={self.cfg.host} port={self.cfg.port} id={self.cfg.client_id}"
                    )
                    raise TimeoutError(self._last_error)

                # Store thread reference for cleanup in app
                app._thread = thread
                self._last_ok = time.time()
                self._last_error = None

            except Exception as e:
                # CRITICAL FIX: Always update _last_error with current exception info
                # This prevents stale error state from previous failures
                error_type = type(e).__name__
                error_msg = str(e)
                self._last_error = (
                    f"{error_type}: {error_msg} " f"(host={self.cfg.host} port={self.cfg.port} id={self.cfg.client_id})"
                )

                # Clean up connection and thread on any exception
                logger.debug(f"TWS connection failed: {self._last_error}, cleaning up")
                with suppress(Exception):
                    app.disconnect()

                # Ensure thread is properly terminated
                if thread and thread.is_alive():
                    thread.join(timeout=1.0)
                    if thread.is_alive():
                        logger.warning("TWS thread failed to terminate after exception")

                record("ibkr.connect.fail")
                raise

        record("ibkr.connect.ok")
        return app

    def handshake_test(self) -> dict[str, Any]:
        app = self._connect()
        try:
            return {
                "host": self.cfg.host,
                "port": self.cfg.port,
                "client_id": self.cfg.client_id,
                "handshake": "ok",
                "errors": app.errors,
                "last_ok": self._last_ok,
            }
        finally:
            app.cleanup()

    # ---------- daily bars (LRU + dynamic TTL) ----------
    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _prune_daily_cache(self) -> None:
        limit = max(1, int(self.cfg.daily_max_entries))
        while len(self._daily_cache) > limit:
            self._daily_cache.popitem(last=False)  # pop LRU

    def _get_cached(
        self, symbol: str, now: float, allow_stale: bool
    ) -> list[tuple[str, float, float, float, float, int]] | None:
        ent = self._daily_cache.get(symbol)
        if not ent:
            return None
        ts, bars = ent
        age = now - ts
        ttl = self._current_ttl()
        if age < ttl or (allow_stale and age < self.cfg.stale_ok_sec):
            # refresh access timestamp and move to MRU
            self._daily_cache[symbol] = (now, bars)
            self._daily_cache.move_to_end(symbol, last=True)
            return bars
        return None

    def _fetch_daily(
        self, app: _HistApp, symbol: str, days: int = 30
    ) -> list[tuple[str, float, float, float, float, int]]:
        now = time.time()
        cached = self._get_cached(symbol, now, allow_stale=False)
        if cached is not None:
            return cached

        req_id = self._next_id()
        wait_evt = app.register_request(req_id)
        app.reqHistoricalData(
            req_id,
            _stock_contract(symbol),
            endDateTime="",
            durationStr=f"{days} D",
            barSizeSetting="1 day",
            whatToShow="TRADES",
            useRTH=1,
            formatDate=1,
            keepUpToDate=False,
            chartOptions=[],
        )

        try:
            if not wait_evt.wait(self.cfg.hist_timeout):
                # try stale fallback
                stale = self._get_cached(symbol, now, allow_stale=True)
                if stale is not None:
                    return stale
                raise TimeoutError(f"historicalData timeout for {symbol}")

            bars = app.take_bars(req_id)
        finally:
            # Always release per-request registries to avoid unbounded growth in long-lived sessions.
            app.release(req_id)

        # store/update LRU
        self._daily_cache[symbol] = (now, bars)
        self._daily_cache.move_to_end(symbol, last=True)
        self._prune_daily_cache()
        return bars

    # ---------- public API ----------
    def features_for_symbols(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        syms = list(dict.fromkeys(symbols))
        ref = (self.cfg.ref_symbol or os.getenv("SENGOKU_TWS_REF", "SPY")) or "SPY"

        include_ref = False
        if ref:
            if ref in syms:
                include_ref = True
            elif getattr(self.cfg, "global_rate_max_requests", 0) == 0:
                # Force reference fetch in offline/test configurations where pacing is disabled
                include_ref = True

        filtered_syms = [s for s in syms if s != ref]
        all_syms = ([ref] + filtered_syms) if include_ref and ref else list(dict.fromkeys(syms))

        app = self._connect()
        try:
            daily: dict[str, list[tuple[str, float, float, float, float, int]]] = {}
            fresh_requests_start = self._fresh_requests
            for s in all_syms:
                self._pace_request()
                started = time.perf_counter()
                try:
                    daily[s] = self._fetch_daily(app, s, days=30)
                    self._last_latency = time.perf_counter() - started
                except Exception as exc:
                    logger.warning("TWS daily fetch failed for %s: %s", s, exc)
                    # last-ditch stale fallback
                    fallback = self._get_cached(s, time.time(), allow_stale=True)
                    daily[s] = fallback if fallback is not None else []
                    if self.cfg.pacing_error_delay_sec > 0:
                        logger.debug("TWS pacing: sleeping %.3fs after error", self.cfg.pacing_error_delay_sec)
                        time.sleep(self.cfg.pacing_error_delay_sec)
            fresh_requests = self._fresh_requests - fresh_requests_start
            if fresh_requests:
                logger.info(
                    "TWS pacing metrics: fresh_requests=%d window=%d interval=%.1fs last_latency=%.3fs",
                    fresh_requests,
                    len(self._request_window),
                    self.cfg.pacing_interval_sec,
                    self._last_latency,
                )
            # Bug #4 FIX: Compute ref return only if ref was fetched
            # If ref wasn't in the requested symbols, rs_strength will default to 0.0
            ref_bars = daily.get(ref, [])
            ref_close = ref_bars[-1][4] if ref_bars else None
            ref_ago = ref_bars[-21][4] if len(ref_bars) >= 21 else None
            ref_ret20 = (ref_close / ref_ago - 1.0) if (ref_close and ref_ago and ref_ago != 0) else 0.0

            out: dict[str, dict[str, Any]] = {}
            for s in syms:
                bars = daily.get(s, [])
                closes = [b[4] for b in bars if b]
                if not closes:
                    out[s] = {
                        "last": 0.0,
                        "dma20": 0.0,
                        "support": 0.0,
                        "resistance": 0.0,
                        "rvol": 1.0,
                        "rs_strength": 0.0,
                        "vwap_diff": 0.0,
                    }
                    continue

                last = closes[-1]
                window = closes[-20:] if len(closes) >= 20 else closes
                dma20 = sum(window) / len(window)
                support = min(window)
                resistance = max(window)

                ago = closes[-21] if len(closes) >= 21 else (closes[0] if closes else last)
                sym_ret20 = (last / ago - 1.0) if (ago and ago != 0) else 0.0
                rs_strength = sym_ret20 - ref_ret20

                base_features = {
                    "last": float(last),
                    "dma20": float(dma20),
                    "support": float(support),
                    "resistance": float(resistance),
                    "rvol": 1.0,
                    "rs_strength": float(rs_strength),
                    "vwap_diff": 0.0,
                }
                out[s] = dict(base_features)
                out[s]["bundles"] = {"1d": dict(base_features)}

            # Filter results so only explicitly requested symbols are returned to the caller.
            # Reference symbol data remains cached internally but is not exposed unless requested.
            return {symbol: out[symbol] for symbol in syms if symbol in out}
        finally:
            app.cleanup()

    # legacy callable form
    def __call__(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        return self.features_for_symbols(symbols)

    def pacing_metrics(self) -> dict[str, Any]:
        # Thread-safe metric reads (Issue #3 fix)
        with self._rate_metrics_lock:
            # Capture snapshot of protected metrics
            rate_wait_last = self._rate_wait_last
            rate_wait_total = self._rate_wait_total

        return {
            "requests_in_window": len(self._request_window),
            "window_interval_sec": self.cfg.pacing_interval_sec,
            "last_request_latency_sec": self._last_latency,
            "total_requests": self._fresh_requests,
            "global_rate_max_requests": self.cfg.global_rate_max_requests,
            "global_rate_interval_sec": self.cfg.global_rate_interval_sec,
            "global_rate_last_wait_sec": rate_wait_last,
            "global_rate_total_wait_sec": rate_wait_total,
            "global_rate_wait_ratio": (
                (rate_wait_total / self.cfg.global_rate_interval_sec) if self.cfg.global_rate_interval_sec else 0.0
            ),
        }

    # ---------- diagnostics helpers ----------
    def daily_cache_len(self) -> int:
        """Return the current number of cached daily-bar entries."""

        return len(self._daily_cache)

    def last_ok_timestamp(self) -> float:
        """Expose the last successful handshake/fetch timestamp (epoch seconds)."""

        return self._last_ok

    def last_error_message(self) -> str | None:
        """Return the last recorded error message (if any)."""

        return self._last_error


# Back-compat alias expected by CLI
RealTwsFetcherConfig = TwsConfig
