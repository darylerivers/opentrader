# Builder Handoff: Round 2 — wt=0 Floor + SELL Guard Fix + Diagnostic

**Single file: `harness.py`**. Three changes, ordered by execution priority.

## Status Update From Phase 1 Round 1

- ✅ Fix 3 (dict normalization): Working, no crashes
- ⚠️ Fix 1 (wt=0): Partial — 3 of 6 BUYs now non-zero (NVDA/MSFT/GOOGL filled). AAPL still 0 due to circular zero when Kelly floor hits 0
- ⚠️ Fix 2d (SELL guard): Format correct but `bear=0.00` reading is wrong (debate vote was Bear HOLD conf=0.40)
- ✅ Fix 2a-b-c (ATR-14 helper + BUY fill + resurrection): Built and wired at harness.py:1307, :787, :2281

## Change 1 — Diagnostic Logging at SELL Guard (shipped FIRST, before other fixes)

*One logging line to confirm whether `_cycle_debates[sym]` is empty at SELL guard fire time.*

At `harness.py:2160` (entry to SELL guard), add temporary:

```python
if effective_action == "SELL" and sym in self._sl_tp_levels:
    # TEMPORARY DIAGNOSTIC — remove once bear=0.00 bug resolved
    logger.info(f"  [diag] sym={sym!r} _cycle_debates.keys={list(self._cycle_debates.keys())} entry={self._cycle_debates.get(sym)}")
    levels = self._sl_tp_levels[sym]
    ...
```

**Why**: This resolves the bear=0.00 mystery in one cycle. Either:
- `_cycle_debates` is empty/None → reset/port-overwrite bug exists somewhere between 1940-2155
- `_cycle_debates[AAPL]` exists but structure differs → key mismatch issue
- `_cycle_debates[AAPL]` exists with bear.conf=0.40 → journal saw a different cycle's data

Builder should run harness ONE cycle with this log, capture output, then continue to Change 2 below based on observed behavior. If bear.conf=0.40 confirmed live, the SELL guard fix in Change 3 below is still needed (the guard fires for a non-debate-driven SELL).

## Change 2 — wt=0 weight_pct Floor (line ~2109-2117)

*Breaks the circular zero when Kelly fraction floors at 0 for low-confidence BUYs.*

**Root cause verified**: When optimizer returns `weight_pct=0` (Kelly at conf=0.23 evaluates near-zero) and `quantity=0` (BUY with no position to trim against), the recovery block computes `qty_new = 0 * total_value / price = 0`, then `a.weight_pct = 0 * price / total_value = 0` → no recovery. For SELL side with stuck position: `a.quantity > 0` so `if a.quantity <= 0` skip the defensive patch entirely.

**Fix**: Replace lines 2107-2117 with a floor based on signal.confidence:

```python
if portfolio_result:
    for a in portfolio_result.allocations:
        signal = next((s for s in all_signals if s.symbol == a.symbol), None)
        # Apply weight floor for low-conviction BUYs (Kelly near-zero recovery)
        if (a.weight_pct < 0.0005 and signal and signal.action == "BUY"
                and signal.confidence > 0.15
                and portfolio_dict.get("total_value", 0) > 0):
            # Floor: small allocation proportional to confidence, capped at 1%
            floor_weight = min(0.01, signal.confidence * 0.03)
            a.weight_pct = max(a.weight_pct, floor_weight)
            price = prices.get(a.symbol, 1)
            a.side = "BUY"
            a.quantity = max((a.weight_pct * portfolio_dict["total_value"]) / max(price, 1), 0)
        # Existing defensive patch for zero-qty cases
        elif a.quantity <= 0 and signal and signal.action in ("BUY", "SELL"):
            if signal.action == "BUY":
                price = prices.get(a.symbol, 1)
                qty_new = (a.weight_pct * portfolio_dict["total_value"]) / max(price, 1)
                a.side = "BUY"
                a.quantity = max(qty_new, 0)
                if portfolio_dict.get("total_value", 0) > 0:
                    a.weight_pct = a.quantity * max(price, 1) / portfolio_dict["total_value"]
            elif signal.action == "SELL":
                pos = portfolio_dict.get("positions", {}).get(a.symbol, 0)
                if pos > 0:
                    a.side = "SELL"
                    a.quantity = float(pos)
        alloc_map[a.symbol] = {
            "side": a.side,
            "weight_pct": a.weight_pct,
            "quantity": a.quantity,
            "reason": a.reason,
        }
```

**Floor rationale**: `signal.confidence * 0.03` at conf=0.23 = 0.0069 = 0.69% allocation — enough to clear the `notional>0` threshold and trigger a real fill. Capped at 1% to prevent runaway size. Only kicks in when Kelly produced below 0.0005 (true floor) — never overrides meaningful Kelly weights.

