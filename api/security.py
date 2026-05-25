"""
security.py
-----------
Simple in-memory IP-based rate limiter. No external dependencies.
Single-instance only — state resets on process restart (acceptable for Railway).
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request


class RateLimiter:
    """
    Callable FastAPI dependency that enforces a sliding-window rate limit per IP.

    Usage:
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        @router.post("/upload", dependencies=[Depends(limiter)])
    """

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._store: dict[str, list[float]] = defaultdict(list)

    def __call__(self, request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        # Evict timestamps outside the current window
        self._store[ip] = [t for t in self._store[ip] if now - t < self.window_seconds]
        if len(self._store[ip]) >= self.max_requests:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Rate limit exceeded: max {self.max_requests} requests "
                    f"per {self.window_seconds}s from the same IP. Try again later."
                ),
            )
        self._store[ip].append(now)


# One limiter instance per endpoint so limits are tracked independently
upload_rate_limit = RateLimiter(max_requests=10, window_seconds=60)
job_rate_limit = RateLimiter(max_requests=5, window_seconds=60)
