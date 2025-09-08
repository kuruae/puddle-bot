# Puddle API Client

Centralized asynchronous client used across the bot to talk to `https://puddle.farm/api`.

## Goals

* Reuse a single `aiohttp` session per context
* Provide consistent timeouts & retries
* Offer optional polite rate limiting
* Present a slim, typed-ish surface of endpoint helpers
* Normalize errors behind a tiny exception hierarchy

## Classes

### PuddleApiClient
Main entry point. Use it via an async context manager:

```python
from api_client import PuddleApiClient

async with PuddleApiClient() as api:
    player = await api.get_player("123456789")
```

Constructor args:
* `base_url: str` (default `https://puddle.farm/api`)
* `timeout: float` total request timeout (seconds)
* `retry_policy: RetryPolicy | None` retry settings
* `rate_limiter: SimpleRateLimiter | None` optional token bucket
* `session: aiohttp.ClientSession | None` external session injection

### RetryPolicy
Configurable retries with exponential backoff.
* `attempts` (default 3 total attempts)
* `backoff_base` (seconds, default 0.5)
* `backoff_factor` (exponential multiplier, default 2.0)
* `retry_statuses` (HTTP codes considered transient)

### SimpleRateLimiter
Minimal token bucket.
* `capacity` tokens per interval
* `interval` seconds

Use if you want to pace bursts:
```python
from api_client import SimpleRateLimiter, PuddleApiClient

limiter = SimpleRateLimiter(capacity=8, interval=1.0)
async with PuddleApiClient(rate_limiter=limiter) as api:
    await api.get_top()
```

## Endpoint Helpers

| Method | Description |
|--------|-------------|
| `get_player(player_id)` | Player profile (ratings, global top info) |
| `get_player_history(player_id, char_short)` | Character-specific match history |
| `get_top()` | Global leaderboard |
| `get_top_char(char_short)` | Leaderboard for one character |
| `get_popularity()` | Character popularity distribution |
| `health()` | Returns True if `/health` responds with OK |

## Health Semantics

`health()` performs a GET on `/health` and returns True iff the response is a 2xx and body equals `OK` (case‑sensitive). Any API exception is swallowed and returns False.

## Error Handling

All API-originated problems inherit from `ApiError`:

* `ApiResponseError(status, body)` – Non‑2xx final HTTP status
* `ApiDecodeError(raw)` – Invalid / unexpected JSON body when JSON expected

Handle broadly:
```python
from api_client import PuddleApiClient, ApiError

async with PuddleApiClient() as api:
    try:
        data = await api.get_top()
    except ApiError as e:
        # log/notify/fallback
        print("API failure", e)
```

Network layer exceptions (`aiohttp.ClientError`, `asyncio.TimeoutError`) propagate if retries are exhausted.

## Adding a New Endpoint

Inside `PuddleApiClient`:
```python
async def get_new_resource(self, some_id: str):
    return await self._request("GET", f"new_resource/{some_id}")
```

Refactor call sites to use the helper—avoid direct `aiohttp` usage elsewhere.

## Design Notes

* `_request` is intentionally minimal: it does not currently log; caller or future middleware can wrap it.
* Rate limiting is coarse (full refill each interval). Adequate for modest bots; replace with a more granular windowed limiter if traffic grows.
* The client is stateless beyond its session & rate limiter references; safe to recreate per task group.

## Future Enhancements

* Structured logging hooks (timings, status, payload size)
* Automatic circuit breaking on repeated failures
* Optional in‑memory caching for high fan‑out endpoints (`top`, `popularity`)
* Typed response models (`pydantic` / `dataclasses`) if stronger guarantees are needed
