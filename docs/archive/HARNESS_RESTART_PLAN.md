# Harness Restart Plan — Wave 3 Activation

## Context

Wave 1 + Wave 3 source-code fixes are in place but the **running harness is a stale pre-fix binary** (PID 2208162, ~144min uptime). Symptoms:

- `Asset allocator failed: cannot access local variable 'prices'` every cycle (A1 bug NOT fixed in this process)
- Two-stage industry scout never fires — still picks `BTC/USDT`, `NVDA`, `MSFT` from old `TRADABLE_UNIVERSE`
- Stuck in coach-only loop since ~09:30, 0 trades in 8h, 17 cycles total
- `data/paper_state.json` corrupted/gone; backup exists at `data/paper_state.json.bak-1784232129` (Jul 16 15:02)

## Pre-flight (already verified — read-only)

- All Wave 1+3 fixes confirmed in source:
  - A1 prices fix: `harness.py:1772` (`prices = {}` at start of `run_cycle`, before allocator calls at 1968/2033)
  - A2 `_safe_parse_json`: `mot/agents/adir_debate.py:47`, called at 405/411/431
  - `--reset-portfolio` flag wired in argparse + `__init__`
  - T8 two-stage scout: `harness.py:1580-1654` (imports `mot.industry_map` + `data.alt_data_mcp`)
  - T6 `industry_map.py`: 49 industries / 545 tickers (exceeds spec)
  - T5 `data/alt_data_mcp.py`: 5 tools, integrated **in-process** via `harness.py:1583` (no HTTP :8092 roundtrip)
  - T6 `load_industry_alt_data()` has hardcoded fallback bindings at `mot/industry_map.py:228-264` — missing `config/industry_alt_data.yaml` is NON-CRITICAL (falls back to defaults)
  - T9 `.gitignore` hardened (`config/alt_data_keys.json`, `*.db` caches)
- llama-swap healthy on :8080 (PID 2144329)
- Dashboard on :8098 (PID 1271803)
- Backup `data/paper_state.json.bak-1784232129` exists (107KB, Jul 16 15:02)

## Execution steps (3 commands)

### Step 1 — Kill stale harness

```bash
kill 2208162 && sleep 3 && pgrep -af harness.py
```

Verify no `harness.py` PIDs remain before continuing. Frees GPU VRAM (~3GB).

### Step 2 — Restore paper state from backup

```bash
cp /home/mrc/opentrader/data/paper_state.json.bak-1784232129 /home/mrc/opentrader/data/paper_state.json
```

Preserves 4-5 SL/TP-guarded positions from prior session (MSFT/TSLA/AAPL/NVDA/BAC). They didn't execute due to the A1 bug, so portfolio is effectively $100 cash with stuck position entries. Do NOT add `--reset-portfolio` on restart — it would wipe this restored state.

### Step 3 — Restart with setsid (survives opencode session timeout)

```bash
cd /home/mrc/opentrader && setsid python3 harness.py \
  --exchange paper --stage 3 --cash 100 \
  --llama-host http://127.0.0.1:8080 \
  --max-cycles 0 --debate-mode adir --parallel-debate \
  --interval 10 --universe-focus 6 \
  > data/harness.log 2>&1 &
```

**Restraints:**
- No `--reset-portfolio` (preserves restored state)
- Do NOT touch `llama-swap` (PID 2144329 already loads Ptolemy-S3 LoRA correctly via `--alias ptolemy-s1`)
- Do NOT touch the smart-router config — model name is centralized in `config/harness_config.json`

## Verification gates (read-only, ~5-10 min after restart)

Run in order. Stop at first failure and consult failure table.

