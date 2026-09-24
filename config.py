import os
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Load .env first, then env.txt (does not override existing values).
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / "env.txt")


def _require(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value or "xxxxxxxx" in value.lower():
        print(
            f"Missing required environment variable: {name}. "
            f"Set it in .env or env.txt.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return value


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = int(str(raw).strip())
    except ValueError:
        print(
            f"{name} must be an integer, got {raw!r}.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if value < minimum:
        print(
            f"{name} must be >= {minimum}, got {value}.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return value


# ──────────────────────────────
# Logging Setup
# ──────────────────────────────

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("ubitvip")

# ──────────────────────────────
# Telegram
# ──────────────────────────────

BOT_TOKEN: str = _require("BOT_TOKEN")
CHANNEL_ID: str = _require("CHANNEL_ID")


def _env_admin_ids() -> frozenset[int]:
    raw = os.getenv("ADMIN_IDS", "").strip()
    if not raw:
        logger.warning(
            "ADMIN_IDS is empty; the Telegram admin panel is disabled."
        )
        return frozenset()

    admin_ids = set()
    for item in raw.split(","):
        value = item.strip()
        if not value:
            continue
        try:
            admin_id = int(value)
        except ValueError:
            print(
                f"ADMIN_IDS contains an invalid Telegram user ID: {value!r}.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if admin_id <= 0:
            print(
                "ADMIN_IDS values must be positive Telegram user IDs.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        admin_ids.add(admin_id)

    return frozenset(admin_ids)


ADMIN_IDS: frozenset[int] = _env_admin_ids()

# ──────────────────────────────
# Yubit Partner API
# ──────────────────────────────

YUBIT_API_KEY: str = _require("YUBIT_API_KEY")
YUBIT_SECRET_KEY: str = _require("YUBIT_SECRET_KEY")

YUBIT_BASE_URL: str = os.getenv(
    "YUBIT_BASE_URL",
    "https://openapi.yubit.com",
).rstrip("/")
YUBIT_RECV_WINDOW: int = _env_int(
    "YUBIT_RECV_WINDOW",
    5000,
    minimum=1,
)
if YUBIT_RECV_WINDOW > 60000:
    print(
        "YUBIT_RECV_WINDOW must be <= 60000.",
        file=sys.stderr,
    )
    raise SystemExit(1)

# ──────────────────────────────
# VIP Settings
# ──────────────────────────────

MIN_BALANCE: int = _env_int("MIN_BALANCE", 50)
WARNING_RANGE: int = _env_int("WARNING_RANGE", 15)

WARNING_LIMIT: int = MIN_BALANCE + WARNING_RANGE

# ──────────────────────────────
# UID Validation
# ──────────────────────────────

UID_MIN_LENGTH: int = _env_int("UID_MIN_LENGTH", 4, minimum=1)
UID_MAX_LENGTH: int = _env_int("UID_MAX_LENGTH", 20, minimum=1)

if UID_MIN_LENGTH > UID_MAX_LENGTH:
    print(
        "UID_MIN_LENGTH cannot be greater than UID_MAX_LENGTH.",
        file=sys.stderr,
    )
    raise SystemExit(1)

# ──────────────────────────────
# Scheduler
# ──────────────────────────────

CHECK_INTERVAL_DAYS: int = _env_int(
    "CHECK_INTERVAL_DAYS",
    7,
    minimum=1,
)

INVITE_EXPIRE_SECONDS: int = CHECK_INTERVAL_DAYS * 24 * 60 * 60

# ──────────────────────────────
# External Links & Support
# ──────────────────────────────

REGISTER_LINK: str = os.getenv(
    "REGISTER_LINK",
    "https://www.yubit.com/",
)

# ──────────────────────────────
# Database
# ──────────────────────────────

_db_name = os.getenv("DB_NAME", "database.db").strip() or "database.db"
_db_path = Path(_db_name)
if not _db_path.is_absolute():
    _db_path = BASE_DIR / _db_path

DB_NAME: str = str(_db_path)
