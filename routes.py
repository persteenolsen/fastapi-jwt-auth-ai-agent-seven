import time
import uuid
import traceback

from datetime import timedelta

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)

from fastapi.security import OAuth2PasswordRequestForm

from auth import verify_token, create_access_token

from integrations.initial_simply_oauth import run_initial_oauth

from models import (
    LoginRequest,
    TokenResponse,
    ChatRequest,
    ChatResponse,
)

from config import (
    logger,
    FAKE_USERNAME,
    FAKE_PASSWORD,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

from agent import run_agent, llm

from tools.wikipedia import wikipedia_tool


router = APIRouter()


# ============================================================
# LOGIN FOR VUE SPA
# ============================================================

@router.post("/login-spa")
def login(form: OAuth2PasswordRequestForm = Depends()):

    if (
        form.username != FAKE_USERNAME
        or form.password != FAKE_PASSWORD
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = create_access_token(
        {"sub": form.username},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "username": FAKE_USERNAME,
    }


# ============================================================
# OAUTH2 TOKEN FOR SWAGGER
# ============================================================

@router.post("/token", response_model=TokenResponse)
def get_token(form: OAuth2PasswordRequestForm = Depends()):

    if (
        form.username != FAKE_USERNAME
        or form.password != FAKE_PASSWORD
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    access_token = create_access_token(
        {"sub": form.username},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return TokenResponse(
        access_token=access_token,
    )


# ============================================================
# SIMPLY.COM - INITIAL OAUTH AUTHORIZATION
# ============================================================
# 02-11-2026 - This endpoint is for initial Simply.com OAuth authorization.
# Disabled in production for security reasons. Use only in a secure environment.
# @router.post("/simply/oauth/initialize")
async def simply_initial_oauth(
    request: Request,
    user: str = Depends(verify_token),
):
    """
    Run initial Simply.com OAuth authorization.

    Automatically reloads credentials into the
    existing SimplyOAuthManager after authorization.
    """

    try:

        logger.info(
            "User %s started Simply.com initial OAuth.",
            user,
        )

        # ----------------------------------------------------
        # INITIAL AUTHORIZATION
        # ----------------------------------------------------

        await run_initial_oauth()

        # ----------------------------------------------------
        # RELOAD EXISTING OAUTH MANAGER
        # ----------------------------------------------------

        oauth = request.app.state.simply_oauth

        oauth.reload_credentials()

        logger.info(
            "Simply.com OAuth manager updated successfully."
        )

        # ----------------------------------------------------
        # RETURN RESULT
        # ----------------------------------------------------

        return {
            "status": "ok",
            "message": (
                "Simply.com authorization completed "
                "and credentials reloaded successfully."
            ),
            "oauth": oauth.get_token_info(),
        }

    except Exception as e:

        error_id = str(uuid.uuid4())

        logger.exception(
            "Simply.com initial OAuth failed. Error ID: %s",
            error_id,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error_id": error_id,
                "type": type(e).__name__,
                "message": str(e),
            },
        ) from e

    
# ============================================================
# SIMPLY.COM - LIST SUBDOMAINS
# ============================================================

@router.get("/simply/subdomains/{domain}")
async def simply_list_subdomains(
    domain: str,
    request: Request,
    user: str = Depends(verify_token),
):

    try:

        logger.info(
            "User %s requested subdomains for %s.",
            user,
            domain,
        )

        simply_client = request.app.state.simply_client

        result = await simply_client.list_subdomains(domain)

        return {
            "status": "ok",
            "domain": domain,
            "subdomains": result,
        }

    except Exception as e:

        error_id = str(uuid.uuid4())

        logger.exception(
            "Simply.com list-subdomains failed. Error ID: %s",
            error_id,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error_id": error_id,
                "message": "Could not retrieve subdomains.",
            },
        ) from e


# ============================================================
# CHAT
# ============================================================

@router.post("/chat", response_model=ChatResponse)
async def chat(
    chat_request: ChatRequest,
    request: Request,
    user: str = Depends(verify_token),
):

    start = time.time()

    try:

        # 02-11-2026 - Logging user info is disabled for privacy reasons.
        #logger.info(
        #    "Chat request received from user: %s",
        #    user,
        #)

        # ----------------------------------------------------
        # SHARED SIMPLY.COM MCP CLIENT
        # ----------------------------------------------------

        # Access FastAPI application state using Request.
        simply_client = request.app.state.simply_client

        # ----------------------------------------------------
        # RUN LANGCHAIN AGENT
        # ----------------------------------------------------

        result = await run_agent(
            chat_request.message,
            simply_client,
        )

        # ----------------------------------------------------
        # LOG EXECUTION TIME
        # ----------------------------------------------------

        elapsed = time.time() - start

        logger.info(
            "Chat request completed in %.2f seconds",
            elapsed,
        )

        # ----------------------------------------------------
        # RETURN RESPONSE
        # ----------------------------------------------------

        return ChatResponse(
            response=result.get("response", {}),
        )

    except Exception as e:

        error_id = str(uuid.uuid4())

        logger.exception(
            "Chat request failed. Error ID: %s",
            error_id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_id": error_id,
                "type": type(e).__name__,
                "message": str(e),
            },
        ) from e


# ============================================================
# HEALTH
# ============================================================

@router.get("/health")
def health(request: Request, user: str = Depends(verify_token),):

    groq_live = False
    simply_oauth_live = False

    # --------------------------------------------------------
    # TEST GROQ
    # --------------------------------------------------------

    try:
        llm.invoke("ping")
        groq_live = True

    except Exception:
        logger.exception("Groq health check failed")

    # --------------------------------------------------------
    # TEST SIMPLY.COM OAUTH
    # --------------------------------------------------------

    try:

        oauth = request.app.state.simply_oauth

        token_info = oauth.get_token_info()

        simply_oauth_live = token_info["authenticated"]

    except Exception:
        logger.exception(
            "Simply.com OAuth health check failed"
        )

    return {
        "status": "ok",
        "groq": groq_live,
        "simply_oauth": simply_oauth_live,
    }


# ============================================================
# TEST GROQ
# ============================================================

@router.get("/test-groq")
def test_groq( user: str = Depends(verify_token),):

    try:

        res = llm.invoke("Tell me a joke")

        return {
            "status": "ok",
            "response": getattr(
                res,
                "content",
                str(res),
            ),
        }

    except Exception as e:

        logger.exception("Groq test failed")

        return {
            "status": "failed",
            "error": str(e),
        }


# ============================================================
# TEST WIKIPEDIA
# ============================================================

@router.get("/test-wikipedia")
def test_wikipedia( user: str = Depends(verify_token),):

    try:

        result = wikipedia_tool(
            "What is Python?"
        )

        if result.get("success"):

            return {
                "status": "ok",
                "result": result,
            }

        return {
            "status": "failed",
            "reason": result.get("content"),
        }

    except Exception as e:

        logger.exception("Wikipedia test failed")

        return {
            "status": "failed",
            "error": str(e),
        }


# ============================================================
# SIMPLY.COM - OAUTH STATUS
# ============================================================

@router.get("/simply/oauth/status")
async def simply_oauth_status(
    request: Request,
    user: str = Depends(verify_token),
):
    """
    Return Simply.com OAuth status.

    Does not expose access or refresh tokens.
    """

    try:

        oauth = request.app.state.simply_oauth

        return {
            "status": "ok",
            "oauth": oauth.get_token_info(),
        }

    except Exception as e:

        logger.exception(
            "Simply.com OAuth status check failed"
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Simply.com OAuth manager unavailable.",
        ) from e


# ============================================================
# SIMPLY.COM - LIST ACCOUNTS
# ============================================================

@router.get("/simply/accounts")
async def simply_list_accounts(
    request: Request,
    user: str = Depends(verify_token),
):
    """
    Retrieve Simply.com accounts.

    The MCP client automatically obtains a valid access token.
    """

    try:

        logger.info(
            "User %s requested Simply.com accounts.",
            user,
        )

        simply_client = request.app.state.simply_client

        accounts = await simply_client.list_accounts()

        return {
            "status": "ok",
            "accounts": accounts,
        }

    except Exception as e:

        error_id = str(uuid.uuid4())

        logger.error(
            "Simply.com account retrieval failed. Error ID: %s",
            error_id,
        )

        logger.exception(
            "Simply.com list-accounts failed"
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error_id": error_id,
                "type": type(e).__name__,
                "message": "Could not retrieve Simply.com accounts.",
            },
        ) from e

# ============================================================
# TEMPORARY SIMPLY.COM TOKEN REFRESH TEST
# ============================================================

@router.post("/simply/oauth/test-refresh")
async def test_simply_token_refresh(
    request: Request,
    user: str = Depends(verify_token),
):
    oauth = request.app.state.simply_oauth

    result = await oauth.force_refresh_for_testing()

    return {
        "message": "Simply.com token refresh successful.",
        "token_info": result
    }
