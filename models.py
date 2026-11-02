from typing import Any

from pydantic import BaseModel, Field, ConfigDict


# ============================================================
# LOGIN
# ============================================================

class LoginRequest(BaseModel):
    username: str
    password: str


# ============================================================
# JWT TOKEN RESPONSE
# ============================================================

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ============================================================
# CHAT REQUEST
# ============================================================

class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Message sent to the AI agent.",
    )


# ============================================================
# AGENT ACTION
# ============================================================

class ChatAction(BaseModel):
    action: str

    action_input: Any = None

    observation: str = ""


# ============================================================
# AGENT RESPONSE
# ============================================================

class AgentResponse(BaseModel):

    actions: list[ChatAction] = Field(
        default_factory=list
    )

    final_answer: str = ""


# ============================================================
# CHAT RESPONSE
# ============================================================

class ChatResponse(BaseModel):
    response: AgentResponse


# ============================================================
# SIMPLY.COM OAUTH STATUS
# ============================================================

class SimplyOAuthStatus(BaseModel):

    authenticated: bool

    has_refresh_token: bool

    expires_at: float | None = None

    expires_in: int | None = None

    needs_refresh: bool


# ============================================================
# SIMPLY.COM ACCOUNT RESPONSE
# ============================================================

class SimplyAccountsResponse(BaseModel):

    status: str = "ok"

    accounts: Any


# ============================================================
# SIMPLY.COM ACCOUNT COUNT RESPONSE
# ============================================================

class SimplyAccountCountResponse(BaseModel):

    status: str = "ok"

    result: Any