1. **Process alive**: `pgrep -af harness.py | grep -v grep` returns one PID
2. **No A1 prices bug**: `grep -c "Asset allocator failed: cannot access local variable 'prices'" data/harness.log` returns 0 within first 3 cycles
3. **Two-stage scout fired**: `grep "Stage 1 industries picked" data/harness.log | tail -1` returns a list of industry names (e.g., `['copper_miners', 'uranium_miners', ...]`) — NOT crypto symbols
4. **Trade fills execute**: `grep "alloc BUY wt=" data/harness.log | tail -5` shows non-zero `wt=` values (vs old `wt=0.0000` flat lines)
5. **ADIR JSON parsing improved**: `grep -c "Adir agent JSON error" data/harness.log` reduced (not zero — occasional tolerated failures OK)
6. **ui_feed.jsonl updated**: new entries should show `industries` field populated and equity tickers (not crypto):
   ```bash
   tail -1 data/ui_feed.jsonl | python3 -c "import json,sys; d=json.loads(sys.stdin.read()); print(f'cycle={d.get(\"cycle\")} industries={d.get(\"industries\")} universe_len={len(d.get(\"universe\",[]))} debates_len={len(d.get(\"debates\",{}))}')"
   ```
7. **No hard crash after 10 cycles**: `grep -c "Cycle .* done in" data/harness.log` >= 10

## Expected cycle structure (post-fix)

```
── Cycle N [Stage 3: 6 symbols] ──
[alt-data fetch attempts per picked industry — may log warnings if NOAA/USDA/EIA slow, non-fatal]
Stage 1 industries picked: ['copper_miners', 'uranium_miners', 'petroleum_producers', ...]
Universe scout picked 6 symbols: ['FCX', 'CCJ', 'XOM', ...]    ← equity tickers not crypto
Signal[FCX]: BUY (conf=0.X, pos_pct=0.XXX, ADIR: Bull(BUY,5X%,evq=0.XX) vs Bear(SELL,YY%,evq=0.XX) → RISK(BUY, ZZ%))
...
Portfolio: 6 allocations, VaR=$X, div_ratio=1.XX, exposure=X.X%
FCX: alloc BUY wt=0.0XXX qty=0.XXXX    ← real allocation
Cycle N done in XX.XXs
```

## Failure modes + diagnostic actions

| Symptom | Likely cause | Diagnostic command |
|---|---|---|
| Process dies immediately | Python import error from new modules | `tail -50 data/harness.log` — look for `ImportError` or `ModuleNotFoundError` |
| Still `Asset allocator failed` after restart | Wrong line/PID killed | `pgrep -af harness.py` — confirm new PID, verify it loaded new code |
| `Stage 1 industries picked: []` empty | `_llm_json_array` JSON parse failed (model output malformed) | Non-fatal — falls back to top-N by ticker count at `harness.py:1616-1618` |
| `Universe scout fallback` warning repeating | Stage 2 LLM call failing | Check `harness.log` for `_llm_json_array` errors; verify llama-swap responds: `curl -s http://127.0.0.1:8080/v1/models \| jq '.data[].id'` |
| `wt=0.0000` for all symbols post-restart | Risk caps binding too tight OR ADIR confidence < threshold | `grep "RiskDBG" data/harness.log \| tail -5` — examine `caps=[...]` and `state=[...]` values |
| `Failed to load adapter Alpha-1` warning | Registry still has zombie entry (should be removed by T3) | `python3 -c "import json; d=json.load(open('data/adapter_registry.json')); print([v['version'] for v in d['adapters']])"` — Alpha-1 must be absent |
| Cycle takes >120s | yfinance rate-limit on first batch | Expected — first cycle is cold cache; subsequent cycles should be 40-60s |

## Known limitations (not addressed by this plan)

- `config/industry_alt_data.yaml` still missing — ships with hardcoded defaults in `mot/industry_map.py:228-264` covering petroleum/gas/refiners/miners/ag/electric. YAML override file is optional polish.
- mcp_server on `:8092` still down — Wave 3 alt-data tools bypass it (in-process import at `harness.py:1583`). The `/api/economics` Connection refused warnings will continue but are cosmetic (try/except wrapped, no behavioral impact).
- `--reset-portfolio` flag is wired but unused in this plan (we restored from backup instead).

## Do NOT do

- Do NOT touch `mot/coordinator.py`, `training/eval_gate.sh`, `training/ops_watchdog.py`
- Do NOT remove `set -e` from any shell scripts
- Do NOT touch llama-swap config or smart-router config
- Do NOT edit the Ptolemy-S3 active adapter in the registry
- Do NOT introduce external pretrained models
- Do NOT use emoji in any code