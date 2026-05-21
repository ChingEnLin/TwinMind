from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from twin_mind.api.middleware import install_middleware
from twin_mind.api.routes import chat as chat_route
from twin_mind.api.routes import health as health_route


def create_app() -> FastAPI:
    app = FastAPI(title="TwinMind", version="0.1.0")
    install_middleware(app)

    app.include_router(health_route.router, prefix="/v1")
    app.include_router(chat_route.router, prefix="/v1")

    @app.exception_handler(RequestValidationError)
    async def _bad_request(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Request validation failed.",
                    "details": exc.errors(),
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Preserve `{"error": {...}}` shape when the detail is already structured.
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        code = {401: "UNAUTHORIZED", 429: "RATE_LIMITED", 503: "BUDGET_EXCEEDED"}.get(
            exc.status_code, "INTERNAL"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": code, "message": str(exc.detail)}},
        )

    return app


app = create_app()
