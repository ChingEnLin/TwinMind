import time
import uuid
from collections import deque
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from twin_mind.config import settings


class RateLimiter:
    """In-memory per-IP rate limiter: 10/min and 100/day."""

    def __init__(self, per_minute: int = 10, per_day: int = 100) -> None:
        self.per_minute = per_minute
        self.per_day = per_day
        self._minute: dict[str, deque[float]] = {}
        self._day: dict[str, deque[float]] = {}

    def check(self, ip: str) -> tuple[bool, int]:
        now = time.time()
        mq = self._minute.setdefault(ip, deque())
        dq = self._day.setdefault(ip, deque())
        while mq and now - mq[0] > 60:
            mq.popleft()
        while dq and now - dq[0] > 86400:
            dq.popleft()
        if len(mq) >= self.per_minute:
            return False, int(60 - (now - mq[0]))
        if len(dq) >= self.per_day:
            return False, int(86400 - (now - dq[0]))
        mq.append(now)
        dq.append(now)
        return True, max(0, self.per_minute - len(mq))


rate_limiter = RateLimiter()


def install_middleware(app: FastAPI) -> None:
    # ALLOWED_ORIGIN may be a single URL or a comma-separated list. The list
    # form lets one deploy serve both the production portfolio and Vercel
    # preview deployments (which get rotating URLs) without redeploying the
    # backend.
    origins = [o.strip() for o in settings.ALLOWED_ORIGIN.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    @app.middleware("http")
    async def request_id_and_rate_limit(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = (
            request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex[:12]}"
        )

        if request.url.path.startswith("/v1/chat"):
            ip = request.client.host if request.client else "unknown"
            ok, remaining = rate_limiter.check(ip)
            if not ok:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMITED",
                            "message": "Too many requests.",
                            "retry_after": remaining,
                        }
                    },
                    headers={"Retry-After": str(remaining)},
                )

        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response
