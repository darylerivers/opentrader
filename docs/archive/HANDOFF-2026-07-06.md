# OPENTRADER — Trading Platform Handoff
**Date:** 2026-07-06 | **Cycle:** ~10,050 | **Portfolio:** ~$100,405 | **Uptime:** Stable

## RUNNING SERVICES (all ports localhost)

| Service | Port | Command |
|---------|------|---------|
| llama-server (Qwythos-9B) | 5809 | Manual start (see below) |
| llama-swap | 8080 | Auto-starts on boot |
| Harness | — | `run_harness.py` (via setsid) |
| Dashboard | 8097 | `dashboard.py --port 8097` (no --reload!) |

### Restart trading stack:
```bash
# 1. Kill everything
pkill -f "harness\.py|dashboard\.py"

# 2. Start llama-server
nohup /home/mrc/src/modelai-llama.cpp/build-wmma/bin/llama-server \
  --model /home/mrc/models/qwythos-9b-mtp/Qwythos-9B-Claude-Mythos-5-1M-MTP-Q4_K_M.gguf \
  --alias qwythos-9b-mtp --host 127.0.0.1 --port 5809 \
  --ctx-size 16384 --cache-type-k q8_0 --cache-type-v q8_0 \
  --jinja --parallel 4 --cont-batching --n-gpu-layers 99 \
  --threads 8 --batch-size 4096 --ubatch-size 1024 \
  --n-predict 2048 --reasoning off --spec-type none \
  > /tmp/llama.log 2>&1 &

# 3. Wait 15s for model to load, then start harness
cd /home/mrc/opentrader
setsid python3 run_harness.py --live --exchange kraken --stage 2 \
  --mot-force increase --max-daily-trades 500 --parallel-debate \
  --llama-host http://127.0.0.1:5809 </dev/null >>/tmp/harness_watch.log 2>&1 &
disown

# 4. Dashboard (NO --reload flag — causes crash loops)
setsid python3 /home/mrc/opentrader/dashboard.py --port 8097 \
  </dev/null >/tmp/dashboard.log 2>&1 &
disown
```

## WHAT'S RUNNING

- **Model**: Qwythos-9B (Q4_K_M, 5.5GB VRAM) on port 5809
- **GPU**: AMD RX 7900 XT (16GB VRAM), ROCm 6.3, gfx1100
- **Exchange**: Kraken (paper settlement, real prices)
- **Stage**: 2 (Crypto Basket: BTC, ETH, SOL)
- **Debate**: fast_debate (single composite call), no JSON response_format issues
- **Cycle time**: 15-22s (improved from 25-30s via caching + direct llama-server)
- **Win rate**: ~63%, Profit factor: ~2.6

## CRITICAL: DO NOT USE LLAMA-SWAP FOR 5809
The harness must point DIRECTLY to `--llama-host http://127.0.0.1:5809`.
llama-swap (port 8080) cannot route to the manually-started Qwythos.
If cycles run at 0.78s with 50% HOLD signals → llama-host is wrong.

## KEY FILES CHANGED TODAY

| File | Changes |
|------|---------|
| `harness.py` | Parallel debate flag, data caches, training lock, arxiv context, F&G metrics |
| `mot/agents/debate.py` | Parallel Bull+Bear mode, BEAR_SYSTEM_INDEPENDENT prompt |
| `mot/scoring.py` | Thread-safe save with lock, direct write (no atomic rename) |
| `data/arxiv.py` | NEW — fetches q-fin papers, LLM feature extraction, 24h cache |
| `training/train_scheduler.py` | NEW — decision engine for train-or-trade optimization |
| `dashboard.py` | F&G gauge, cycle_time_s fix, no-reload mode |
| `benchmark_models.py` | Added urllib import, --reasoning off for Qwythos |

## TRAINING (DO NOT RUN DURING TRADING)

