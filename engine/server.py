from __future__ import annotations

import logging
import os
import signal
import sys
from concurrent import futures
from decimal import Decimal, InvalidOperation

import grpc

# Generated proto files use bare `import orderbook_pb2` so we need engine/ on sys.path
sys.path.insert(0, os.path.dirname(__file__))

import orderbook_pb2 as pb2
import orderbook_pb2_grpc as pb2_grpc

from engine.models import OrderStatus, Side
from engine.orderbook import OrderBook

logger = logging.getLogger(__name__)


class OrderBookServicer(pb2_grpc.OrderBookServiceServicer):
    def __init__(self) -> None:
        self.book = OrderBook()

    def PlaceOrder(self, request, context):
        try:
            price = Decimal(request.price)
            quantity = Decimal(request.quantity)
        except InvalidOperation:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Price and quantity must be valid decimal strings")
            return pb2.PlaceOrderResponse()

        if price <= 0:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Price must be positive")
            return pb2.PlaceOrderResponse()
        if quantity <= 0:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Quantity must be positive")
            return pb2.PlaceOrderResponse()

        side = Side.BUY if request.side == pb2.BUY else Side.SELL
        order, fills = self.book.place_order(
            client_order_id=request.client_order_id,
            side=side,
            price=price,
            quantity=quantity,
        )

        proto_fills = [
            pb2.Trade(
                trade_id=t.trade_id,
                price=str(t.price),
                quantity=str(t.quantity),
                maker_order_id=t.maker_order_id,
                taker_order_id=t.taker_order_id,
                timestamp_ns=t.timestamp_ns,
            )
            for t in fills
        ]

        return pb2.PlaceOrderResponse(
            order_id=order.order_id,
            status=order.status.value,
            remaining_quantity=str(order.remaining_quantity),
            fills=proto_fills,
        )

    def CancelOrder(self, request, context):
        success, message = self.book.cancel_order(request.order_id)
        if not success and "not found" in message.lower():
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(message)
        return pb2.CancelOrderResponse(success=success, message=message)

    def GetOrderBook(self, request, context):
        depth = request.depth if request.depth > 0 else 10
        snap = self.book.get_snapshot(depth=depth)

        bids = [
            pb2.PriceLevel(
                price=str(lvl.price),
                total_quantity=str(lvl.total_quantity),
                order_count=lvl.order_count,
            )
            for lvl in snap.bids
        ]
        asks = [
            pb2.PriceLevel(
                price=str(lvl.price),
                total_quantity=str(lvl.total_quantity),
                order_count=lvl.order_count,
            )
            for lvl in snap.asks
        ]

        return pb2.OrderBookSnapshot(
            pair=snap.pair,
            bids=bids,
            asks=asks,
            best_bid=str(snap.best_bid) if snap.best_bid is not None else "",
            best_ask=str(snap.best_ask) if snap.best_ask is not None else "",
            spread=str(snap.spread) if snap.spread is not None else "",
            timestamp_ns=snap.timestamp_ns,
        )

    def GetOrder(self, request, context):
        order = self.book.get_order(request.order_id)
        if order is None:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Order {request.order_id} not found")
            return pb2.OrderResponse()

        return pb2.OrderResponse(
            order_id=order.order_id,
            client_order_id=order.client_order_id,
            side=order.side.value,
            price=str(order.price),
            original_quantity=str(order.original_quantity),
            remaining_quantity=str(order.remaining_quantity),
            filled_quantity=str(order.filled_quantity),
            status=order.status.value,
            created_at_ns=order.created_at_ns,
        )

    def GetTradeHistory(self, request, context):
        limit = request.limit if request.limit > 0 else 20
        trades = self.book.get_recent_trades(limit=limit)

        proto_trades = [
            pb2.Trade(
                trade_id=t.trade_id,
                price=str(t.price),
                quantity=str(t.quantity),
                maker_order_id=t.maker_order_id,
                taker_order_id=t.taker_order_id,
                timestamp_ns=t.timestamp_ns,
            )
            for t in trades
        ]
        return pb2.TradeHistoryResponse(trades=proto_trades)


def serve(port: int = 50051) -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_OrderBookServiceServicer_to_server(OrderBookServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    logger.info("Trading engine listening on port %d", port)
    print(f"Trading engine listening on port {port}")

    def _shutdown(signum, frame):
        print("\nShutting down engine...")
        server.stop(grace=5)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    server.wait_for_termination()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    port = int(os.environ.get("GRPC_PORT", "50051"))
    serve(port)
