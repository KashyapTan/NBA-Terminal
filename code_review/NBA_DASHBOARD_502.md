# NBA dashboard 502 diagnosis and mitigation

## Diagnosis

The FastAPI wrapper in `nba_terminal/webapp.py` previously converted every unexpected service exception into the same HTTP 502, without logging the original exception. The checkout has no running local server on port 8000, so the current user session could not be inspected live. The existing `NBA_WEB_REFACTOR_V3.md` review records the last direct schedule probe: NBA Stats timed out at 10 seconds and NBA's schedule CDN returned HTTP 403. That evidence supports an upstream timeout plus rejected fallback; it does not prove rate limiting.

The dashboard also requested upcoming games and game history concurrently. Both service functions fetched the same season schedule under different cache keys, which doubled schedule traffic on a cold dashboard load.

## Changes

- Add structured exception logging in the API wrapper and upstream response logging with endpoint, HTTP status, content type, and `Retry-After` (without query strings).
- Serialize NBA Stats requests with a one-second minimum interval in the worker thread and retry idempotent GET requests at most twice for 429/502/503/504, honoring `Retry-After`.
- Share a short-lived season schedule cache between upcoming games and game history.
- Coalesce simultaneous misses for any identical cache key.

## Verification and remaining risks

- Mocked tests cover duplicate misses, shared schedule reads, and configured retry policy.
- A live backend was not running during diagnosis. The recorded NBA Stats timeout and CDN 403 must be checked again from the user's local network after deploying this change.
- NBA.com does not publish a stable public request quota for these endpoints; one request per second is a conservative client-side pacing choice, not a documented guarantee.
