"""Tests focused on the matching engine logic -- edge cases and invariants."""

from decimal import Decimal

import pytest

from engine.models import OrderStatus, Side
from engine.orderbook import OrderBook


@pytest.fixture
def book() -> OrderBook:
    return OrderBook()


class TestMatchingInvariants:
    def test_trade_price_is_maker_price(self, book: OrderBook):
        """Trades always execute at the maker (resting) order's price."""
        book.place_order("s1", Side.SELL, Decimal("100"), Decimal("5"))
        _, fills = book.place_order("b1", Side.BUY, Decimal("105"), Decimal("5"))
        assert fills[0].price == Decimal("100")  # Maker's price, not 105

    def test_no_self_trade(self, book: OrderBook):
        """Different client_order_ids are always different orders."""
        book.place_order("c1", Side.SELL, Decimal("100"), Decimal("5"))
        order, fills = book.place_order("c2", Side.BUY, Decimal("100"), Decimal("5"))
        assert fills[0].maker_order_id != fills[0].taker_order_id

    def test_quantity_conservation(self, book: OrderBook):
        """Total filled quantity equals original quantity when fully matched."""
        book.place_order("s1", Side.SELL, Decimal("100"), Decimal("10"))
        order, fills = book.place_order("b1", Side.BUY, Decimal("100"), Decimal("10"))
        total_filled = sum(f.quantity for f in fills)
        assert total_filled == Decimal("10")
        assert order.filled_quantity == Decimal("10")

    def test_sell_matches_against_bids(self, book: OrderBook):
        """Incoming sell matches against the highest bid first."""
        book.place_order("b1", Side.BUY, Decimal("98"), Decimal("2"))
        book.place_order("b2", Side.BUY, Decimal("100"), Decimal("2"))
        book.place_order("b3", Side.BUY, Decimal("99"), Decimal("2"))

        _, fills = book.place_order("s1", Side.SELL, Decimal("98"), Decimal("3"))
        # Should match 100 first (highest bid), then 99
        assert fills[0].price == Decimal("100")
        assert fills[1].price == Decimal("99")

    def test_no_match_when_spread_positive(self, book: OrderBook):
        """Buy at 99 doesn't match sell at 100."""
        book.place_order("s1", Side.SELL, Decimal("100"), Decimal("5"))
        order, fills = book.place_order("b1", Side.BUY, Decimal("99"), Decimal("5"))
        assert fills == []
        assert order.status == OrderStatus.OPEN

    def test_partial_maker_survives(self, book: OrderBook):
        """Partially filled maker stays on the book with correct remaining qty."""
        sell, _ = book.place_order("s1", Side.SELL, Decimal("100"), Decimal("10"))
        _, fills = book.place_order("b1", Side.BUY, Decimal("100"), Decimal("3"))

        assert sell.remaining_quantity == Decimal("7")
        assert sell.status == OrderStatus.PARTIALLY_FILLED
        assert len(book.asks) == 1

    def test_multiple_fills_single_order(self, book: OrderBook):
        """One aggressive order can fill against multiple resting orders."""
        book.place_order("s1", Side.SELL, Decimal("100"), Decimal("2"))
        book.place_order("s2", Side.SELL, Decimal("101"), Decimal("2"))
        book.place_order("s3", Side.SELL, Decimal("102"), Decimal("2"))

        order, fills = book.place_order("b1", Side.BUY, Decimal("102"), Decimal("6"))
        assert len(fills) == 3
        assert order.status == OrderStatus.FILLED

    def test_filled_quantity_property(self, book: OrderBook):
        book.place_order("s1", Side.SELL, Decimal("100"), Decimal("5"))
        order, _ = book.place_order("b1", Side.BUY, Decimal("100"), Decimal("3"))
        # The buy filled 3 against the sell
        assert order.filled_quantity == Decimal("3")

    def test_decimal_precision(self, book: OrderBook):
        """Decimal values maintain precision through matching."""
        book.place_order("s1", Side.SELL, Decimal("100.25"), Decimal("1.123"))
        order, fills = book.place_order("b1", Side.BUY, Decimal("100.25"), Decimal("1.123"))
        assert fills[0].price == Decimal("100.25")
        assert fills[0].quantity == Decimal("1.123")
        assert order.remaining_quantity == Decimal("0")
