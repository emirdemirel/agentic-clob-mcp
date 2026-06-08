"""Unit tests for the CLOB engine order book."""

from decimal import Decimal

import pytest

from engine.models import Order, OrderStatus, Side, Trade
from engine.orderbook import OrderBook


@pytest.fixture
def book() -> OrderBook:
    return OrderBook()


class TestPlaceOrder:
    def test_place_buy_no_match(self, book: OrderBook):
        order, fills = book.place_order("c1", Side.BUY, Decimal("100"), Decimal("10"))
        assert order.status == OrderStatus.OPEN
        assert order.remaining_quantity == Decimal("10")
        assert fills == []
        assert len(book.bids) == 1

    def test_place_sell_no_match(self, book: OrderBook):
        order, fills = book.place_order("c1", Side.SELL, Decimal("100"), Decimal("10"))
        assert order.status == OrderStatus.OPEN
        assert order.remaining_quantity == Decimal("10")
        assert fills == []
        assert len(book.asks) == 1

    def test_exact_match(self, book: OrderBook):
        book.place_order("c1", Side.SELL, Decimal("100"), Decimal("5"))
        order, fills = book.place_order("c2", Side.BUY, Decimal("100"), Decimal("5"))

        assert order.status == OrderStatus.FILLED
        assert order.remaining_quantity == Decimal("0")
        assert len(fills) == 1
        assert fills[0].price == Decimal("100")
        assert fills[0].quantity == Decimal("5")
        assert len(book.asks) == 0
        assert len(book.bids) == 0

    def test_partial_fill(self, book: OrderBook):
        sell_order, _ = book.place_order("c1", Side.SELL, Decimal("100"), Decimal("3"))
        buy_order, fills = book.place_order("c2", Side.BUY, Decimal("100"), Decimal("10"))

        assert buy_order.status == OrderStatus.PARTIALLY_FILLED
        assert buy_order.remaining_quantity == Decimal("7")
        assert sell_order.status == OrderStatus.FILLED
        assert len(fills) == 1
        assert fills[0].quantity == Decimal("3")
        # Unfilled remainder rests on bid side
        assert len(book.bids) == 1

    def test_price_time_priority(self, book: OrderBook):
        """First order at same price level gets matched first (FIFO)."""
        first, _ = book.place_order("c1", Side.SELL, Decimal("100"), Decimal("5"))
        second, _ = book.place_order("c2", Side.SELL, Decimal("100"), Decimal("5"))

        _, fills = book.place_order("c3", Side.BUY, Decimal("100"), Decimal("5"))
        assert len(fills) == 1
        assert fills[0].maker_order_id == first.order_id

    def test_price_priority(self, book: OrderBook):
        """Lower-priced sell matched before higher-priced sell."""
        book.place_order("c1", Side.SELL, Decimal("100"), Decimal("5"))
        book.place_order("c2", Side.SELL, Decimal("99"), Decimal("5"))

        _, fills = book.place_order("c3", Side.BUY, Decimal("100"), Decimal("3"))
        assert fills[0].price == Decimal("99")

    def test_trade_at_maker_price(self, book: OrderBook):
        """Execution happens at the maker (resting) order's price."""
        book.place_order("c1", Side.SELL, Decimal("95"), Decimal("2"))
        _, fills = book.place_order("c2", Side.BUY, Decimal("100"), Decimal("2"))
        assert fills[0].price == Decimal("95")

    def test_multi_level_matching(self, book: OrderBook):
        """Buy sweeps through multiple ask price levels."""
        book.place_order("c1", Side.SELL, Decimal("100"), Decimal("2"))
        book.place_order("c2", Side.SELL, Decimal("101"), Decimal("3"))
        book.place_order("c3", Side.SELL, Decimal("102"), Decimal("5"))

        order, fills = book.place_order("c4", Side.BUY, Decimal("101"), Decimal("4"))
        assert len(fills) == 2
        assert fills[0].price == Decimal("100")
        assert fills[0].quantity == Decimal("2")
        assert fills[1].price == Decimal("101")
        assert fills[1].quantity == Decimal("2")
        assert order.remaining_quantity == Decimal("0")


