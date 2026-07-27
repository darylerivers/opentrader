# OpenTrader V2 Architecture Plan

## Hardware Layer

```
┌─────────────────────────────────────────────────────────────┐
│                    Intel Platform (850W PSU)                 │
│                                                             │
│  ┌─────────────────────┐    ┌──────────────────────────┐   │
│  │  RTX 3070 (8GB)     │    │  RX 7900 GRE (16GB)      │   │
│  │  CUDA backend       │    │  ROCm backend            │   │
│  │  PCIe 3.0 x4 (chip) │    │  PCIe 4.0 x16 (CPU)     │   │
│  │  Role: ALL INFERENCE│    │  Role: GAMING + DESKTOP  │   │
│  └─────────┬───────────┘    └──────────────────────────┘   │
│            │                                                │
│  ┌─────────┴──────────────────────────────────────┐        │
│  │              llama-swap (:8080)                 │        │
│  │         Routes between models by demand         │        │
│  └─────────┬──────────────────────────────────────┘        │
│            │                                                │
│     ┌──────┴──────┐                                        │
│     ▼             ▼                                        │
│  ┌──────────┐  ┌──────────────┐                            │
│  │ Ollama   │  │ llama-server │                            │
│  │ :11434   │  │ :5801        │                            │
│  │ gemma    │  │ Qwythos 9B   │                            │
│  │ 11.9B    │  │ + LoRA       │                            │
│  └────┬─────┘  └──────┬───────┘                            │
│       │               │                                    │
│       ▼               ▼                                    │
│  ┌────────────┐  ┌──────────────┐                          │
│  │ OpenCode   │  │ OpenTrader   │                          │
│  │ Agent      │  │ Harness      │                          │
│  │ Framework  │  │ Trading Loop │                          │
│  └────────────┘  └──────────────┘                          │
│                                                             │
│  Time-sharing: Only ONE model loaded on 3070 at a time.     │
│  llama-swap hot-swaps by unloading idle model, loading      │
│  requested one (~15s swap time).                            │
└─────────────────────────────────────────────────────────────┘
```

### GPU Split

| GPU | VRAM | Backend | Role |
|-----|------|---------|------|
| RTX 3070 | 8GB | CUDA | ALL inference — agent models + trading models (time-shared) |
| RX 7900 | 16GB | ROCm | Gaming, desktop, training (when idle), 27B model if needed |

### 3070 Time-Sharing (via llama-swap)

| Mode | Model | VRAM | When |
|------|-------|------|------|
| Agent | gemma-agentic-32k (11.9B Q4) | 7.4GB + 0.5GB KV | OpenCode sessions |
| Trading | Qwythos-9B + Ptolemy-S3 LoRA | 5.5GB + 1.0GB KV | Harness running |
| Idle | Unloaded | 0GB | Neither active |

### 7900 Optional Inference

| Scenario | Model | VRAM |
|----------|-------|------|
| Gaming only | — | 0GB ML |
| Overnight training | Full pipeline | Up to 16GB |
| 27B experiment | qwen35-opus-distil:27b | 16GB (full card) |

---

## Port Layout

```
:11434  Ollama (RTX 3070, CUDA)       → OpenCode agent models
:5801   llama-server (RX 7900, ROCm)  → OpenTrader harness inference
:8080   llama-swap                    → Routes to :5801 (future: :11434 too)
:8092   MCP Server (OpenTrader)       → Economics, state tools
:8097   Dashboard (OpenTrader)        → Web UI
```

---

## Software Stack

### Layer 1: Inference Servers

```
Ollama (Port :11434, GPU 0 = RTX 3070)
├── gemma-agentic-32k (11.9B, Q4_K_M, 7.4GB)
│   ├── Capabilities: completion, tools, thinking
│   ├── Context: 32K
│   └── Role: OpenCode supervisor, builder, manager
│
└── Future: qwen35-opus-distil:27b (if 3070 upgrades or 7900 runs it)

llama-server (Port :5801, GPU 1 = RX 7900)
├── Model: Qwythos-9B Q4_K_M + Ptolemy-S3 LoRA
├── Context: 16K
├── KV: q4_0 (flash attention on)
├── Role: Trading debate engine (Bull/Bear/Risk agents)
│
└── llama-swap (:8080) → Routes to :5801
    └── Config: ~/llama-swap/config.yaml
```

### Layer 2: Agent Framework (OpenCode)

```
Supervisor (gemma-agentic-32k via :11434)
├── Steps: 25
├── Tools: bash, read, write, edit, glob, grep, task, skill
├── MCP: codesage, context7, playwright, huggingface
│
├── Builder (gemma-agentic-32k)
│   ├── Steps: 40
│   └── Role: Code changes, bug fixes, feature development
│
├── Manager (gemma-agentic-32k)
│   ├── Mode: subagent
│   └── Role: Architectural decisions, tradeoff analysis
│
├── Qwen-Worker (gemma-agentic-32k)
│   └── Mode: subagent, fast task execution
│
└── Modelfixer (gemma-agentic-32k)
    └── Role: LLM integration debugging
```

### Layer 3: Trading System (OpenTrader)

