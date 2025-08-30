"""Async Puddle API client service.

Centralizes HTTP concerns (timeouts, retries, error handling, logging,
future rate limiting) behind a tiny abstraction so call sites stay
focused on domain logic.

Design goals:
 - Minimal churn: existing code can wrap this without large refactors.
 - Safe defaults: short timeout, limited retries on transient errors.
 - Extensible: easy to plug in rate limiting / instrumentation later.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
import asyncio
import time
import json
import aiohttp

DEFAULT_BASE_URL = "https://puddle.farm/api"


class ApiError(Exception):
	"""Base API error."""


class ApiResponseError(ApiError):
	def __init__(self, status: int, body: str | None, message: str = "HTTP error"):
		super().__init__(f"{message} (status={status})")
		self.status = status
		self.body = body

	def __repr__(self) -> str:  # pragma: no cover - convenience
		return f"ApiResponseError(status={self.status}, body={self.body!r})"


class ApiDecodeError(ApiError):
	def __init__(self, raw: str):
		super().__init__("Invalid JSON response")
		self.raw = raw


@dataclass(slots=True)
class RetryPolicy:
	attempts: int = 3              # total attempts (initial + retries)
	backoff_base: float = 0.5      # seconds
	backoff_factor: float = 2.0    # exponential factor
	retry_statuses: tuple[int, ...] = (500, 502, 503, 504)

	def compute_sleep(self, attempt: int) -> float:
		# attempt is 1-based (1 = first retry after initial)
		return self.backoff_base * (self.backoff_factor ** (attempt - 1))


class SimpleRateLimiter:
	"""Very small token bucket rate limiter.

	Not strictly required now; provides a hook for future politeness.
	capacity tokens per interval seconds.
	"""

	def __init__(self, capacity: int = 5, interval: float = 1.0):
		self.capacity = capacity
		self.interval = interval
		self._tokens = capacity
		self._last = time.monotonic()
		self._lock = asyncio.Lock()

	async def acquire(self):
		"""Acquire a single token, waiting for the next interval if bucket empty."""
		async with self._lock:
			now = time.monotonic()
			elapsed = now - self._last
			if elapsed >= self.interval:
				# Refill full bucket each interval (simplest model)
				self._tokens = self.capacity
				self._last = now
			if self._tokens == 0:
				# Wait until next interval
				to_sleep = self.interval - elapsed if elapsed < self.interval else self.interval
				await asyncio.sleep(max(0.01, to_sleep))
				return await self.acquire()  # recurse after sleep
			self._tokens -= 1


class PuddleApiClient:
	def __init__(
		self,
		base_url: str = DEFAULT_BASE_URL,
		timeout: float = 5.0,
		retry_policy: RetryPolicy | None = None,
		rate_limiter: Optional[SimpleRateLimiter] = None,
		session: aiohttp.ClientSession | None = None,
	):
		"""Create a new API client.

		Args:
			base_url: Root of the puddle API (no trailing slash required).
			timeout: Total request timeout in seconds.
			retry_policy: Optional retry configuration (defaults provided if None).
			rate_limiter: Optional rate limiter (token bucket) for politeness.
			session: Optional externally managed aiohttp session (if supplied, client won't close it).
		"""
		self.base_url = base_url.rstrip("/")
		self._timeout = aiohttp.ClientTimeout(total=timeout)
		self._retry = retry_policy or RetryPolicy()
		self._rate_limiter = rate_limiter
		self._session_external = session is not None
		self._session = session

	# ---------------- Context management ----------------
	async def __aenter__(self) -> "PuddleApiClient":
		"""Enter async context, creating an internal ClientSession if needed."""
		if self._session is None:
			self._session = aiohttp.ClientSession(timeout=self._timeout)
		return self

	async def __aexit__(self, exc_type, exc, tb):
		"""Exit async context, closing internal session (if owned)."""
		if not self._session_external and self._session:
			await self._session.close()
		self._session = None

	# ---------------- Low-level request helper ----------------
	async def _request(self, method: str, path: str) -> Any | None:
		"""Low-level JSON request helper.

		Handles retries, rate limiting, error classification and JSON decoding.
		Returns parsed JSON (dict/list/etc.) or None if empty body.
		Raises:
			ApiResponseError: For non-success HTTP status (after retry policy exhausted).
			ApiDecodeError: If body cannot be decoded as JSON.
			aiohttp.ClientError / asyncio.TimeoutError: For network issues after retries.
		"""
		if self._session is None:
			raise RuntimeError("ClientSession not initialized - use 'async with' or call __aenter__ explicitly")

		url = f"{self.base_url}/{path.lstrip('/')}"
		attempt = 0
		last_err: Exception | None = None

		while attempt < self._retry.attempts:
			attempt += 1
			if self._rate_limiter:
				await self._rate_limiter.acquire()
			try:
				async with self._session.request(method, url) as resp:
					status = resp.status
					if status >= 400:
						# Retry on configured statuses
						if status in self._retry.retry_statuses and attempt < self._retry.attempts:
							await asyncio.sleep(self._retry.compute_sleep(attempt))
							continue
						body_text = None
						try:
							body_text = await resp.text()
						except Exception as read_err:  # capture but ignore (logging placeholder)
							body_text = f"<unreadable body: {read_err}>"
						raise ApiResponseError(status, body_text)
					try:
						return await resp.json()
					except (aiohttp.ContentTypeError, json.JSONDecodeError) as decode_err:
						raise ApiDecodeError(await resp.text()) from decode_err
			except (aiohttp.ClientError, asyncio.TimeoutError) as net_err:
				last_err = net_err
				if attempt < self._retry.attempts:
					await asyncio.sleep(self._retry.compute_sleep(attempt))
				else:
					raise
		if last_err:
			raise last_err
		return None

	# ---------------- High-level endpoint helpers ----------------
	async def get_player(self, player_id: str) -> Any | None:
		"""Fetch a player's profile (ratings, metadata)."""
		return await self._request("GET", f"player/{player_id}")

	async def get_player_history(self, player_id: str, char_short: str) -> Any | None:
		"""Fetch match history for a specific player + character."""
		return await self._request("GET", f"player/{player_id}/{char_short}/history")

	async def get_top(self) -> Any | None:
		"""Fetch global top leaderboard."""
		return await self._request("GET", "top")

	async def get_top_char(self, char_short: str) -> Any | None:
		"""Fetch top leaderboard for a specific character short code."""
		return await self._request("GET", f"top_char/{char_short}")

	async def get_popularity(self) -> Any | None:
		"""Fetch character popularity distribution data."""
		return await self._request("GET", "popularity")

	async def health(self) -> bool:
		"""Return True if `/health` returns a 2xx with body == 'OK'."""
		if self._session is None:
			raise RuntimeError("ClientSession not initialized - use 'async with' or call __aenter__ explicitly")
		url = f"{self.base_url}/health"
		try:
			async with self._session.get(url) as resp:
				if resp.status >= 400:
					return False
				try:
					text = await resp.text()
				except Exception:
					return False
				return text.strip() == "OK"
		except (aiohttp.ClientError, asyncio.TimeoutError, ApiError):
			return False

__all__ = [
	"PuddleApiClient",
	"RetryPolicy",
	"SimpleRateLimiter",
	"ApiError",
	"ApiResponseError",
	"ApiDecodeError",
]
