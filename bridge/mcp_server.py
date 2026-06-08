from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from decimal import Decimal

import grpc
from mcp.server.fastmcp import FastMCP

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "engine"))

import orderbook_pb2 as pb2
import orderbook_pb2_grpc as pb2_grpc

from agent.guardrails import RateLimiter, check_market_sanity, check_prompt_injection, validate_order

MCP_PORT = int(os.environ.get("MCP_PORT", "8000"))

mcp = FastMCP(
    "Agentic CLOB Trading Bridge",
    instructions=(
        "You are a trading assistant for the ETH/USDC spot market. "
        "Always read the order book before placing orders. "
        "Never place orders without the user specifying both price and quantity. "
        "All prices are in USDC. All quantities are in ETH."
    ),
    host="127.0.0.1",
    port=MCP_PORT,
    json_response=True,
)

GRPC_HOST = os.environ.get("GRPC_HOST", "localhost:50051")
channel = grpc.insecure_channel(GRPC_HOST)
stub = pb2_grpc.OrderBookServiceStub(channel)

rate_limiter = RateLimiter(max_requests=10, window_seconds=60)


def _grpc_call(fn, request):
    """Wrap gRPC stub calls with timeout and error mapping."""
    try:
        return fn(request, timeout=5)
    except grpc.RpcError as e:
        code = e.code()
        if code == grpc.StatusCode.UNAVAILABLE:
            return {"error": "engine_unavailable", "message": "Trading engine not reachable."}
        elif code == grpc.StatusCode.INVALID_ARGUMENT:
            return {"error": "invalid_input", "message": e.details()}
        elif code == grpc.StatusCode.NOT_FOUND:
            return {"error": "not_found", "message": e.details()}
        else:
            return {"error": "engine_error", "message": f"Unexpected: {code.name}"}


def _format_fills(fills) -> list[dict]:
    return [
        {"trade_id": f.trade_id, "price": f.price, "qty": f.quantity}
        for f in fills
    ]


@mcp.tool()
async def place_limit_buy(
    price: str, quantity: str, client_order_id: str | None = None
) -> str:
    """Place a limit buy order on ETH/USDC.

    Args:
        price: Buy price in USDC (e.g., "3450.50"). Must be a valid positive decimal.
        quantity: Amount of ETH to buy (e.g., "1.5"). Must be positive, max 1000.
        client_order_id: Optional idempotency key. Auto-generated if omitted.

    Returns: JSON with order_id, status, remaining quantity, and any immediate fills.
    """
    for field_val in [price, quantity, client_order_id or ""]:
        injection = check_prompt_injection(field_val)
        if injection:
            return json.dumps({"error": "rejected", "message": injection})

    if not rate_limiter.check():
        return json.dumps({"error": "rate_limited", "message": "Max 10 orders per minute. Try again shortly."})

    try:
        validated = validate_order(price, quantity)
    except (ValueError, Exception) as e:
        return json.dumps({"error": "validation_failed", "message": str(e)})

    sanity = await check_market_sanity(validated.price, "BUY", stub)
    if sanity:
        return json.dumps({"error": "market_sanity", "message": sanity})

    request = pb2.PlaceOrderRequest(
        client_order_id=client_order_id or str(uuid.uuid4()),
        side=pb2.BUY,
        price=str(validated.price),
        quantity=str(validated.quantity),
    )

    response = await asyncio.to_thread(_grpc_call, stub.PlaceOrder, request)
    if isinstance(response, dict):
        return json.dumps(response)

    return json.dumps({
        "order_id": response.order_id,
        "status": pb2.OrderStatus.Name(response.status),
        "remaining": response.remaining_quantity,
        "fills": _format_fills(response.fills),
    })


@mcp.tool()
async def place_limit_sell(
    price: str, quantity: str, client_order_id: str | None = None
) -> str:
    """Place a limit sell order on ETH/USDC.

    Args:
        price: Sell price in USDC (e.g., "3500.00"). Must be a valid positive decimal.
        quantity: Amount of ETH to sell (e.g., "2.0"). Must be positive, max 1000.
        client_order_id: Optional idempotency key. Auto-generated if omitted.

    Returns: JSON with order_id, status, remaining quantity, and any immediate fills.
    """
    for field_val in [price, quantity, client_order_id or ""]:
        injection = check_prompt_injection(field_val)
        if injection:
            return json.dumps({"error": "rejected", "message": injection})

    if not rate_limiter.check():
        return json.dumps({"error": "rate_limited", "message": "Max 10 orders per minute. Try again shortly."})

    try:
        validated = validate_order(price, quantity)
    except (ValueError, Exception) as e:
        return json.dumps({"error": "validation_failed", "message": str(e)})

    sanity = await check_market_sanity(validated.price, "SELL", stub)
    if sanity:
        return json.dumps({"error": "market_sanity", "message": sanity})

    request = pb2.PlaceOrderRequest(
        client_order_id=client_order_id or str(uuid.uuid4()),
        side=pb2.SELL,
        price=str(validated.price),
        quantity=str(validated.quantity),
    )

    response = await asyncio.to_thread(_grpc_call, stub.PlaceOrder, request)
    if isinstance(response, dict):
        return json.dumps(response)

    return json.dumps({
        "order_id": response.order_id,
        "status": pb2.OrderStatus.Name(response.status),
        "remaining": response.remaining_quantity,
        "fills": _format_fills(response.fills),
    })


