from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, field_validator


class OrderInput(BaseModel, strict=True):
    """Validated order input. All financial amounts use Decimal for precision."""

    price: Decimal
    quantity: Decimal

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Price must be positive")
        if v.as_tuple().exponent < -2:
            raise ValueError("Price allows max 2 decimal places")
        return v

    @field_validator("quantity")
    @classmethod
    def quantity_in_bounds(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Quantity must be positive")
        if v > Decimal("1000"):
            raise ValueError("Max 1000 ETH per order")
        if v.as_tuple().exponent < -8:
            raise ValueError("Quantity allows max 8 decimal places")
        return v
