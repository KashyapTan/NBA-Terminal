"""Keep public NBA enrichment offline in ESPN/API integration tests.

The enrichment's own test module mocks its individual network boundaries instead.
"""

import pytest

from nba_terminal.services import fantasy_nba


@pytest.fixture(autouse=True)
def offline_nba_enrichment(request, monkeypatch):
    if request.node.path.name == "test_fantasy_nba.py":
        return
    monkeypatch.setattr(
        fantasy_nba,
        "load",
        lambda *args, **kwargs: {
            "rates": [],
            "schedule": None,
            "rates_status": "unavailable",
            "schedule_status": "not_needed",
        },
    )
    monkeypatch.setattr(
        fantasy_nba, "load_prior_rates", lambda *args: {"prior_rates": [], "prior_rates_status": "unavailable"}
    )

    monkeypatch.setattr(fantasy_nba, "fetch_identities", lambda year: [])
