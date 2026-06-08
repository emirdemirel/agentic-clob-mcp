from __future__ import annotations

import asyncio
import os
import re
import sys
import time
from collections import deque
from decimal import Decimal, InvalidOperation

import grpc

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "engine"))

import orderbook_pb2 as pb2
import orderbook_pb2_grpc as pb2_grpc

from agent.schemas import OrderInput

INJECTION_PATTERNS = [
    re.compile(r"(?i)(ignore|override|disregard|forget).{0,30}(instruct|previous|above|rules|safety)"),
    re.compile(r"(?i)SYSTEM\s*:"),
    re.compile(r"(?i)you are now a different"),
]

MAX_OPEN_ORDERS = 50
MAX_DAILY_VOLUME = Decimal("10000")
MARKET_SANITY_THRESHOLD = Decimal("0.10")  # 10%


def validate_order(price_str: str, quantity_str: str) -> OrderInput:
    """Parse and validate order parameters. Raises ValueError on invalid input."""
    try:
        price = Decimal(price_str)
        quantity = Decimal(quantity_str)
    except InvalidOperation as e:
        raise ValueError(f"Invalid decimal value: {e}")
    return OrderInput(price=price, quantity=quantity)


def check_prompt_injection(input_str: str) -> str | None:
    """Return rejection reason if injection detected, else None."""
    for pattern in INJECTION_PATTERNS:
        if pattern.search(input_str):
            return "Potential prompt injection detected. Request rejected."
    return None


async def check_market_sanity(
    price: Decimal, side: str, stub: pb2_grpc.OrderBookServiceStub
) -> str | None:
    """Reject orders with price >10% from current mid-price. Returns error or None."""
    try:
        response = await asyncio.to_thread(
            stub.GetOrderBook, pb2.GetOrderBookRequest(depth=1), timeout=5
        )
    except grpc.RpcError:
        return None  # Can't check, allow (engine may be empty)

    if not response.best_bid or not response.best_ask:
        return None  # Empty book, skip check

    best_bid = Decimal(response.best_bid)
    best_ask = Decimal(response.best_ask)
    mid_price = (best_bid + best_ask) / 2

    if mid_price == 0:
        return None

    deviation = abs(price - mid_price) / mid_price
    if deviation > MARKET_SANITY_THRESHOLD:
        return (
            f"Price {price} is {deviation:.1%} from mid-price {mid_price}. "
            f"Max allowed deviation is {MARKET_SANITY_THRESHOLD:.0%}."
        )
    return None


class RateLimiter:
    """Sliding-window rate limiter."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: deque[float] = deque()

    def check(self) -> bool:
        """Return True if request is allowed, False if rate limited."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
        if len(self._timestamps) >= self.max_requests:
            return False
        self._timestamps.append(now)
        return True

    def reset(self) -> None:
        self._timestamps.clear()
