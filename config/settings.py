"""
Environment-driven configuration.

No credentials, client identifiers, or environment names are committed to this
repository. Every value below is read from the environment at runtime, with a
safe local default. See .env.example for the full list.
"""

import os


def _int_list(raw: str):
    """Parse a comma-separated string of integers into a list."""
    if not raw:
        return []
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


# --- Server -----------------------------------------------------------------
HOST = os.getenv("APP_HOST", "127.0.0.1")
PORT = int(os.getenv("APP_PORT", "5000"))
DEBUG = os.getenv("APP_DEBUG", "false").lower() == "true"

# Comma-separated list of allowed origins. Never ship "*" to production.
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")]

# --- Data source ------------------------------------------------------------
# Logical name of the target environment/tenant database. Supplied per request
# or via env; never hardcoded.
DEFAULT_SERVER_CODE = os.getenv("DEFAULT_SERVER_CODE", "local")

DB_URL = os.getenv("DATABASE_URL", "")  # e.g. postgresql://user:pass@host:5432/dbname

CACHE_DIR = os.getenv("CACHE_DIR", "./data/cache")
CACHE_REFRESH_HOUR = int(os.getenv("CACHE_REFRESH_HOUR", "0"))

# --- Local dev harness only -------------------------------------------------
# Used by `python -m src.app --local` to exercise modules without a frontend.
DEV_CLIENT_INDEX = _int_list(os.getenv("DEV_CLIENT_INDEX", ""))
DEV_USER_EMP_INDEX = os.getenv("DEV_USER_EMP_INDEX")
DEV_USER_EMP_INDEX = int(DEV_USER_EMP_INDEX) if DEV_USER_EMP_INDEX else None

# --- Defaults ---------------------------------------------------------------
DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "USD")
DEFAULT_PALETTE = ["#05668D", "#028090", "#00A896", "#02C39A"]
DEFAULT_TEXT_COLOR = "#333333"
DEFAULT_GRAPH_SIZE = "2x2"

# Sentinel date used by the source system to mean "no end date yet".
SENTINEL_DATE = "1900-01-01"

# Grade values treated as leadership. Configurable because grade taxonomies
# differ per deployment.
LEADERSHIP_GRADES = [g.strip() for g in os.getenv("LEADERSHIP_GRADES", "High-Level").split(",")]
LEADERSHIP_KEYWORDS = ["senior", "lead", "director", "manager", "executive", "head"]
FLEXIBLE_WORK_KEYWORDS = ["part", "contract", "remote", "hybrid", "casual", "flex"]
