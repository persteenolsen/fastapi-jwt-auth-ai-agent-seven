
import os
import logging

from dotenv import load_dotenv

# Load local environment variables.
# Deployed environments can supply these directly.
load_dotenv()

# ============================================================
# DATABASE
# ============================================================

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("Missing environment variable: DATABASE_URL")


# ============================================================
# APPLICATION CONFIGURATION
# ============================================================

SECRET_KEY = os.getenv("SECRET_KEY")
FAKE_USERNAME = os.getenv("FAKE_USERNAME")
FAKE_PASSWORD = os.getenv("FAKE_PASSWORD")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

required_env_vars = [
    "SECRET_KEY",
    "FAKE_USERNAME",
    "FAKE_PASSWORD",
    "GROQ_API_KEY",
]

for var in required_env_vars:
    if not os.getenv(var):
        raise RuntimeError(
            f"Missing environment variable: {var}"
        )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


# ============================================================
# OPTIONAL API CONFIGURATION
# ============================================================

#VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)
