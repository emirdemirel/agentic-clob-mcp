from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from decimal import Decimal

from sortedcontainers import SortedDict

from engine.models import Order, OrderStatus, Side, Trade


@dataclass
class PriceLevelInfo:
    price: Decimal
    total_quantity: Decimal
    order_count: int


@dataclass
class Snapshot:
    pair: str
    bids: list[PriceLevelInfo]
    asks: list[PriceLevelInfo]
    best_bid: Decimal | None
    best_ask: Decimal | None
    spread: Decimal | None
    timestamp_ns: int


class OrderBook:
    """Thread-safe Central Limit Order Book with price-time priority matching."""

    def __init__(self) -> None:
        self.bids: SortedDict = SortedDict()  # price -> deque[Order]
        self.asks: SortedDict = SortedDict()  # price -> deque[Order]
        self.orders: dict[str, Order] = {}
        self.trades: list[Trade] = []
        self._lock = threading.RLock()
        self._idempotency: dict[str, str] = {}  # client_order_id -> order_id

    def place_order(
        self, client_order_id: str, side: Side, price: Decimal, quantity: Decimal
    ) -> tuple[Order, list[Trade]]:
        with self._lock:
            if client_order_id in self._idempotency:
                existing_id = self._idempotency[client_order_id]
                return self.orders[existing_id], []

            order = Order(
                client_order_id=client_order_id,
                side=side,
                price=price,
                original_quantity=quantity,
                remaining_quantity=quantity,
            )
            self.orders[order.order_id] = order

            fills = self._match(order)

            if order.remaining_quantity > 0 and order.status != OrderStatus.CANCELLED:
                book = self.bids if side == Side.BUY else self.asks
                if order.price not in book:
                    book[order.price] = deque()
                book[order.price].append(order)

            self._idempotency[client_order_id] = order.order_id
            return order, fills

    def _match(self, incoming: Order) -> list[Trade]:
        fills: list[Trade] = []

        if incoming.side == Side.BUY:
            opposite = self.asks
            should_match = lambda best_price: best_price <= incoming.price
            get_best_key = lambda: opposite.keys()[0]
        else:
            opposite = self.bids
            should_match = lambda best_price: best_price >= incoming.price
            get_best_key = lambda: opposite.keys()[-1]

        while incoming.remaining_quantity > 0 and len(opposite) > 0:
            best_price = get_best_key()
            if not should_match(best_price):
                break

            level: deque[Order] = opposite[best_price]
            maker = level[0]

            fill_qty = min(incoming.remaining_quantity, maker.remaining_quantity)
            trade = Trade(
                price=maker.price,
                quantity=fill_qty,
                maker_order_id=maker.order_id,
                taker_order_id=incoming.order_id,
            )

            incoming.remaining_quantity -= fill_qty
            maker.remaining_quantity -= fill_qty

            incoming.status = (
                OrderStatus.FILLED
                if incoming.remaining_quantity == 0
                else OrderStatus.PARTIALLY_FILLED
            )
            maker.status = (
                OrderStatus.FILLED
                if maker.remaining_quantity == 0
                else OrderStatus.PARTIALLY_FILLED
            )

            if maker.remaining_quantity == 0:
                level.popleft()
                if not level:
                    del opposite[best_price]

            self.trades.append(trade)
            fills.append(trade)

        return fills

    def cancel_order(self, order_id: str) -> tuple[bool, str]:
        with self._lock:
            order = self.orders.get(order_id)
            if order is None:
                return False, f"Order {order_id} not found"
            if order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED):
                return False, f"Order {order_id} is already {order.status.name}"

            book = self.bids if order.side == Side.BUY else self.asks
            if order.price in book:
                level = book[order.price]
                try:
                    level.remove(order)
                except ValueError:
                    pass
                if not level:
                    del book[order.price]

            order.status = OrderStatus.CANCELLED
            return True, f"Order {order_id} cancelled"

    def get_snapshot(self, depth: int = 10) -> Snapshot:
        with self._lock:
            bid_levels = []
            for price in reversed(self.bids.keys()):
                if len(bid_levels) >= depth:
                    break
                level = self.bids[price]
                total_qty = sum(o.remaining_quantity for o in level)
                bid_levels.append(PriceLevelInfo(price, total_qty, len(level)))

            ask_levels = []
            for price in self.asks.keys():
                if len(ask_levels) >= depth:
                    break
                level = self.asks[price]
                total_qty = sum(o.remaining_quantity for o in level)
                ask_levels.append(PriceLevelInfo(price, total_qty, len(level)))

            best_bid = self.bids.keys()[-1] if self.bids else None
            best_ask = self.asks.keys()[0] if self.asks else None
            spread = (best_ask - best_bid) if (best_bid is not None and best_ask is not None) else None

            return Snapshot(
                pair="ETH/USDC",
                bids=bid_levels,
                asks=ask_levels,
                best_bid=best_bid,
                best_ask=best_ask,
                spread=spread,
                timestamp_ns=time.time_ns(),
            )

    def get_order(self, order_id: str) -> Order | None:
        return self.orders.get(order_id)

    def get_recent_trades(self, limit: int = 20) -> list[Trade]:
        return self.trades[-limit:] if self.trades else []