Training needs VRAM. Must stop llama-server first:
```bash
# 1. Download model cache (ONE TIME — 3GB, ~10 min)
cd /home/mrc/opentrader
PYTHONPATH=/home/mrc/opentrader /home/mrc/rocm_venv/bin/python3 -c "
from training.finetune_cycle import run_finetune
run_finetune('/home/mrc/opentrader/data', dry_run=True)
"

# 2. Kill trading, train, restart
pkill -f "harness\.py|llama-server.*qwythos"
sleep 5
cd /home/mrc/opentrader
PYTHONPATH=/home/mrc/opentrader /home/mrc/rocm_venv/bin/python3 training/run_training.py
# Then restart llama-server + harness (see above)
```
- Training uses Unsloth + LoRA on `Qwen/Qwen2.5-7B-Instruct` (4-bit)
- Same architecture family as Qwythos-9B (Qwen 2.5) — LoRA adapter compatible
- Qwythos superseded gemma-4-e4b-it (better trading performance)
- ~31 examples available in `data/training/training_data.jsonl`
- First run: ~12 min (download model), cached: ~3 min
- Output: `data/models/finetune/Alpha-1/`
- Status: `data/training/finetune_status.json`

## RACE CONDITIONS FIXED
- **scoring.py**: Thread-safe save — multiple parallel debate threads write agent_scores safely
- **dashboard.py**: `--reload` flag causes uvicorn restart loops on file changes → REMOVED

## ARXIV INTEGRATION
- Fetches 5 latest q-fin papers daily → `data/arxiv_cache.json`
- Injected as context into debate engine
- Every 50 cycles: LLM extracts implementable trading rules → `data/feature_backlog.json`
- Current backlog: 3 features (entry filter, position sizing, market impact)

## OPTIMIZATIONS DONE
- Bars fetch: deduped (was 50+80, now single 80-bar fetch)
- Economics: cached per cycle (was 3 MCP calls, now 1)
- 4h bars: 15min TTL cache (was fresh every cycle)
- News cache: already per-cycle

## TODO / NEXT SESSION

1. **Run training** — download model first (dry_run to cache), then train
2. **Persist --llama-host :5809** — add to run_harness.py defaults or systemd unit
3. **Publish to HF/GitHub** — end of month (dataset, arxiv tool, debate engine)
4. **Social media parsing** — async background thread, feed sentiment to context
5. **Dashboard stability** — use systemd unit instead of setsid

## KNOWN BUGS (from 2026-07-09 audit)

### CRITICAL
- **report_risk.py crash**: `s.get("positions", {})` fails when positions is a list (StateManager stores list). Fix: handle both types.
- **report_risk.py stage**: `s.get("stage", "?")` reads nonexistent top-level key. Stage is at `models.stage`.
- **Training scheduler never runs**: Both arXiv extraction and training eval use `_last_arxiv_extract` guard. Arxiv resets it, starving training eval.
- **run_harness.py defaults to :8080**: Should be `:5809` (direct llama-server, not llama-swap).

### HIGH
- **News/arxiv cache not thread-safe**: `_news_cycle` gate has no lock. Parallel debate threads can duplicate fetches.
- **MCP `_cycle` resets on restart**: Never loaded from persisted state. Fills get wrong cycle numbers.
- **Dashboard `--reload` crash**: Respawns process, resetting all global state. Use `setsid` instead.
- **SELL scoring records wrong action**: Uses `signal.action` instead of `effective_action` when portfolio optimizer overrides.

### MEDIUM
- **Portfolio optimizer runs on HOLD cycles**: Wastes compute fetching prices and running optimization when all signals are HOLD.
- **No circuit breaker recovery**: Once tripped, harness stops permanently. Manual restart required.
- **Dashboard PVA cache**: New symbols don't appear in price curves until enough history accumulates.

## PORT MAP
- 5809: llama-server (Qwythos-9B, direct)
- 8080: llama-swap (routing proxy — DO NOT use for harness)
- 8092: MCP server (economics, state)
- 8097: Dashboard (no --reload!)
