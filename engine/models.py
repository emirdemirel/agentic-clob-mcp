from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class Side(Enum):
    BUY = 0
    SELL = 1


class OrderStatus(Enum):
    OPEN = 0
    PARTIALLY_FILLED = 1
    FILLED = 2
    CANCELLED = 3


@dataclass
class Order:
    client_order_id: str
    side: Side
    price: Decimal
    original_quantity: Decimal
    remaining_quantity: Decimal
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: OrderStatus = OrderStatus.OPEN
    created_at_ns: int = field(default_factory=time.time_ns)

    @property
    def filled_quantity(self) -> Decimal:
        return self.original_quantity - self.remaining_quantity


@dataclass
class Trade:
    price: Decimal
    quantity: Decimal
    maker_order_id: str
    taker_order_id: str
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp_ns: int = field(default_factory=time.time_ns)
