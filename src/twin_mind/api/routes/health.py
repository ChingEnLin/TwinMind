from fastapi import APIRouter, Response

from twin_mind.config import settings

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(response: Response) -> dict:
    ready = bool(settings.ANTHROPIC_API_KEY)
    if not ready:
        response.status_code = 503
        return {"status": "not_ready", "reason": "ANTHROPIC_API_KEY not configured"}
    return {"status": "ok"}
