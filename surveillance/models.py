"""Data models for the short-sell surveillance system.

Contains dataclasses for orders, per-symbol state tracking,
and alert output. No business logic lives here.
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class Order:
    """An active / working order tracked by the engine."""

    client_order_id: str
    symbol: str
    side: str  # 'Buy' or 'Sell'
    qty: int
    price: float
    leaves_qty: int  # shares still open (unfilled)
    sell_flag: str  # 'Long', 'Short', or '' (for buys)
    source: str


@dataclass
class SymbolState:
    """Real-time bookkeeping for a single symbol.

    Tracks net position, borrow limit, and all open orders.
    Working-quantity properties are computed on the fly from
    the open-orders dict so they never drift out of sync.
    """

    symbol: str
    net_position: int  # positive = long, negative = short
    borrow: int  # max shares we may borrow for the day
    open_orders: Dict[str, Order] = field(default_factory=dict)

    @property
    def working_long_sell_qty(self) -> int:
        """Total leaves_qty of open sell orders flagged 'Long'."""
        return sum(
            o.leaves_qty
            for o in self.open_orders.values()
            if o.side == "Sell" and o.sell_flag == "Long"
        )

    @property
    def working_short_sell_qty(self) -> int:
        """Total leaves_qty of open sell orders flagged 'Short'."""
        return sum(
            o.leaves_qty
            for o in self.open_orders.values()
            if o.side == "Sell" and o.sell_flag == "Short"
        )


@dataclass
class Alert:
    """Emitted when a sell order's flag differs from what it should be."""

    symbol: str
    client_order_id: str
    actual_flag: str
    expected_flag: str
    net_position: int
    working_long_sell_qty: int
    working_short_sell_qty: int
    borrow: int
    order_qty: int
