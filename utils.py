
"""
Utility functions for Agent Simply MCP.
PostgreSQL database connection and initialization.
"""

from sqlalchemy import create_engine, text

from config import DATABASE_URL


# ============================================================
# DATABASE CONNECTION
# ============================================================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
)


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():
    """
    Create the Simply.com OAuth credentials table.

    No migrations or additional database setup required.
    """

    with engine.begin() as connection:

        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS simply_oauth_credentials (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                tokens JSONB NOT NULL,
                client_info JSONB NOT NULL,
                expires_at BIGINT NOT NULL,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))

    return True
