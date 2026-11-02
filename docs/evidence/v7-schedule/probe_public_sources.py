import concurrent.futures
import datetime
import json
import pathlib

import requests

root = pathlib.Path(__file__).resolve().parent
root.mkdir(exist_ok=True, parents=True)
urls = {
    "nba-cdn": "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json",
    "nba-cdn-int": "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2Int.json",
    "nba-stats": "https://stats.nba.com/stats/scheduleleaguev2?LeagueID=00&Season=2026-27",
    "upstream-doc": "https://raw.githubusercontent.com/swar/nba_api/master/docs/nba_api/stats/endpoints/scheduleleaguev2.md",
    "upstream-parser": "https://raw.githubusercontent.com/swar/nba_api/master/src/nba_api/stats/endpoints/_parsers/scheduleleaguev2.py",
    "espn-season": "https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/2027?view=proTeamSchedules_wl",
}


def probe(item):
    name, url = item
    r = {
        "url": url,
        "requested_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "timeout_seconds": [3.05, 8],
    }
    try:
        response = requests.get(url, timeout=(3.05, 8))
        r.update(
            status=response.status_code, bytes=len(response.content), content_type=response.headers.get("Content-Type")
        )
        (root / (name + ".response")).write_bytes(response.content)
        try:
            data = response.json()
            league = data.get("leagueSchedule", {})
            r.update(season=league.get("seasonYear"), game_dates=len(league.get("gameDates", [])))
        except ValueError:
            pass
    except requests.RequestException as e:
        r["error"] = str(e)
    return name, r


results = dict(concurrent.futures.ThreadPoolExecutor(max_workers=6).map(probe, urls.items()))
(root / "public-probes.json").write_text(json.dumps(results, indent=2) + "\n")
print(json.dumps(results, indent=2))
