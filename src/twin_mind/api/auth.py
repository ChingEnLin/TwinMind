from fastapi import Header, HTTPException, status

from twin_mind.config import settings


def require_api_key(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "missing bearer token"}},
        )
    token = authorization.split(" ", 1)[1].strip()
    if token != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "invalid api key"}},
        )
