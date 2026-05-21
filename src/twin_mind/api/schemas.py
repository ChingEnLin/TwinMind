from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    session_id: str | None = None


class ErrorBody(BaseModel):
    code: str
    message: str
    retry_after: int | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