class TestCancelOrder:
    def test_cancel_open_order(self, book: OrderBook):
        order, _ = book.place_order("c1", Side.BUY, Decimal("100"), Decimal("5"))
        success, msg = book.cancel_order(order.order_id)
        assert success is True
        assert order.status == OrderStatus.CANCELLED
        assert len(book.bids) == 0

    def test_cancel_filled_order(self, book: OrderBook):
        book.place_order("c1", Side.SELL, Decimal("100"), Decimal("5"))
        buy, _ = book.place_order("c2", Side.BUY, Decimal("100"), Decimal("5"))
        success, msg = book.cancel_order(buy.order_id)
        assert success is False
        assert "FILLED" in msg

    def test_cancel_nonexistent(self, book: OrderBook):
        success, msg = book.cancel_order("nonexistent-id")
        assert success is False
        assert "not found" in msg

    def test_cancel_already_cancelled(self, book: OrderBook):
        order, _ = book.place_order("c1", Side.BUY, Decimal("100"), Decimal("5"))
        book.cancel_order(order.order_id)
        success, msg = book.cancel_order(order.order_id)
        assert success is False


class TestIdempotency:
    def test_same_client_order_id(self, book: OrderBook):
        o1, _ = book.place_order("same-id", Side.BUY, Decimal("100"), Decimal("5"))
        o2, fills2 = book.place_order("same-id", Side.BUY, Decimal("100"), Decimal("5"))
        assert o1.order_id == o2.order_id
        assert fills2 == []
        assert len(book.bids) == 1  # Only one order on the book


class TestSnapshot:
    def test_snapshot_depth(self, book: OrderBook):
        for i in range(15):
            book.place_order(f"b{i}", Side.BUY, Decimal(str(100 + i)), Decimal("1"))
            book.place_order(f"a{i}", Side.SELL, Decimal(str(200 + i)), Decimal("1"))

        snap = book.get_snapshot(depth=10)
        assert len(snap.bids) == 10
        assert len(snap.asks) == 10

    def test_spread_calculation(self, book: OrderBook):
        book.place_order("c1", Side.BUY, Decimal("99"), Decimal("1"))
        book.place_order("c2", Side.SELL, Decimal("101"), Decimal("1"))

        snap = book.get_snapshot()
        assert snap.best_bid == Decimal("99")
        assert snap.best_ask == Decimal("101")
        assert snap.spread == Decimal("2")

    def test_empty_book_snapshot(self, book: OrderBook):
        snap = book.get_snapshot()
        assert snap.best_bid is None
        assert snap.best_ask is None
        assert snap.spread is None
        assert len(snap.bids) == 0
        assert len(snap.asks) == 0

    def test_bids_sorted_descending(self, book: OrderBook):
        book.place_order("c1", Side.BUY, Decimal("100"), Decimal("1"))
        book.place_order("c2", Side.BUY, Decimal("102"), Decimal("1"))
        book.place_order("c3", Side.BUY, Decimal("101"), Decimal("1"))

        snap = book.get_snapshot()
        prices = [lvl.price for lvl in snap.bids]
        assert prices == [Decimal("102"), Decimal("101"), Decimal("100")]

    def test_asks_sorted_ascending(self, book: OrderBook):
        book.place_order("c1", Side.SELL, Decimal("200"), Decimal("1"))
        book.place_order("c2", Side.SELL, Decimal("198"), Decimal("1"))
        book.place_order("c3", Side.SELL, Decimal("199"), Decimal("1"))

        snap = book.get_snapshot()
        prices = [lvl.price for lvl in snap.asks]
        assert prices == [Decimal("198"), Decimal("199"), Decimal("200")]


class TestConcurrency:
    def test_concurrent_orders(self, book: OrderBook):
        """Submit 100 orders concurrently; no crashes or data corruption."""
        from concurrent.futures import ThreadPoolExecutor

        def place(i: int):
            side = Side.BUY if i % 2 == 0 else Side.SELL
            price = Decimal("100") if side == Side.BUY else Decimal("200")
            book.place_order(f"c{i}", side, price, Decimal("1"))

        with ThreadPoolExecutor(max_workers=10) as pool:
            list(pool.map(place, range(100)))

        assert len(book.orders) == 100


class TestGetOrder:
    def test_get_existing(self, book: OrderBook):
        order, _ = book.place_order("c1", Side.BUY, Decimal("100"), Decimal("5"))
        found = book.get_order(order.order_id)
        assert found is not None
        assert found.order_id == order.order_id

    def test_get_nonexistent(self, book: OrderBook):
        assert book.get_order("not-real") is None


class TestRecentTrades:
    def test_get_recent(self, book: OrderBook):
        book.place_order("c1", Side.SELL, Decimal("100"), Decimal("5"))
        book.place_order("c2", Side.BUY, Decimal("100"), Decimal("5"))
        trades = book.get_recent_trades(limit=10)
        assert len(trades) == 1
        assert trades[0].quantity == Decimal("5")

    def test_empty(self, book: OrderBook):
        assert book.get_recent_trades() == []
