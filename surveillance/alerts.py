"""Alert formatting and logging.

Simple, human-readable output and logging for each mis-flagged sell order.
"""

import logging
from .models import Alert

logger = logging.getLogger("surveillance.alerts")


def format_alert(alert: Alert) -> str:
    """Return a single-line alert string.

    Includes symbol, order id, actual vs expected flag,
    and the supporting figures (net position, working
    quantities, borrow, order qty).
    """
    return (
        f"ALERT  symbol={alert.symbol}  "
        f"order={alert.client_order_id}  "
        f"flag={alert.actual_flag} -> expected={alert.expected_flag}  |  "
        f"net_pos={alert.net_position}  "
        f"wk_long_sell={alert.working_long_sell_qty}  "
        f"wk_short_sell={alert.working_short_sell_qty}  "
        f"borrow={alert.borrow}  "
        f"order_qty={alert.order_qty}"
    )


def log_alert(alert: Alert) -> None:
    """Log a mis-flagged sell order alert using the surveillance logger."""
    logger.warning(format_alert(alert))
