# OpenTrader Bug Inventory & Todo List
**Generated:** 2026-07-09 | **Sources:** HANDOFF.md, report_overnight.txt, code audit of all core modules

---

## PHASE 1 — CRITICAL (breaking bugs, data corruption)

### [P1-1] `report_risk.py` crashes on state read
- **File:** `report_risk.py` lines 17, 40
- **Bug:** Line 17: `pos = s.get("positions", {})` assumes `positions` is a dict, but `StateManager.write()` stores it as a **list** (line 32 param `positions: list`, line 49: `"positions": positions`).
- **Impact:** Overnight report crashes with `AttributeError: 'list' object has no attribute 'items'`. Confirmed in `report_overnight.txt` line 20-24.
- **Fix:** Handle both formats: `pos = {p["symbol"]: p for p in s.get("positions", []) if isinstance(p, dict)}` or check `isinstance(s.get("positions"), dict)`.
- **Evidence:** `state/manager.py` line 32 `positions: list`, line 49; `report_risk.py` line 17.
- **Ref:** `/report_overnight.txt` lines 20-24

### [P1-2] `report_risk.py` stage is always "?"
- **File:** `report_risk.py` line 40
- **Bug:** `s.get("stage", "?")` reads a top-level key that doesn't exist. Stage is stored at `state["models"]["stage"]` and `state["metrics"]["stage"]`.
- **Impact:** Overnight report shows `Stage: ?` (confirmed in report_overnight.txt line 61).
- **Fix:** Read from `s.get("models", {}).get("stage", "?")` or `s.get("metrics", {}).get("stage", "?")`.
- **Evidence:** `harness.py` line 1001: `"models": {"agent": ..., "stage": self.stage, ...}`; line 1008: `"metrics": {"stage": self.stage, ...}`. Neither is at top level.

### [P1-3] Training scheduler uses `_last_arxiv_extract` (copy-paste bug)
- **File:** `harness.py` lines 1788, 1794, 1799
- **Bug:** Both arXiv feature extraction (line 1788) and training scheduler evaluation (line 1799) guard on `self.cycle - self._last_arxiv_extract >= 50`. Line 1794 resets `_last_arxiv_extract = self.cycle` after arxiv extraction, which means training scheduler eval ONLY runs if arxiv extraction doesn't. If arxiv extraction runs first, the training eval condition `self.cycle - self._last_arxiv_extract >= 50` resets and training eval may NEVER run.
- **Impact:** Training scheduler evaluation is gated behind arxiv's variable — they're coupled when they shouldn't be.
- **Fix:** Add `self._last_training_eval = 0` alongside `_last_arxiv_extract`, use it at line 1799, and update it at line 1809.
- **Evidence:** Lines 1788-1794 vs 1799-1809 — identical guard variable.

### [P1-4] FlashTrainer uses non-existent model names
- **File:** `harness.py` lines 284-285
- **Bug:** `student_model="ls:gemma-4-e4b"` and `teacher_model="ls:qwen3.6-35b-a3b"` don't exist in llama-swap. The current model is `qwythos-9b-mtp` (Qwythos-9B). HANDOFF.md line 88: "Qwythos superseded gemma-4-e4b-it".
- **Impact:** FlashTrainer will crash if it tries to use these models. Currently only initialized at startup with `auto_train=True`.
- **Fix:** Update to existing models or add a try/except with fallback. `ls:qwythos-9b-mtp` for teacher, or document that FlashTrainer is experimental.

### [P1-5] `run_harness.py` defaults to llama-swap port 8080
- **File:** `run_harness.py` line 26
- **Bug:** Defaults to `--llama-host http://127.0.0.1:8080` even though HANDOFF.md explicitly says "DO NOT use llama-swap for harness" (line 51-53). Also `_check_llama` (harness.py line 443) fallback default is `:8080`.
- **Impact:** First-time or auto-restart will use wrong port, resulting in 0.78s cycles with 50% HOLD (the exact symptom mentioned in HANDOFF.md line 54).
- **Fix:** Change default to `http://127.0.0.1:5809`. Also update `_check_llama` fallback.
- **Note:** HANDOFF.md TODO item #2 already flags this.

---

## PHASE 2 — HIGH (incorrect behavior, potential crashes)

