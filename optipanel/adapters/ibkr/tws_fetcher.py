from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple

# ibapi is installed in your venv (9.81.1.post1)
from ibapi.client import EClient
from ibapi.wrapper import EWrapper


@dataclass(frozen=True)
class TwsConfig:
    host: str = os.getenv("SENGOKU_TWS_HOST", "127.0.0.1")
    port: int = int(os.getenv("SENGOKU_TWS_PORT", "7496"))
    client_id: int = int(os.getenv("SENGOKU_TWS_CLIENT_ID", "107"))
    handshake_timeout: float = float(os.getenv("SENGOKU_TWS_HANDSHAKE", "7.0"))


def cfg_from_env() -> TwsConfig:
    # Read env on each call so shell changes are respected
    return TwsConfig(
        host=os.getenv("SENGOKU_TWS_HOST", "127.0.0.1"),
        port=int(os.getenv("SENGOKU_TWS_PORT", "7496")),
        client_id=int(os.getenv("SENGOKU_TWS_CLIENT_ID", "107")),
        handshake_timeout=float(os.getenv("SENGOKU_TWS_HANDSHAKE", "7.0")),
    )


class _App(EWrapper, EClient):
    """Minimal client just to perform a clean handshake and allow later requests."""
    def __init__(self) -> None:
        EClient.__init__(self, self)
        self.ready = threading.Event()
        self.errors: list[Tuple[int,str]] = []

    # Non-fatal farm messages (don’t trip the handshake)
    _NON_FATAL = {2104, 2106, 2158}

    def error(self, reqId, code, msg, advancedOrderRejectJson=""):
        if code not in self._NON_FATAL:
            self.errors.append((code, str(msg)))

    def connectAck(self):
        # Some builds require this; we don’t set ready here—wait for nextValidId.
        pass

    def nextValidId(self, orderId):
        self.ready.set()


class RealTwsFetcher:
    """Connects to TWS and (later) fetches raw snapshots. For now we expose a stable handshake."""
    def __init__(self, cfg: TwsConfig | None = None) -> None:
        self.cfg = cfg or cfg_from_env()

    # Exposed for diagnostics
    def handshake_test(self) -> Dict[str, Any]:
        app, thread = self._handshake()
        try:
            return {
                "host": self.cfg.host,
                "port": self.cfg.port,
                "client_id": self.cfg.client_id,
                "handshake": "ok",
                "errors": app.errors,
            }
        finally:
            app.disconnect()

    def _handshake(self) -> Tuple[_App, threading.Thread]:
        app = _App()
        app.connect(self.cfg.host, self.cfg.port, clientId=self.cfg.client_id)
        t = threading.Thread(target=app.run, name="tws-run", daemon=True)
        t.start()

        ok = app.ready.wait(self.cfg.handshake_timeout)
        if not ok:
            app.disconnect()
            raise TimeoutError(
                f"TWS handshake timed out "
                f"(host={self.cfg.host} port={self.cfg.port} id={self.cfg.client_id})."
            )
        return app, t

    # Placeholder; our CLI currently pipes this to a translator. We’ll flesh this out next.
    # We still raise until we implement data requests so callers don’t silently assume features exist.
    def __call__(self, symbols: List[str]) -> List[Dict[str, Any]]:
        # For now do only the handshake to verify connection, then explicitly tell the caller
        # that live fetch is not implemented yet in this minimal scaffold.
        app, t = self._handshake()
        try:
            raise NotImplementedError("Live raw snapshot fetch not implemented yet in RealTwsFetcher.")
        finally:
            app.disconnect()
