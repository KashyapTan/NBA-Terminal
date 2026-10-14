"""Conservative, observable HTTP transport for the unofficial NBA Stats API."""

from __future__ import annotations

import logging
import threading
import time
from urllib.parse import urlsplit

from nba_api.stats.library.http import NBAStatsHTTP
from requests import Response, Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)
MIN_REQUEST_INTERVAL_SECONDS = 1.0
_configure_lock = threading.Lock()
_configured = False


class RateLimitedStatsSession(Session):
    """Serialize Stats requests and leave a small interval between request starts."""

    def __init__(self, minimum_interval: float = MIN_REQUEST_INTERVAL_SECONDS) -> None:
        super().__init__()
        self.minimum_interval = minimum_interval
        self._request_lock = threading.Lock()
        self._last_request_at = 0.0

    def request(self, method: str, url: str, **kwargs) -> Response:
        with self._request_lock:
            delay = self.minimum_interval - (time.monotonic() - self._last_request_at)
            if delay > 0:
                time.sleep(delay)
            self._last_request_at = time.monotonic()
            response = super().request(method, url, **kwargs)
        if response.status_code >= 400 or "json" not in response.headers.get("Content-Type", "").lower():
            endpoint = urlsplit(response.url).path.rsplit("/", 1)[-1]
            logger.warning(
                "NBA Stats upstream response: status=%d endpoint=%s content_type=%s retry_after=%s",
                response.status_code,
                endpoint,
                response.headers.get("Content-Type", "unknown"),
                response.headers.get("Retry-After", "none"),
            )
        return response


def configure_nba_stats_client() -> None:
    """Set one shared rate-limited session with bounded retries for transient failures."""
    global _configured
    if _configured:
        return
    with _configure_lock:
        if _configured:
            return
        retry = Retry(
            total=2,
            connect=2,
            read=1,
            status=2,
            backoff_factor=0.5,
            status_forcelist=(429, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        session = RateLimitedStatsSession()
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        NBAStatsHTTP.set_session(session)
        _configured = True
