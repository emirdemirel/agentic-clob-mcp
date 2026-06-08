# Agentic CLOB Trading Agent

A simplified, deterministic Central Limit Order Book (CLOB) engine exposed via gRPC, wrapped with an MCP bridge for Claude-powered natural language trading, and validated by a multi-run evaluation harness.

**Trading Pair:** ETH/USDC

## Architecture

```
┌─────────────┐     ┌─────────────────┐     ┌──────────────┐
│  LLM Agent  │────▶│   MCP Bridge    │────▶│ CLOB Engine  │
│ (Claude +   │     │ (Streamable-HTTP│     │ (gRPC)       │
│  pydantic-  │     │  4 tools +      │     │ Price-time   │
│  ai)        │◀────│  3 resources)   │◀────│ priority     │
│             │     │  :8001          │     │ matching     │
│  CLI        │     │                 │     │  :50051      │
└─────────────┘     └─────────────────┘     └──────────────┘
                            │
                    ┌───────┴────────┐
                    │  Guardrails    │
                    │  - Schema      │
                    │  - Risk limits │
                    │  - Market san. │
                    │  - Rate limit  │
                    │  - Injection   │
                    └────────────────┘
```

| Layer          | Role                                    | Protocol         | Port           |
|----------------|-----------------------------------------|------------------|----------------|
| Trading Engine | In-memory CLOB, price-time matching     | gRPC (protobuf)  | localhost:50051|
| MCP Bridge     | Wraps gRPC in MCP tools and resources   | Streamable HTTP  | localhost:8001 |
| LLM Agent      | Claude natural language + guardrails    | pydantic-ai      | CLI            |
| Eval Harness   | Scenario bank, multi-run metrics        | pytest + runner  | CLI            |

## LLM model

We have chosen Claude API and ```anthropic:claude-sonnet-4-20250514``` LLM model.

## Quick Start

### Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- `ANTHROPIC_API_KEY` environment variable set

### One-Command Setup & Run

```bash
# Install dependencies
make install

# Run everything (engine + bridge + agent)
make run-all
```

### Step-by-Step (3 terminals)

```bash
# Terminal 1: Start engine
make run-engine

# Terminal 2: Start MCP bridge
make run-bridge

# Terminal 3: Start interactive agent
export ANTHROPIC_API_KEY=your-key-here
make run-agent
```

### Run Tests

```bash
make test
```

### Run Evaluation

```bash
export ANTHROPIC_API_KEY=your-key-here
make eval
```

For multi-run eval, run the eval command as follows (for example with N=5 runs)

```
EVAL_RUNS=5 make eval
```

At the end of the evaluation, the harness prints a structured report to stdout and writes a full JSON report to `eval_report.json`.
Please note that multi-run eval takes a few minutes to complete. Results are aggregated across runs when reporting final metrics.
For a deep dive on the evaluation framework, see [EVALUATION.md](EVALUATION.md).

## Project Structure

```
agentic-clob-mcp/
├── protos/orderbook.proto .............. gRPC service definition
├── engine/
│   ├── models.py ...................... Order, Trade, Side, OrderStatus
│   ├── orderbook.py .................. CLOB with price-time priority
│   ├── server.py ..................... gRPC server (sync, thread-safe)
│   ├── orderbook_pb2.py .............. Generated protobuf
│   └── orderbook_pb2_grpc.py ......... Generated gRPC stubs
├── bridge/
│   └── mcp_server.py ................. MCP server wrapping gRPC client
├── agent/
│   ├── schemas.py .................... Pydantic models for orders
│   ├── guardrails.py ................. Deterministic validation rules
│   └── trading_agent.py .............. pydantic-ai agent + MCP toolset
├── evaluation/
│   ├── scenarios.py .................. 24-scenario test bank
│   ├── harness.py .................... Multi-run evaluation runner
│   └── metrics.py .................... Metric computation + reporting
├── tests/
│   ├── test_orderbook.py ............. Order book unit tests (23 tests)
│   ├── test_matching.py .............. Matching engine tests (9 tests)
│   └── test_guardrails.py ............ Guardrail validation tests (20 tests)
├── pyproject.toml .................... Dependencies and config
├── Makefile .......................... One-command build/run/test/eval
└── README.md
```

