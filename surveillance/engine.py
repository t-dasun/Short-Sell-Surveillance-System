"""Event-replay engine — the brain of the surveillance system.

Processes order-event rows one by one, maintaining per-symbol
state and delegating flag decisions to ``flag_rules``.

Responsibilities
----------------
* Track open orders (add on New/Amend, remove on Cancel/Cancelled/full Fill).
* Handle both ``Fill`` and ``Filled`` events because the sample feed contains both forms.
* Treat both ``Cancel`` and ``Cancelled`` as terminal cancellation events for this assignment.
* Update ``net_position`` on fills.
* Call ``determine_expected_flag`` for every Sell ``New`` and ``Amend``.
* Return an ``Alert`` whenever the actual flag ≠ expected flag.

The engine does NOT decide what the correct flag is — that logic
lives entirely in ``flag_rules.determine_expected_flag``.
"""

from typing import Dict, List, Optional, Tuple

from .flag_rules import determine_expected_flag
from .models import Alert, Order, SymbolState


class SurveillanceEngine:
    """Stateful engine that replays order events and emits alerts."""

    def __init__(self, ref_data: Dict[str, Tuple[int, int]]) -> None:
        """Initialise per-symbol state from reference data.

        Parameters
        ----------
        ref_data:
            ``{symbol: (init_position, borrow)}``
        """
        self.states: Dict[str, SymbolState] = {}
        for symbol, (init_pos, borrow) in ref_data.items():
            self.states[symbol] = SymbolState(
                symbol=symbol,
                net_position=init_pos,
                borrow=borrow,
            )

    # ── public interface ───────────────────────────────────────────

    def process_event(self, row: Dict[str, str]) -> Optional[Alert]:
        """Process a single event row and return an Alert (or None)."""
        handler = {
            "New": self._handle_new,
            "NewAccept": self._handle_new_accept,
            "Amend": self._handle_amend,
            "AmendConfirm": self._handle_amend_confirm,
            "Fill": self._handle_fill,
            "Filled": self._handle_filled,
            "Cancel": self._handle_cancel,
            "Cancelled": self._handle_cancelled,
        }.get(row["event"])

        if handler is None:
            return None  # unknown event type — skip
        return handler(row)

    # ── helpers ────────────────────────────────────────────────────

    def _get_state(self, symbol: str) -> Optional[SymbolState]:
        """Return state for symbols present in ref_data.

        The assignment says symbols missing from ref_data should be skipped,
        so the engine does not create default state for unknown symbols.
        """
        return self.states.get(symbol)

    def _check_sell_flag(
        self, state: SymbolState, client_order_id: str,
        sell_flag: str, order_qty: int,
    ) -> Optional[Alert]:
        """Compare actual flag with the expected flag; return Alert on mismatch."""
        expected = determine_expected_flag(
            net_position=state.net_position,
            working_long_sell_qty=state.working_long_sell_qty,
            working_short_sell_qty=state.working_short_sell_qty,
            borrow=state.borrow,
            order_qty=order_qty,
        )
        if expected == sell_flag:
            return None

        return Alert(
            symbol=state.symbol,
            client_order_id=client_order_id,
            actual_flag=sell_flag,
            expected_flag=expected,
            net_position=state.net_position,
            working_long_sell_qty=state.working_long_sell_qty,
            working_short_sell_qty=state.working_short_sell_qty,
            borrow=state.borrow,
            order_qty=order_qty,
        )

    @staticmethod
    def _make_order(row: Dict[str, str], leaves_qty: int) -> Order:
        """Build an Order from a raw event row."""
        price_str = row.get("price", "").strip()
        return Order(
            client_order_id=row["client_order_id"],
            symbol=row["symbol"],
            side=row["side"],
            qty=int(row["qty"]),
            price=float(price_str) if price_str else 0.0,
            leaves_qty=leaves_qty,
            sell_flag=row.get("sell_flag", "").strip(),
            source=row.get("source", ""),
        )

    # ── event handlers ─────────────────────────────────────────────

    def _handle_new(self, row: Dict[str, str]) -> Optional[Alert]:
        """New order submitted.

        * Check the sell flag for Sell orders (BEFORE adding to state).
        * Add the order to open_orders with leaves_qty = qty.
        """
        symbol = row["symbol"]
        side = row["side"]
        qty = int(row["qty"])
        sell_flag = row.get("sell_flag", "").strip()
        client_order_id = row["client_order_id"]
        state = self._get_state(symbol)
        if state is None:
            return None

        alert: Optional[Alert] = None
        if side == "Sell":
            alert = self._check_sell_flag(state, client_order_id, sell_flag, qty)

        # Register the order (leaves starts at full qty; NewAccept may correct it).
        state.open_orders[client_order_id] = self._make_order(row, leaves_qty=qty)
        return alert

    def _handle_new_accept(self, row: Dict[str, str]) -> Optional[Alert]:
        """Exchange acknowledged the order — update leaves_qty only."""
        state = self._get_state(row["symbol"])
        if state is None:
            return None
        order = state.open_orders.get(row["client_order_id"])
        if order is not None:
            leaves_str = row.get("leaves_qty", "").strip()
            if leaves_str:
                order.leaves_qty = int(leaves_str)
        return None

    def _handle_amend(self, row: Dict[str, str]) -> Optional[Alert]:
        """Amend replaces an old order with a new one.

        1. Remove the old order (frees its working-qty commitment).
        2. Check the sell flag for the *new* order.
        3. Add the new order to open_orders.
        """
        symbol = row["symbol"]
        side = row["side"]
        qty = int(row["qty"])
        sell_flag = row.get("sell_flag", "").strip()
        client_order_id = row["client_order_id"]
        orig_client_order_id = row["orig_client_order_id"]
        state = self._get_state(symbol)
        if state is None:
            return None

        # Remove old order so working quantities reflect state *without* it.
        state.open_orders.pop(orig_client_order_id, None)

        alert: Optional[Alert] = None
        if side == "Sell":
            alert = self._check_sell_flag(state, client_order_id, sell_flag, qty)

        # Add the amended order.  Use full qty as leaves_qty —
        # AmendConfirm (next event, same timestamp) will correct it.
        state.open_orders[client_order_id] = self._make_order(row, leaves_qty=qty)
        return alert

    def _handle_amend_confirm(self, row: Dict[str, str]) -> Optional[Alert]:
        """Exchange confirmed the amend — update leaves_qty."""
        state = self._get_state(row["symbol"])
        if state is None:
            return None
        order = state.open_orders.get(row["client_order_id"])
        if order is not None:
            leaves_str = row.get("leaves_qty", "").strip()
            if leaves_str:
                order.leaves_qty = int(leaves_str)
        return None

    def _handle_fill(self, row: Dict[str, str]) -> Optional[Alert]:
        """Partial or full fill.

        * Compute fill amount from the difference in leaves_qty.
        * Adjust net_position accordingly.
        * Remove the order if fully filled (leaves = 0).
        """
        state = self._get_state(row["symbol"])
        if state is None:
            return None
        client_order_id = row["client_order_id"]
        order = state.open_orders.get(client_order_id)

        if order is not None:
            new_leaves_str = row.get("leaves_qty", "").strip()
            new_leaves = int(new_leaves_str) if new_leaves_str else 0
            fill_amount = order.leaves_qty - new_leaves

            if order.side == "Buy":
                state.net_position += fill_amount
            else:
                state.net_position -= fill_amount

            order.leaves_qty = new_leaves
            if new_leaves <= 0:
                del state.open_orders[client_order_id]

        return None

    def _handle_filled(self, row: Dict[str, str]) -> Optional[Alert]:
        """Order fully filled (terminal event).

        The order may have been submitted via a separate workflow
        (e.g. ManualTrade) and may reference an earlier order via
        ``orig_client_order_id``.
        """
        state = self._get_state(row["symbol"])
        if state is None:
            return None
        client_id = row["client_order_id"]
        orig_id = row.get("orig_client_order_id", "").strip()

        # Find the order under either key.
        order_key = None
        if orig_id and orig_id in state.open_orders:
            order_key = orig_id
        elif client_id in state.open_orders:
            order_key = client_id

        if order_key is not None:
            order = state.open_orders.pop(order_key)
            fill_amount = order.leaves_qty
            if order.side == "Buy":
                state.net_position += fill_amount
            else:
                state.net_position -= fill_amount
        else:
            # Order not previously tracked — treat as instant fill.
            qty = int(row["qty"]) if row.get("qty", "").strip() else 0
            if row["side"] == "Buy":
                state.net_position += qty
            else:
                state.net_position -= qty

        return None

    def _handle_cancel(self, row: Dict[str, str]) -> Optional[Alert]:
        """Cancel removes the order for this assignment.

        The prompt groups Cancel / Cancelled together as withdrawn orders, so
        both event names use the same state-removal logic.
        """
        return self._remove_cancelled_order(row)

    def _handle_cancelled(self, row: Dict[str, str]) -> Optional[Alert]:
        """Cancelled removes the order using the same logic as Cancel."""
        return self._remove_cancelled_order(row)

    def _remove_cancelled_order(self, row: Dict[str, str]) -> Optional[Alert]:
        state = self._get_state(row["symbol"])
        if state is None:
            return None
        orig_id = row.get("orig_client_order_id", "").strip()
        state.open_orders.pop(orig_id, None)
        return None
