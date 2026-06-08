from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Side(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    BUY: _ClassVar[Side]
    SELL: _ClassVar[Side]

class OrderStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    OPEN: _ClassVar[OrderStatus]
    PARTIALLY_FILLED: _ClassVar[OrderStatus]
    FILLED: _ClassVar[OrderStatus]
    CANCELLED: _ClassVar[OrderStatus]
BUY: Side
SELL: Side
OPEN: OrderStatus
PARTIALLY_FILLED: OrderStatus
FILLED: OrderStatus
CANCELLED: OrderStatus

class PlaceOrderRequest(_message.Message):
    __slots__ = ("client_order_id", "side", "price", "quantity")
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    client_order_id: str
    side: Side
    price: str
    quantity: str
    def __init__(self, client_order_id: _Optional[str] = ..., side: _Optional[_Union[Side, str]] = ..., price: _Optional[str] = ..., quantity: _Optional[str] = ...) -> None: ...

class PlaceOrderResponse(_message.Message):
    __slots__ = ("order_id", "status", "remaining_quantity", "fills")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    REMAINING_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    FILLS_FIELD_NUMBER: _ClassVar[int]
    order_id: str
    status: OrderStatus
    remaining_quantity: str
    fills: _containers.RepeatedCompositeFieldContainer[Trade]
    def __init__(self, order_id: _Optional[str] = ..., status: _Optional[_Union[OrderStatus, str]] = ..., remaining_quantity: _Optional[str] = ..., fills: _Optional[_Iterable[_Union[Trade, _Mapping]]] = ...) -> None: ...

class Trade(_message.Message):
    __slots__ = ("trade_id", "price", "quantity", "maker_order_id", "taker_order_id", "timestamp_ns")
    TRADE_ID_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    MAKER_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    TAKER_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_NS_FIELD_NUMBER: _ClassVar[int]
    trade_id: str
    price: str
    quantity: str
    maker_order_id: str
    taker_order_id: str
    timestamp_ns: int
    def __init__(self, trade_id: _Optional[str] = ..., price: _Optional[str] = ..., quantity: _Optional[str] = ..., maker_order_id: _Optional[str] = ..., taker_order_id: _Optional[str] = ..., timestamp_ns: _Optional[int] = ...) -> None: ...

class CancelOrderRequest(_message.Message):
    __slots__ = ("order_id",)
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    order_id: str
    def __init__(self, order_id: _Optional[str] = ...) -> None: ...

class CancelOrderResponse(_message.Message):
    __slots__ = ("success", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ...) -> None: ...

class GetOrderBookRequest(_message.Message):
    __slots__ = ("depth",)
    DEPTH_FIELD_NUMBER: _ClassVar[int]
    depth: int
    def __init__(self, depth: _Optional[int] = ...) -> None: ...

class PriceLevel(_message.Message):
    __slots__ = ("price", "total_quantity", "order_count")
    PRICE_FIELD_NUMBER: _ClassVar[int]
    TOTAL_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    ORDER_COUNT_FIELD_NUMBER: _ClassVar[int]
    price: str
    total_quantity: str
    order_count: int
    def __init__(self, price: _Optional[str] = ..., total_quantity: _Optional[str] = ..., order_count: _Optional[int] = ...) -> None: ...

class OrderBookSnapshot(_message.Message):
    __slots__ = ("pair", "bids", "asks", "best_bid", "best_ask", "spread", "timestamp_ns")
    PAIR_FIELD_NUMBER: _ClassVar[int]
    BIDS_FIELD_NUMBER: _ClassVar[int]
    ASKS_FIELD_NUMBER: _ClassVar[int]
    BEST_BID_FIELD_NUMBER: _ClassVar[int]
    BEST_ASK_FIELD_NUMBER: _ClassVar[int]
    SPREAD_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_NS_FIELD_NUMBER: _ClassVar[int]
    pair: str
    bids: _containers.RepeatedCompositeFieldContainer[PriceLevel]
    asks: _containers.RepeatedCompositeFieldContainer[PriceLevel]
    best_bid: str
    best_ask: str
    spread: str
    timestamp_ns: int
    def __init__(self, pair: _Optional[str] = ..., bids: _Optional[_Iterable[_Union[PriceLevel, _Mapping]]] = ..., asks: _Optional[_Iterable[_Union[PriceLevel, _Mapping]]] = ..., best_bid: _Optional[str] = ..., best_ask: _Optional[str] = ..., spread: _Optional[str] = ..., timestamp_ns: _Optional[int] = ...) -> None: ...

class GetOrderRequest(_message.Message):
    __slots__ = ("order_id",)
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    order_id: str
    def __init__(self, order_id: _Optional[str] = ...) -> None: ...

class OrderResponse(_message.Message):
    __slots__ = ("order_id", "client_order_id", "side", "price", "original_quantity", "remaining_quantity", "filled_quantity", "status", "created_at_ns")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    ORIGINAL_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    REMAINING_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    FILLED_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_NS_FIELD_NUMBER: _ClassVar[int]
    order_id: str
    client_order_id: str
    side: Side
    price: str
    original_quantity: str
    remaining_quantity: str
    filled_quantity: str
    status: OrderStatus
    created_at_ns: int
    def __init__(self, order_id: _Optional[str] = ..., client_order_id: _Optional[str] = ..., side: _Optional[_Union[Side, str]] = ..., price: _Optional[str] = ..., original_quantity: _Optional[str] = ..., remaining_quantity: _Optional[str] = ..., filled_quantity: _Optional[str] = ..., status: _Optional[_Union[OrderStatus, str]] = ..., created_at_ns: _Optional[int] = ...) -> None: ...

class GetTradeHistoryRequest(_message.Message):
    __slots__ = ("limit",)
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    limit: int
    def __init__(self, limit: _Optional[int] = ...) -> None: ...

class TradeHistoryResponse(_message.Message):
    __slots__ = ("trades",)
    TRADES_FIELD_NUMBER: _ClassVar[int]
    trades: _containers.RepeatedCompositeFieldContainer[Trade]
    def __init__(self, trades: _Optional[_Iterable[_Union[Trade, _Mapping]]] = ...) -> None: ...