### [P2-1] News/arxiv/social cache not thread-safe (TOCTOU race)
- **File:** `harness.py` lines 1133-1137, 1143-1145
- **Bug:** `_news_cycle` gate (line 1133) is not protected by a lock. `_debate_one_symbol` runs from multiple threads when `--parallel-debate` is enabled. Two threads can both pass the `self.cycle != self._news_cycle` check before either sets `_news_cycle`, causing duplicate `fetch_all_news()`, `fetch_arxiv()`, and `get_social_sentiment()` calls. Also cache corruption: `_social_cache` is a dict, and two threads writing simultaneously could interleave.
- **Impact:** Wasted API calls, potential cache corruption, increased cycle time.
- **Fix:** Guard with `self._data_lock = threading.Lock()`:
  ```python
  with self._data_lock:
      if self.cycle != self._news_cycle:
          self._news_cycle = self.cycle
          self._news_cache = fetch_all_news()
          ...
  ```
- **Evidence:** Comment at line 1133 says "thread-safe fetch-once-per-cycle" but there's no actual lock.

### [P2-2] MCP server `_cycle` doesn't load from state on restart
- **File:** `mcp_server.py` line 37, 321
- **Bug:** `_cycle: int = 0` initialized at module level, never loaded from `paper_state.json`. `record_cycle()` (line 321) just increments from 0.
- **Impact:** Restarting the MCP server resets the cycle counter. History JSON files (`cycle_XXXX.json`) preserve the real cycle, but MCP's `_cycle` diverges. Fills recorded with wrong cycle number.
- **Fix:** Add a `_load_cycle()` function that reads `paper_state.json` and sets `_cycle` to max cycle found in history files.

### [P2-3] MCP server trade sizing double-book-keeping
- **File:** `mcp_server.py` lines 162-169
- **Bug:** 
  ```python
  # Line 162-165: compute qty
  qty = (result.adjusted_size * bal.total_value) / max(prices.get(symbol, 1), 1)
  # Line 168: compute risk_qty — EXACT SAME FORMULA
  risk_qty = (result.adjusted_size * bal.total_value) / max(prices.get(symbol, 1), 1)
  # Line 169: min of identical values — always no-op
  final_qty = min(qty, risk_qty)
  ```
- **Impact:** The "risk-adjusted size cap" comment is misleading. `qty == risk_qty` always (same formula), so `min()` is always a no-op. If the intent was to cap against a different limit, the second cap formula is missing.
- **Fix:** Either remove `risk_qty` as dead code, or implement a real cap (e.g., max position size from config vs. Kelly-adjusted size).

### [P2-4] Dashboard `--reload` causes crash loop
- **File:** `dashboard.py` line 3190
- **Bug:** When `--reload` is used, `uvicorn.run("dashboard:app", ...)` passes the app as a string, causing uvicorn to respawn on code changes. This re-imports the module, resetting all global state (`_state_reader`, `_harness_state_dir`, `_harness_process`). The old harness subprocess handle is lost.
- **Impact:** Any file save triggers complete state loss. Dashboard becomes disconnected from running harness.
- **Fix:** Already documented as DO NOT USE. Could be fixed by storing state in file-based singletons instead of module globals.
- **Note:** HANDOFF.md line 11 says "(no --reload!)" and line 96 says it was "REMOVED" — but the option is still in the code.

### [P2-5] SELL scoring uses wrong action
- **File:** `harness.py` lines 1689-1691
- **Bug:** When a SELL order fills:
  ```python
  self._score_prediction(sym, signal.action, pnl_pct)
  self.committee.record_outcome(sym, signal.action, pnl_pct > 0)
  ```
  `signal.action` is the ORIGINAL signal action (e.g., "BUY" from the debate), not the actual executed action. If the portfolio optimizer flipped BUY→SELL for rebalancing, the wrong action is scored.
- **Impact:** Signal accuracy tracking attributes SELL outcomes to BUY predictions. Distorts accuracy metrics.
- **Fix:** Use `effective_action` (from portfolio optimizer override) instead of `signal.action`.