## Design Decisions

| Decision | Chosen | Alternative | Why |
|----------|--------|-------------|-----|
| Matching algo | Price-time priority | Pro-rata | Standard for spot CLOB, simpler, fair, deterministic |
| Price type | `decimal.Decimal` from string | `float` | Financial precision, no rounding errors |
| Thread safety | `threading.RLock` | `asyncio.Lock` | Sync gRPC with ThreadPoolExecutor; RLock for nested calls |
| MCP transport | streamable-http | stdio | Multiple concurrent clients, production-ready |
| Buy/sell tools | Separate `place_limit_buy`/`place_limit_sell` | Single `place_order` | Reduces LLM ambiguity |
| Agent framework | pydantic-ai | LangChain | Type-safe, native MCP, cleaner API |
| Eval approach | Multi-run with pass@k/pass^k | Single-run | Handles LLM non-determinism statistically |
| Guardrails | Deterministic Pydantic + rules | LLM-as-judge | Zero false negatives for defined invariants |

## Component Deep Dives

### Trading Engine
- **Matching:** Price-time priority. Incoming orders match against the best resting price first, and within a price level, the earliest order (FIFO). Trades always execute at the maker's price.
- **Thread Safety:** `threading.RLock` guards all order book mutations. Safe for concurrent gRPC requests via `ThreadPoolExecutor`.
- **Idempotency:** `client_order_id` deduplication prevents duplicate orders on gRPC retries.
- **Data Structures:** `SortedDict` for O(log n) insert/delete with O(1) best-price peek.

### MCP Bridge
- **7 Tools:** `place_limit_buy`, `place_limit_sell`, `cancel_order`, `get_order_status`, `get_orderbook`, `get_spread`, `get_recent_trades`
- **3 Resources:** `orderbook://ETH-USDC/snapshot`, `orderbook://ETH-USDC/spread`, `orderbook://ETH-USDC/trades/recent` (thin wrappers over tools for MCP spec compliance)
- **Token optimization:** Arrays-of-arrays format, compact JSON, pre-computed spread

### Guardrails (5 layers)
1. **Prompt injection detection:** Regex patterns for SYSTEM/IGNORE/OVERRIDE/FORGET/DISREGARD — checked on every string parameter before any processing
2. **Rate limiting:** Sliding window, 10 order requests/minute
3. **Schema validation:** Pydantic v2 strict mode — positive price (max 2dp), positive quantity (max 8dp, max 1000 ETH)
4. **Market sanity:** Reject orders with price >10% from current mid-price
5. **gRPC server validation:** Final price > 0, quantity > 0 at the engine level

### Evaluation Metrics

The evaluation harness measures end-to-end agent quality across **24 scenarios** in **5 dimensions**. Each scenario runs **N independent times** (default `N=3`, configurable via `EVAL_RUNS`) against a seeded order book (`seed=42`) for reproducibility.

#### Methodology

LLM outputs are non-deterministic — a single run can pass or fail by chance. Multi-run statistical evaluation accounts for this. All pass/fail decisions use **deterministic rule-based scoring** (tool name, argument values, guardrail rejection), not LLM-as-judge, so results are unambiguous and reproducible.

Three core reliability metrics appear across dimensions:

- **pass@k** (capability ceiling) — P(at least 1 success in k runs). Shows whether the agent is *ever* capable of the task.
- **pass^k** (reliability floor) — P(all k runs succeed). The production-relevant bar; a trading agent must be consistently correct, not occasionally lucky.
- **Behavioral consistency** — fraction of runs with an identical tool-call sequence. Measures determinism of the agent's plan, independent of pass/fail.

These metrics are borrowed from code-generation evaluation literature (Chen et al., 2021) and implemented in `evaluation/metrics.py` via `compute_aggregate_metrics`.

#### 1. Trade Execution Accuracy (8 scenarios)

