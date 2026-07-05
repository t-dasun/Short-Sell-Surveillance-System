"""Pure decision logic for sell-flag validation.

This module answers exactly one question:
    "Given the current symbol state, what flag should this sell order have?"

This module does not the mutate state.
The engine calls this function, compares the result with the
actual flag, and raises an alert if they differ.

Possible return values
----------------------
'Long'        - fully covered by owned (but uncommitted) shares.
'Short'       - not covered by owned shares, but within the borrow limit.
'Uncovered'   - would exceed the borrow limit.
'0-crossing'  - the order spans both owned and borrowed territory
                and must be split into separate Long and Short orders.
"""


def determine_expected_flag(
    net_position: int,
    working_long_sell_qty: int,
    working_short_sell_qty: int,
    borrow: int,
    order_qty: int,
) -> str:
    """Return the flag this sell order should carry.

    Parameters
    ----------
    net_position:
        Current net share position (positive = long, negative = short).
    working_long_sell_qty:
        Total ``leaves_qty`` of open sell orders flagged ``Long``.
    working_short_sell_qty:
        Total ``leaves_qty`` of open sell orders flagged ``Short``.
    borrow:
        Maximum shares the desk may borrow for short selling today.
    order_qty:
        Quantity of the incoming sell order.
    """
    # Shares we own that are NOT already committed to existing Long sells.
    available_owned = net_position - working_long_sell_qty

    # ---- Zero-crossing -------------------------------------------------
    # The order would partly sell owned stock and partly go short.
    # A single order cannot straddle the zero boundary.
    if 0 < available_owned < order_qty:
        return "0-crossing"

    # ---- Long ----------------------------------------------------------
    # Fully covered by owned shares → must be flagged Long.
    if available_owned >= order_qty:
        return "Long"

    # ---- Short(available_owned ≤ 0) ------------------------------------
    # Two independent constraints from the assignment spec:
    #   1. Combined working-short quantity must not exceed borrow.
    total_working_short = working_short_sell_qty + order_qty
    #   2. Position after ALL sells must not drop below -borrow. (both short&long)
    position_after_all_sells = (
        available_owned - working_short_sell_qty - order_qty
    )

    if total_working_short > borrow or position_after_all_sells < -borrow:
        return "Uncovered"

    return "Short"