@mcp.tool()
async def cancel_order(order_id: str) -> str:
    """Cancel an open order by its order ID.

    Args:
        order_id: The server-generated order UUID to cancel.

    Returns: JSON with success status and message.
    """
    injection = check_prompt_injection(order_id)
    if injection:
        return json.dumps({"error": "rejected", "message": injection})

    request = pb2.CancelOrderRequest(order_id=order_id)
    response = await asyncio.to_thread(_grpc_call, stub.CancelOrder, request)
    if isinstance(response, dict):
        return json.dumps(response)

    return json.dumps({"success": response.success, "message": response.message})


@mcp.tool()
async def get_order_status(order_id: str) -> str:
    """Get the current status and details of an order.

    Args:
        order_id: The server-generated order UUID.

    Returns: JSON with full order details including status, filled quantity, etc.
    """
    injection = check_prompt_injection(order_id)
    if injection:
        return json.dumps({"error": "rejected", "message": injection})

    request = pb2.GetOrderRequest(order_id=order_id)
    response = await asyncio.to_thread(_grpc_call, stub.GetOrder, request)
    if isinstance(response, dict):
        return json.dumps(response)

    return json.dumps({
        "order_id": response.order_id,
        "client_order_id": response.client_order_id,
        "side": pb2.Side.Name(response.side),
        "price": response.price,
        "original_qty": response.original_quantity,
        "remaining_qty": response.remaining_quantity,
        "filled_qty": response.filled_quantity,
        "status": pb2.OrderStatus.Name(response.status),
    })


@mcp.tool()
async def get_orderbook(depth: int = 10) -> str:
    """Get the current ETH/USDC order book with top bid/ask price levels.

    Args:
        depth: Number of price levels per side to return (default 10).

    Returns: JSON with bids, asks (as [price, qty, count] arrays), best_bid, best_ask, and spread.
    """
    response = await asyncio.to_thread(
        _grpc_call, stub.GetOrderBook, pb2.GetOrderBookRequest(depth=depth)
    )
    if isinstance(response, dict):
        return json.dumps(response)

    bids = [[lvl.price, lvl.total_quantity, lvl.order_count] for lvl in response.bids]
    asks = [[lvl.price, lvl.total_quantity, lvl.order_count] for lvl in response.asks]

    return json.dumps({
        "pair": response.pair,
        "bids": bids,
        "asks": asks,
        "best_bid": response.best_bid,
        "best_ask": response.best_ask,
        "spread": response.spread,
    })


@mcp.tool()
async def get_spread() -> str:
    """Get the current best bid, best ask, mid price, and spread for ETH/USDC.

    Returns: JSON with bid, ask, mid, and spread values.
    """
    response = await asyncio.to_thread(
        _grpc_call, stub.GetOrderBook, pb2.GetOrderBookRequest(depth=1)
    )
    if isinstance(response, dict):
        return json.dumps(response)

    mid = ""
    if response.best_bid and response.best_ask:
        mid = str((Decimal(response.best_bid) + Decimal(response.best_ask)) / 2)

    return json.dumps({
        "bid": response.best_bid,
        "ask": response.best_ask,
        "mid": mid,
        "spread": response.spread,
    })


@mcp.tool()
async def get_recent_trades(limit: int = 20) -> str:
    """Get the most recent executed trades for ETH/USDC.

    Args:
        limit: Number of recent trades to return (default 20).

    Returns: JSON with trades as [price, quantity, timestamp_ns] arrays.
    """
    response = await asyncio.to_thread(
        _grpc_call, stub.GetTradeHistory, pb2.GetTradeHistoryRequest(limit=limit)
    )
    if isinstance(response, dict):
        return json.dumps(response)

    trades = [
        [t.price, t.quantity, t.timestamp_ns]
        for t in response.trades
    ]
    return json.dumps({"trades": trades})


# Keep resources for MCP spec compliance (accessible via MCP resource reads)
@mcp.resource("orderbook://ETH-USDC/snapshot")
async def orderbook_snapshot_resource() -> str:
    """Current ETH/USDC order book snapshot."""
    return await get_orderbook()


@mcp.resource("orderbook://ETH-USDC/spread")
async def spread_resource() -> str:
    """Current ETH/USDC spread."""
    return await get_spread()


@mcp.resource("orderbook://ETH-USDC/trades/recent")
async def recent_trades_resource() -> str:
    """Recent ETH/USDC trades."""
    return await get_recent_trades()


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
