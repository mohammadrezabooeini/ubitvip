from datetime import datetime, timedelta, timezone
from typing import Optional

MAX_BALANCE_WARNINGS = 3


def is_insufficient_balance(balance: float, min_balance: float) -> bool:
    """User cannot join or stay if balance is below the minimum."""
    return balance < min_balance


def is_warning_balance(
    balance: float,
    min_balance: float,
    warning_limit: float,
) -> bool:
    """Warn when balance is still valid but inside the warning range."""
    return min_balance <= balance <= warning_limit


def should_remove_after_warnings(warning_count: int) -> bool:
    """Remove on the next failed check after three delivered warnings."""
    return warning_count >= MAX_BALANCE_WARNINGS


def needs_recheck(
    last_check: Optional[str],
    interval_days: int,
    now: Optional[datetime] = None,
) -> bool:
    """Return True if this user is due for a balance check."""
    if not last_check:
        return True

    current = now or datetime.now(timezone.utc).replace(tzinfo=None)

    try:
        checked_at = datetime.strptime(
            str(last_check),
            "%Y-%m-%d %H:%M:%S",
        )
    except ValueError:
        return True

    return current - checked_at >= timedelta(days=interval_days)