- **What it measures:** Whether the agent selects the correct MCP tool and passes the right arguments (price, quantity, order ID) for natural-language trading instructions.
- **Metrics:** Tool selection rate, pass@k, pass^k, behavioral consistency.
- **Target:** >95% tool selection rate; pass@k >98%; pass^k >85%.
- **Why it matters:** Wrong tool or wrong arguments means a wrong trade. This is the baseline correctness dimension — everything else is irrelevant if the agent cannot execute the right action.

#### 2. Latency (all runs)

- **What it measures:** End-to-end response time from user prompt to final agent output, across every scenario run.
- **Metrics:** P50 (median), P95 (tail), P99 (extreme tail), mean ± std dev, min/max range.
- **Target:** P50 < 2s; P95 < 5s.
- **Why it matters:** Tail latency, not the average, defines user-facing responsiveness. Percentiles expose outliers that a mean hides — a trading agent that is fast 95% of the time but stalls for 30s on the rest is unusable in practice.

#### 3. Safety / Guardrail Effectiveness (6 scenarios)

- **What it measures:** Whether unsafe orders (negative price, zero quantity, quantity exceeding limits, price far from market) are blocked by the 5-layer guardrail pipeline before reaching the engine.
- **Metrics:** Safety rejection rate, false-negative rate, pass@k, pass^k.
- **Target:** 100% rejection rate; 0% false-negative rate.
- **Why it matters:** A single unsafe order slipping through is a critical failure. False-negative rate is tracked explicitly because "mostly safe" is not acceptable for a system that moves money.

#### 4. Prompt Robustness / Injection Resistance (6 scenarios)

- **What it measures:** Whether the agent resists prompt-injection attacks (IGNORE instructions, SYSTEM overrides, persona switches, rule-forgetting attempts) and refuses to place unauthorized orders.
- **Metrics:** Injection block rate, pass@k, pass^k.
- **Target:** 100% blocked.
- **Why it matters:** LLM agents are exposed to adversarial input in any real deployment. The agent must never be coerced into placing trades the user did not intend.

#### 5. Simulation-Based Testing (4 scenarios)

- **What it measures:** Multi-step workflows that mirror real usage — read the order book, then place an order; place a buy, then check status; place and cancel; market-making with paired buy/sell.
- **Metrics:** Multi-step completion rate, tool-sequence accuracy, behavioral consistency, pass@k, pass^k.
- **Target:** >90% multi-step completion.
- **Why it matters:** Real trading workflows are multi-step. Correct tool selection on a single instruction is necessary but not sufficient — the agent must maintain context and call tools in the right order across a conversation.

#### Reading `eval_report.json`

After `make eval`, the JSON report keys map directly to the dimensions above (produced by `compute_aggregate_metrics` in `evaluation/metrics.py`):

| JSON key | Dimension |
|----------|-----------|
| `exec_accuracy` | Trade Execution Accuracy |
| `latency` | Latency |
| `safety` | Safety / Guardrails |
| `injection_resistance` | Prompt Robustness |
| `simulation` | Simulation-Based Testing |
| `overall` | Cross-dimension aggregate (total pass rate, pass@k, pass^k, consistency) |

For the full scenario bank, guardrail pipeline details, seeding logic, and sample results, see [EVALUATION.md](EVALUATION.md).

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `ANTHROPIC_API_KEY` | Yes | - | Claude API key |
| `GRPC_HOST` | No | `localhost:50051` | Engine address |
| `MCP_HOST` | No | `http://localhost:8000/mcp` | Bridge address |
| `EVAL_RUNS` | No | `3` | Runs per evaluation scenario |

## Trade-offs & Future Work

| Trade-off | Current | With More Time |
|-----------|---------|----------------|
| Order types | Limit only | Market, stop-loss, OCO |
| Persistence | In-memory | SQLite or Redis |
| Real-time updates | Polling via resources | gRPC server-side streaming |
| Auth | None (single-user) | API keys, session tokens |
| Concurrency | Sync gRPC (ThreadPool) | Async stack for throughput |
| Error recovery | Structured error mapping | Retry with exponential backoff |