## Change 3 — SELL Guard Checks `signal.action` Not `effective_action`

*Fix the guard firing on optimizer-derived SELL (trim) when debate said BUY.*

**Root cause verified at line 2141-2147**: `effective_action = signal.action` (debate intent), then `effective_action = alloc["side"]` (optimizer override). The SELL guard at 2160 checks `effective_action == "SELL"`. When a position is above Kelly target, optimizer returns `side="SELL"` regardless of signal.action. The SELL guard then fires for a non-debate-driven trim, and the bear conf reading becomes meaningless (debate voted BUY, not SELL).

**Fix**: Replace the guard condition to check `signal.action` instead of `effective_action`:

```python
# ── SL/TP guard: only block DEBATE-DRIVEN SELL when SL/TP active ──
# Optimizer-driven SELL (trim of above-Kelly position) should NOT trigger this guard,
# only explicit debate votes for SELL should be blocked to let SL/TP handle exits.
if signal.action == "SELL" and sym in self._sl_tp_levels:
    levels = self._sl_tp_levels[sym]
    sl = levels.get("stop_loss")
    tp = levels.get("take_profit")
    if sl or tp:
        debate = self._cycle_debates.get(sym, {})
        bear_conf = debate.get("bear", {}).get("conf", 0)
        risk_data = debate.get("risk", {})
        risk_action = risk_data.get("action", "")
        risk_conf = risk_data.get("conf", 0)
        if bear_conf >= 0.6 or (risk_action == "SELL" and risk_conf >= 0.5):
            logger.info(f"  {sym}: high-conviction SELL override "
                      f"(bear={bear_conf:.2f}, risk={risk_conf:.2f}) — clearing SL/TP")
            del self._sl_tp_levels[sym]
            # Force the SELL through downstream
            effective_action = "SELL"
            if alloc:
                alloc["side"] = "SELL"
                pos_qty = portfolio_dict.get("positions", {}).get(sym, 0)
                if pos_qty > 0:
                    alloc["quantity"] = float(pos_qty)
        else:
            logger.info(f"  {sym}: debate SELL blocked (SL/TP active: SL={sl or 'N/A'}, "
                      f"TP={tp or 'N/A'}) — low conviction (bear={bear_conf:.2f}, risk={risk_conf:.2f})")
            effective_action = "HOLD"
            effective_position_pct = 0
            if alloc:
                alloc["side"] = "HOLD"
                alloc["quantity"] = 0
```

**Critical**: Place this block AFTER the line that sets `effective_action = alloc["side"]` (current line ~2147), so the guard can OVERRIDE the optimizer's SELL trim back to HOLD if debate conviction is low. The `signal.action` check at the guard entry makes it only fire for explicit debate SELLs — optimizer SELLs (trims when signal.action=BUY) pass through untouched (position gets trimmed by the optimizer's intent, not blocked by the guard).

## Execution Order

1. **Change 1 (diagnostic log)** — add at line 2160
2. Restart harness, tail 1-2 cycles, capture diagnostic log output
3. **Change 2 (wt=0 floor)** — apply
4. **Change 3 (SELL guard fix)** — apply, **KEEP diagnostic log from Change 1** during initial verification
5. Restart, tail 5 cycles — verify non-zero wt= for AAPL, no SELL guard misfire for BUY signals
6. Once behavior confirmed, **remove diagnostic log** (or downgrade to DEBUG)

## Verification Gates

1. `python3 -c "import ast; ast.parse(open('/home/mrc/opentrader/harness.py').read()); print('syntax OK')"`
2. After Change 1: `tail -f data/harness.log` for 1-2 cycles, capture `[diag] sym=...` lines
3. After Changes 2+3: tail 5 cycles:
   - AAPL has non-zero `wt=` (e.g., 0.0069) and non-zero `qty=` — filled BUY
   - NO `AAPL: SELL blocked ... bear=0.00` (because signal.action=BUY, not SELL, so guard doesn't fire)
   - No `99900%` fee rejection on AAPL
   - For any symbol with signal.action=SELL AND stuck SL/TP: guard fires correctly with real bear_conf
4. Wait 10 cycles: no crash, no training.lock, harness alive

## Restraints

- **ONLY file edited: `harness.py`**
- NO touching portfolio_optimizer.py (floor belongs in harness, not optimizer)
- NO `--reset-portfolio`, NO `set -e` changes
- NO emoji in code
- Read line numbers may have shifted from verified state — verify by context, not exact line numbers
- The diagnostic log in Change 1 should be REMOVED after one successful verification cycle (or wrapped in `logger.isEnabledFor(logging.DEBUG)`)

---

Three changes, single file, ~30 lines added. Ship diagnostic first to resolve bear=0.00 mystery, then ship floor + guard together. Estimated builder time: ~30 min implementation + ~15 min verification.
