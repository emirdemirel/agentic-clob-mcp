.PHONY: proto install test run-engine run-bridge run-agent run-all eval clean

install:
	uv sync

proto:
	uv run python -m grpc_tools.protoc -I protos \
		--python_out=engine --pyi_out=engine --grpc_python_out=engine \
		protos/orderbook.proto

test: proto
	uv run pytest tests/ -v

run-engine: proto
	uv run python -m engine.server

run-bridge:
	uv run python -m bridge.mcp_server

run-agent:
	uv run python -m agent.trading_agent

# Start engine + bridge in background, then launch agent in foreground.
# On exit (Ctrl-C), kill the background processes.
run-all: proto
	@echo "Starting engine..."
	@uv run python -m engine.server &
	@ENGINE_PID=$$!; \
	sleep 2; \
	echo "Starting MCP bridge..."; \
	uv run python -m bridge.mcp_server & \
	BRIDGE_PID=$$!; \
	sleep 2; \
	echo "Starting agent (Ctrl-C to quit all)..."; \
	uv run python -m agent.trading_agent; \
	kill $$ENGINE_PID $$BRIDGE_PID 2>/dev/null; \
	echo "All processes stopped."

eval: proto
	@echo "Starting engine for evaluation..."
	@uv run python -m engine.server &
	@ENGINE_PID=$$!; \
	sleep 2; \
	echo "Starting MCP bridge..."; \
	uv run python -m bridge.mcp_server & \
	BRIDGE_PID=$$!; \
	sleep 2; \
	uv run python -m evaluation.harness; \
	kill $$ENGINE_PID $$BRIDGE_PID 2>/dev/null

clean:
	rm -f engine/orderbook_pb2.py engine/orderbook_pb2.pyi engine/orderbook_pb2_grpc.py
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
