from nba_api.stats.library.http import NBAStatsHTTP
from requests.adapters import HTTPAdapter

from nba_terminal.services import nba_http


def test_configure_nba_stats_client_installs_rate_limited_session_and_retries(monkeypatch):
    monkeypatch.setattr(nba_http, "_configured", False)
    installed = []
    monkeypatch.setattr(NBAStatsHTTP, "set_session", staticmethod(lambda session: installed.append(session)))
    nba_http.configure_nba_stats_client()

    session = installed[0]
    assert isinstance(session, nba_http.RateLimitedStatsSession)
    assert isinstance(session.get_adapter("https://"), HTTPAdapter)
    retry = session.get_adapter("https://").max_retries
    assert retry.status_forcelist == (429, 502, 503, 504)
    assert retry.total == 2
    assert retry.respect_retry_after_header is True
    assert retry.raise_on_status is False
    session.close()