### [P2-6] `_load_optimal_params` re-reads JSON from disk every 100 cycles
- **File:** `harness.py` lines 1290-1300
- **Bug:** Every 100 cycles, `_load_optimal_params` reads `data/param_opt/params.json` from disk, parses all scales, does linear interpolation, and re-applies. This is an I/O+CPU operation on every 100th cycle.
- **Impact:** Minor latency spike every 100 cycles. Portfolio value changes slowly (noise), so re-reading is wasteful.
- **Fix:** Cache the parsed result in memory and only re-read if params.json's mtime changed.

---

## PHASE 3 — MEDIUM (edge cases, inefficiencies)

### [P3-1] Portfolio optimizer runs even with all-HOLD signals
- **File:** `harness.py` line 1431
- **Bug:** `if multi_symbol and self.debate and all_signals:` triggers portfolio optimization on EVERY cycle that has any signals. If all signals are HOLD, the optimizer computes allocations that will be ignored anyway.
- **Impact:** Wasted compute (fetches prices, runs optimize, extracts price history, computes VaR). Roughly 1-3s per cycle wasted if all HOLD.
- **Fix:** Check `any(s.action in ("BUY", "SELL") for s in all_signals)` before running optimizer.

### [P3-2] No circuit breaker recovery mechanism
- **File:** `harness.py` circuit breaker logic (~line 1309-1320 area)
- **Bug:** The circuit breaker (`self.running = False`) is a one-way trip. Once triggered (e.g., by excessive drawdown), the harness stops permanently. There's no cool-down period or re-evaluation.
- **Impact:** Harness requires manual restart after any circuit breaker trip. No automatic recovery even if conditions improve.
- **Fix:** Add a cool-down mechanism: after N cycles of being stopped, re-evaluate conditions and reset `self.running = True` if recovery criteria are met.

### [P3-3] State `positions` format inconsistency (latent)
- **File:** `state/manager.py` vs all consumers
- **Bug:** `StateManager.write()` accepts `positions: list` (line 32 type hint, line 49 storage). But `report_risk.py` and potentially other consumers expect a dict (`symbol → quantity`). Dashboard handles both formats, but it's a latent bug.
- **Impact:** Any new consumer that reads `positions` as a dict will crash.
- **Fix:** Either store positions as dict in state (breaking change for dashboard), or add a consumer helper function `normalize_positions()`.

### [P3-4] Dashboard PVA cache misses new symbols
- **File:** `dashboard.py` lines 548-571 (cache hit path), 575-614 (cache miss path)
- **Bug:** In the cache hit path (lines 548-571), `base_prices` is built from historical points only. When live state contains symbols not in history, they're silently skipped at line 556 (`k not in base_prices` check prevents adding them retroactively). The cache miss path (line 590-592) has the same issue: `if sym_short not in base_prices and px > 0: base_prices[sym_short] = px` — but this only adds them on miss, not on hit.
- **Impact:** New symbols added to trading don't show price curves until enough history files exist to trigger a cache miss.
- **Fix:** In cache hit path, merge live state prices into `base_prices` before the initial check.

### [P3-5] Single-symbol `sym_res` unused variable
- **File:** `harness.py` line 1400
- **Bug:** `sym_res, signal, ctx, regime_dict = self._debate_one_symbol(...)` — `sym_res` captures the returned symbol but is never used (loop variable `sym` already has it).
- **Impact:** Cleanup only. PyLint warning.
- **Fix:** Change to `_, signal, ctx, regime_dict = ...` or remove the unused first return from `_debate_one_symbol`.

---

## PHASE 4 — LOW (cosmetics, documentation)

### [P4-1] Portfolio optimizer override loses original signal action
- **File:** `harness.py` lines ~1528-1532 area
- **Bug:** When portfolio optimizer produces an allocation that overrides `effective_action`, the original debate signal's action is discarded from the trade journal. The scoring and journal show the override action, not the signal that led to it.
- **Impact:** Signal attribution is muddy: was the trade signal-driven or optimizer-driven?
- **Fix:** Record both `signal.action` and `effective_action` in the trade journal.

### [P4-2] MCP server duplicate computation
- **File:** `mcp_server.py` lines 162-169
- **Bug:** `qty` and `risk_qty` computed identically. Dead code.
- **Impact:** None (no-op), but confusing to read.
- **Fix:** Remove `risk_qty` or implement real cap.

