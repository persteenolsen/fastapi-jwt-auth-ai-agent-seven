
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import router
from config import logger

from integrations.simply_oauth import SimplyOAuthManager
from integrations.simply_client import SimplyMCPClient

from utils import init_db


# ============================================================
# FASTAPI LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("Starting FastAPI application...")

    try:
        # ----------------------------------------------------
        # INITIALIZE POSTGRESQL
        # ----------------------------------------------------

        logger.info("Initializing PostgreSQL...")

        init_db()

        logger.info("PostgreSQL initialized successfully.")

        # ----------------------------------------------------
        # INITIALIZE SIMPLY.COM OAUTH
        # ----------------------------------------------------

        logger.info("Initializing Simply.com OAuth manager...")

        simply_oauth = SimplyOAuthManager(
            refresh_buffer=120,
            timeout=30,
        )

        app.state.simply_oauth = simply_oauth

        # ----------------------------------------------------
        # INITIALIZE SIMPLY.COM MCP CLIENT
        # ----------------------------------------------------

        logger.info("Initializing Simply.com MCP client...")

        simply_client = SimplyMCPClient(
            oauth_manager=simply_oauth
        )

        app.state.simply_client = simply_client

        logger.info("Simply.com MCP client initialized.")

        logger.info("FastAPI startup completed.")

        yield

    except Exception:
        logger.exception("FastAPI startup failed.")
        raise

    finally:
        logger.info("Shutting down FastAPI application...")


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title=(
        "FastAPI with JWT Authentication and a "
        "LangChain AI Agent for Simply.com Private MCP"
    ),
    description=(
        "02-11-2026 - FastAPI with JWT authentication and a "
        "Groq-powered LangChain agent using Simply.com "
        "private MCP tools and Wikipedia. "
        "Includes automatic Simply.com OAuth 2.1 "
        "token refreshing with PostgreSQL persistence."
    ),
    version="0.0.5",
    contact={
        "name": "Per Olsen",
        "url": "https://persteenolsen.netlify.app",
    },
    lifespan=lifespan,
)


# ============================================================
# CORS CONFIGURATION
# ============================================================

origins = [
    "https://fastapi-jwt-auth-ai-agent-seven.vercel.app",
    "https://vue.fastapi.jwt.auth.ai.agent.seven.persteenolsen.com",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# API ROUTES
# ============================================================

app.include_router(router)


# ============================================================
# APPLICATION INFORMATION
# ============================================================

logger.info("FastAPI application configured successfully.")