```
Harness Loop (harness.py, cycle ~11K)
├── 1. Signal Generation
│   ├── ADIR Debate Engine
│   │   ├── Bull Agent → long thesis
│   │   ├── Bear Agent → short thesis
│   │   └── Risk Agent → risk assessment
│   ├── News + arXiv + Social Sentiment context
│   └── Model: Qwythos-9B via llama-swap (:8080 → :5801)
│
├── 2. Portfolio Optimization
│   ├── Kelly sizing (fraction=0.35)
│   ├── Correlation-aware allocation
│   └── Per-symbol parameter optimization
│
├── 3. Risk Check
│   ├── Circuit breaker (5% drawdown)
│   ├── Position limits (max 5, 20% each)
│   ├── Stop-loss (4%) / Take-profit (8%)
│   └── Trailing stops (2% trail, 1.5% activation)
│
├── 4. Order Execution
│   ├── PaperExchange (synthetic bars)
│   ├── Kraken/Coinbase (via CCXT, paper settle)
│   ├── Finnhub stocks (US equities, paper settle)
│   └── IBKR (ib_insync, paper settle)
│
├── 5. Post-Cycle
│   ├── Flash Training (during HOLD streaks)
│   ├── Reflection (trade outcome logging)
│   ├── State Persistence (JSON files)
│   └── Agent Scoring (Bull/Bear accuracy)
│
└── 6. Periodic (every REVIEW_HOURS)
    ├── MoT Coordinator (strategy review)
    ├── Coach Agent (high-level guidance)
    ├── Training Scheduler (when to fine-tune)
    └── Adapter Registry (LoRA lifecycle)
```

### Layer 4: Data & Storage

```
State Files (data/)
├── paper_state.json        → Cycle, cash, positions, P&L
├── high_level_state.json   → Regime, confidence, posture
├── agent_state.json        → Signal history (500 entries)
├── health.json             → Process status
├── connections.json        → API keys, service config
├── reflection_log.json     → Trade outcome analysis
├── agent_scores.json       → Bull/Bear accuracy
└── coach_report.json       → Strategic guidance

Caches (data/)
├── price_cache.db          → SQLite price cache
├── alt_data_cache.db       → Alternative data
├── ticker_industry_cache.db → Sector mappings
├── arxiv_cache.json        → Research papers
├── news_cache.json         → News articles
└── social_cache.json       → Reddit/Twitter sentiment

Training Data (data/training/)
├── training_data.jsonl     → Combined examples
├── dpo_training_data.jsonl → Preference pairs
├── real_patterns.jsonl     → Successful trade patterns
└── synthetic_scenarios.jsonl → Generated scenarios

Models (data/models/finetune/)
└── Ptolemy-S3/             → LoRA adapter
    └── adapter_model.safetensors

History (data/history_archive_100k/)
└── 39K+ archived cycles for training
```

---

## Known Issues & Fix Priority

| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| 1 | P0 | MCP server (:8092) down — `Connection refused` | Start with `setsid python3 mcp_server.py --port 8092 &` |
| 2 | P0 | Stuck in HOLD regime (confidence 0.01, 12K cycles) | Check debate engine output, verify model on :5801 responding |
| 3 | P1 | Asset allocator scoping bug `cannot access local variable 'prices'` | Fix in `risk/asset_allocator.py` |
| 4 | P1 | Stale port in `connections.json` (5805 → 8080, 8098 → 8097) | Update connections.json |
| 5 | P1 | `harness_config.json` references :11434 but harness uses :8080 | Sync configs |
| 6 | P2 | Ollama KEEP_ALIVE=5m → model eviction mid-trade | Set to 2h (sudo needed) |
| 7 | P2 | Ollama KV_CACHE_TYPE not set → 2x VRAM | Set to q8_0 (sudo needed) |
| 8 | P3 | $100 capital → 14% round-trip fees on $5 positions | Increase to $500+ or reduce fee model |
| 9 | P3 | No PLAN.md or ROADMAP.md | This document replaces |

---

## GPU Evolution Path

```
Now:                RTX 3070 (agent) + RX 7900 (trading)
                    gemma 11.9B            Qwythos-9B

Phase 1 (today):    Agent → gemma-agentic-32k on 3070
                    Trading → Qwythos-9B + Ptolemy-S3 on 7900

Phase 2 (paper):    Prove profitable strategy
                    Training pipeline generates LoRA adapters
                    Debate engine switches to finetuned models

Phase 3 (live):     Live exchange (Kraken API keys)
                    Risk circuit breakers active
                    $100 → scale with profits

Phase 4 (scale):    Agent → qwen 27B on 7900 (16GB fits VRAM)
                    Trading → dedicated 3070 for inference
                    Or: cloud GPU for training, local for inference
```

---

## Config Sync Checklist

| File | Fix Needed |
|------|-----------|
| `~/.config/opencode/opencode.jsonc` | ✓ Clean — all agents → gemma-agentic-32k |
| `~/.opencode/opencode.json` | ✓ Synced with above |
| `/etc/systemd/system/ollama.service.d/override.conf` | ✗ Needs KV_CACHE_TYPE + KEEP_ALIVE |
| `~/llama-swap/config.yaml` | ✗ Not configured |
| `~/opentrader/data/connections.json` | ✗ Ports stale (5805→8080, 8098→8097) |
| `~/opentrader/config/harness_config.json` | ✗ llama_host wrong |
| `~/opentrader/risk/manager.py` | ✓ RiskConfig valid for $100 |
| `~/opentrader/risk/asset_allocator.py` | ✗ Scoping bug |