### [P4-3] HANDOFF.md gaps not updated
- **File:** `HANDOFF.md` lines 110-115
- **Bug:** The TODO section is incomplete — missing: report_risk.py crash, stage missing, training scheduler bug, MCP server issues, thread safety.
- **Impact:** Next developer inherits known bugs without warning.
- **Fix:** Update with findings from this audit.

### [P4-4] `_check_llama` fallback default is hardcoded 8080
- **File:** `harness.py` line 443
- **Bug:** `url = (host or "http://127.0.0.1:8080")` — hardcoded fallback. Should be configurable or match the model port.
- **Impact:** If `_check_llama` is called without host arg, it checks the wrong port.

---

## SUMMARY TABLE

| # | Severity | File | Bug | Type |
|---|----------|------|-----|------|
| P1-1 | 🔴 CRITICAL | report_risk.py:17 | `positions` dict vs list crash | Runtime crash |
| P1-2 | 🔴 CRITICAL | report_risk.py:40 | `stage` always "?" | Data loss |
| P1-3 | 🔴 CRITICAL | harness.py:1799 | Training eval uses arxiv variable | Silent skip |
| P1-4 | 🔴 CRITICAL | harness.py:284-285 | Non-existent model names | Runtime crash |
| P1-5 | 🔴 CRITICAL | run_harness.py:26 | Wrong default port | Wrong behavior |
| P2-1 | 🟠 HIGH | harness.py:1133-1137 | News cache not thread-safe | Race condition |
| P2-2 | 🟠 HIGH | mcp_server.py:37 | Cycle counter not loaded from state | Data corruption |
| P2-3 | 🟠 HIGH | mcp_server.py:162-169 | Trade sizing double-book-keeping | Wrong behavior |
| P2-4 | 🟠 HIGH | dashboard.py:3190 | `--reload` crash loop | Runtime crash |
| P2-5 | 🟠 HIGH | harness.py:1689-1691 | SELL scores wrong action | Data corruption |
| P2-6 | 🟠 HIGH | harness.py:1290-1300 | JSON re-read every 100 cycles | Inefficiency |
| P3-1 | 🟡 MEDIUM | harness.py:1431 | Optimizer on all-HOLD signals | Waste |
| P3-2 | 🟡 MEDIUM | harness.py | No circuit breaker recovery | Reliability |
| P3-3 | 🟡 MEDIUM | state/manager.py | Positions format inconsistency | Latent bug |
| P3-4 | 🟡 MEDIUM | dashboard.py:548-571 | PVA cache missing new symbols | Wrong display |
| P3-5 | 🟡 MEDIUM | harness.py:1400 | `sym_res` unused variable | Cleanup |
| P4-1 | 🟢 LOW | harness.py:1528-1532 | Optimizer override loses signal attr | Attribution |
| P4-2 | 🟢 LOW | mcp_server.py:162-169 | Duplicate computation | Cleanup |
| P4-3 | 🟢 LOW | HANDOFF.md:110-115 | Gaps not documented | Documentation |
| P4-4 | 🟢 LOW | harness.py:443 | Hardcoded port fallback | Robustness |

---

## RECOMMENDED FIX ORDER

1. **P1-1** + **P1-2** — Fix report_risk.py (both in same file, 5-min fix)
2. **P1-3** — Fix training scheduler variable (add `_last_training_eval`, 2-min fix)
3. **P1-4** — Fix FlashTrainer model names (update to existing models, 5-min fix)
4. **P1-5** — Fix run_harness.py default port (:5809 instead of :8080, 1-min fix)
5. **P2-1** — Add threading lock to news cache (10-min fix with testing)
6. **P2-2** — Load MCP cycle from state on startup (15-min fix)
7. **P2-5** — Fix SELL scoring to use effective_action (5-min fix)
8. **P2-6** — Cache `_load_optimal_params` result with mtime check (10-min fix)
9. **P3-1** — Skip optimizer when all signals are HOLD (5-min fix)
10. **P3-3** — Normalize positions format (10-min fix, requires testing dashboard)
11. **P3-2** — Circuit breaker recovery (20-min fix, needs careful design)
12. **P2-3** + **P4-2** — Clean up MCP trade sizing (5-min fix)
13. **P3-4** — Fix PVA cache for new symbols (10-min fix)
14. **P2-4** — Fix or remove `--reload` flag (15-min fix)
15. Rest — Cleanup, documentation, unused variables
