# TUI Dashboard — Agentic Layer Integration Plan

**Status:** Planning (not yet executed)
**Author:** OpenCode plan-mode session (m0493–m0509)
**Scope:** Extend `tui_dashboard.py` to surface the agentic engineering layer (ADIR debate, universe scouting, deep-eval breakdown, pending candidates, deploy gate, research/scout heartbeat) that is currently invisible in the dashboard.

---

## Current State (verified on disk)

`tui_dashboard.py` (353 lines, Rich-based) currently shows:
- KPI tiles (portfolio, return, trades, win rate, drawdown, peak, cycle)
- Positions table
- Recent signals table
- System status (harness/model/training status, mode line, cron line)
- Training & eval panel (active adapter + eval scores per version)
- Equity curve sparkline
- 3 tabs: Overview | Positions | Training

**Missing from TUI** — despite being built and running:
- ADIR per-symbol debate votes (Bull/Bear/Risk actions + confidences + evidence_quality)
- Universe top-6 picks with opportunity scores (harness scouts 52 assets each cycle)
- Pending eval candidates awaiting eval_gate.sh
- Deep eval per-dimension breakdown (7 dims, only weighted score shown now)
- Deploy gate threshold + delta-to-promote for each candidate
- Research scout / distiller / ATDL heartbeat and staleness
- Advisor logic bug (only uses harness win-rate, ignores eval_score)

---

## Cross-cutting Design Decisions

**Read pattern**: TUI continues polling `data/paper_state.json` every 2s. For Forks 1 & 3, add reads of:
- New `data/ui_feed.jsonl` (Fork 1 only — harness writes, TUI reads tail)
- Existing `data/eval/reports/*_deep_*.json` (Fork 2)
- Existing `data/adapter_registry.json` (Fork 2)
- Existing `data/scheduler_state.json` + `data/scheduler_cron.log` (Fork 3)
- Existing `data/eval_state.json` (Fork 2)

**Write pattern (Fork 1 only)**: harness appends **one JSON line per cycle** to `data/ui_feed.jsonl` (universe picks + ADIR votes per symbol). JSONL for tail-rotate simplicity. Cap at ~200 lines (~800KB).

**Layout change**: expand 3-tab system to **5 tabs**:
- Tab 1: Overview (unchanged, swap training right-panel for a compact cross-link)
- Tab 2: Positions (unchanged)
- Tab 3: Training (slimmed — just active + eval totals, link to Pipeline tab)
- Tab 4: Debate (NEW — Fork 1)
- Tab 5: Pipeline (NEW — Forks 2 + 3 combined)

Keypress map: `1`=Overview, `2`=Positions, `3`=Training, `4`=Debate, `5`=Pipeline, `q`=quit, `p`=pause, `r`=refresh.

---

## FORK 2 — Eval pipeline surfaces (read-only, ship first)

**Risk:** very low. No harness changes. Pure file reads against existing artifacts.
**Files modified:** `tui_dashboard.py` only (~180 added lines).
**Estimated time:** 1 hour.

### 2a. New function: `eval_breakdown_panel()`

Locate the latest `*_deep_*.json` for each Ptolemy-S{0,1,2,3} via the existing pattern at `tui_dashboard.py:207`. Render per model:

- **weighted_score** + 7 per-dim mini-bars
- Use 12-char-wide bar chart: `█▆▇▆█▃▅` (the BLOCKS string already exists at `tui_dashboard.py:53`)
- Color: ≥0.75 green, 0.50–0.74 yellow, <0.50 red
- Show `elapsed_s` per dim as a small footer (lets user see whether eval actually ran fully)
- Header row: `Model | weighted | dim1 | dim2 | dim3 | dim4 | dim5 | dim6 | dim7 | n_runs`
- Sort by `weighted_score` descending — top entry highlighted cyan
- Show std-dev across multiple runs (read sibling files with same prefix) if found

### 2b. New function: `pending_candidates_panel()`

Read `data/adapter_registry.json` → list entries with `status == "pending"` AND no `eval_score` set (no deep report exists).

For each: `version | examples | training_ts | awaiting_eval? ✗ | next eval_gate in ~Xm`

Compute "next eval_gate ETA": `eval_gate.sh` runs every 30 min via cron. ETA = `(30 - now.minute % 30) min` (simple approximation).

If `data/training.lock` exists: show "training in progress — eval deferred". If zero pending: dim "No pending candidates — all evaluated".

### 2c. New function: `deploy_gate_panel()`

Parse `eval_deploy.py` (read-only) for `should_promote()` threshold — currently `>= 3.0`. Compute, for each candidate vs active: `delta = candidate.eval_score - active.eval_score`.

Show as a small table: `Candidate | score | active | delta | gate (≥+3.0) | verdict`

Verdict colors:
- green: delta ≥ 3.0 — "ready to deploy"
- yellow: 0 ≤ delta < 3.0 — "no edge"
- red: delta < 0 — "no promotion"

### 2d. Fix advisor logic (`tui_dashboard.py:224`)

Current (broken):
```python
if br > 0 and wr > 55: "Strong"
elif wr > 50: "Developing"
else: "Weak"
```

Proposed (cross-reference with active model's `eval_score`):
```python
if active_eval >= 0.75 and (br > 0 or wr > 55):
    "Strong — eval ≥ 0.75 + beating market"
elif active_eval >= 0.50:
    "Developing — eval healthy, building track record"
elif active_eval > 0:
    "Weak — eval below 0.50, needs more training"
else:
    "Unevaluated — pending deep_eval"
```

### 2e. Tab wiring

- New `build_pipeline_detail(s)` builder combining 2a + 2b + 2c
- Add `'Pipeline' = builder index 5` to TABS
- Update keypress handling: `5` → TAB=5
- Update Overview right column to replace `training_panel()` with a compact one-liner: `Active: S3 (eval 0.78) | 2 pending | next eval 14m` (links to Tab 5)

### Verification (Fork 2)

- `python3 tui_dashboard.py` → Tab 5 "Pipeline" shows all 3 panels populated from current data
- No new process started; no files touched

---

## FORK 1 — ADIR + Universe visibility (harness write + TUI read)

**Risk:** medium. One append at harness cycle end. Idempotent JSON appending, no other harness changes.
**Files modified:**
- `harness.py:1545–1716` (`_scout_universe`): persist raw model response before filtering
- `harness.py:2413` (end of `run_cycle`): append cycle ui_feed record
- `mot/agents/adir_debate.py`: expose `last_debate_results` property
- `tui_dashboard.py`: new `universe_panel()` + `debate_panel()` + tab builder
**Estimated time:** 1.5 hours split across 2 sessions.

### 1a. Persist universe picks with scores

In `_scout_universe`, around `harness.py:1703` (where `data = json.loads(array_match.group(0))` succeeds):

- Save the raw picks JSON to instance attribute: `self._last_universe_pick = data` (list of `{"symbol", "score", "reason"}` dicts)
- Falls back gracefully if `data` is None → `self._last_universe_pick = [{"symbol": s, "score": 0, "reason": "fallback"} for s in picks]`

### 1b. Expose ADIR per-symbol debate votes

`AdirDebateEngine` already has the structured debate vote internally. Add:

```python
@property
def last_debate_results(self) -> dict[str, dict]:
    """Returns {symbol: {bull_action, bull_conf, bull_evq,
                          bear_action, bear_conf, bear_evq,
                          risk_action, risk_conf}} for the last debate."""
    return dict(self._last_debate_results) if hasattr(self, '_last_debate_results') else {}
```

Wire storage inside `_debate_one_symbol` (`harness.py:1291`) where the ADIR result is captured.

### 1c. New file: `data/ui_feed.jsonl`

**Schema per line** — one per harness cycle:

```json
{
  "cycle": 12567,
  "ts": "2026-07-16T15:34:21+00:00",
  "universe": [
    {"symbol": "BTC/USDT", "score": 8.5, "reason": "strong momentum"},
    "...up to 6 items"
  ],
  "debates": {
    "BTC/USDT": {
      "bull": {"action": "BUY", "conf": 0.65, "evq": 0.58},
      "bear": {"action": "SELL", "conf": 0.76, "evq": 0.35},
      "risk": {"action": "SELL", "conf": 0.20, "evq": null}
    }
  },
  "signals": [
    {"symbol": "BTC/USDT", "action": "SELL", "confidence": 0.42, "position_pct": 0.10, "reason": "..."}
  ]
}
```

### 1d. Append call site (harness.py:2413 area)

After cycle complete, before `logger.info(f"Cycle {self.cycle} done in {cycle_time:.2f}s")`:

```python
try:
    feed = {
        "cycle": self.cycle,
        "ts": datetime.now(timezone.utc).isoformat(),
        "universe": getattr(self, "_last_universe_pick", [])[:6],
        "debates": self.debate.last_debate_results if self.debate else {},
        "signals": self._cycle_signals_summary or [],
    }
    with open(_Path(self.state_dir) / "ui_feed.jsonl", "a") as f:
        f.write(json.dumps(feed) + "\n")
    # Rotate: keep last 200 lines
    p = _Path(self.state_dir) / "ui_feed.jsonl"
    if p.stat().st_size > 200 * 4096:  # ~800KB cap
        lines = p.read_text().splitlines()[-200:]
        p.write_text("\n".join(lines) + "\n")
except Exception as e:
    logger.debug(f"ui_feed append failed: {e}")
```

**Critical safety property:** any error logged at DEBUG only — never crashes the harness. ui_feed is telemetry, not trading logic.

### 1e. TUI panels

**`universe_panel()`**: read last line of `ui_feed.jsonl`, show 6 rows of `Symbol | Score | Reason` colored by score (≥7 green, 4–6 yellow, <4 red). Title: "Universe Top 6 (agent scouts 52)".

**`debate_panel()`**: show last 6 debates as bar-chart-style bull/bear vertical columns:

```
BTC/USDT  Bull BUY  ████████▌ 65% (evq=0.58)
          Bear SELL █████████▌ 76% (evq=0.35)
          RISK SELL ██▎ 20%  → SELL
```

- Each symbol block shows the three-role debate alignment
- Flag disagreement when `|conf_bull - conf_bear| > 0.3` → yellow border
- New `build_debate_detail(s)` tab combines Universe panel + Debate panel side-by-side, also showing signal decisions for cross-reference

### Verification (Fork 1)

- Start harness with `--universe-focus 6`, wait 2 cycles (~20s)
- `tail /home/mrc/opentrader/data/ui_feed.jsonl` — should show JSON lines
- `python3 tui_dashboard.py` → Tab 4 "Debate" shows live universe + debate votes
- After 200 cycles, file should rotate, not grow unbounded

### Risk mitigation

- Append wrapped in try/except, debug-log only — cannot break trading cycle
- File rotation prevents log explosion
- If `_last_universe_pick` missing (early cycle), defaults to `[]` — panel shows "Collecting..."

---

## FORK 3 — Research & autonomy heartbeat (read-only, ship last)

**Risk:** zero (pure file reads, no harness touching).
**Files modified:** `tui_dashboard.py` only (~80 added lines). Adds to Pipeline tab built in Fork 2.
**Estimated time:** 45 minutes.

### 3a. New function: `research_heartbeat_panel()`

Read `data/scheduler_state.json` → show:

```
Research Scout:
  Last sweep: 2026-07-15 05:00 (stale by 28h — flag red if >6h)
  Last distill: 2026-07-15 05:00
  Last ATDL trigger: 2026-07-14 17:10
  DPO triggered: true
  Research model check: 2026-07-14 17:10
```

- Compute staleness = `now - last_scout_sweep`; if > 6h show red `⚠ stale by Xh`, else green
- Tail `data/scheduler_cron.log` for last action verb ("scout", "distill", "research", "cycle")

### 3b. Read autonomy markers

- Read `data/atdl_state.json` if present — show current ATDL phase, last action, last transition timestamp
- Read `data/training_state.json` for current training lifecycle stage

### 3c. New function: `research_findings_panel()` (optional)

- Look for recent capability manifests in `data/research/` directory (created by `research_runner.py`)
- List N most recent findings with title + score + source (arXiv vs HF Hub)
- If `data/research/` doesn't exist, show "No findings cached — research hasn't run yet" (matches current state)

### 3d. Tab integration

- Add `research_heartbeat_panel()` + `research_findings_panel()` to the Pipeline tab (from Fork 2)
- Pipeline tab becomes 3 vertical sections:
  - Top: Eval Pipeline (Fork 2a + 2b)
  - Middle: Deploy Gate (Fork 2c)
  - Bottom: Autonomy Heartbeat (Fork 3a + 3b + 3c)
- Distributes via Layout

### Verification (Fork 3)

- Pipeline tab shows all panels
- Staleness flag triggers red since `scheduler_state.json` is from Jul 14–15 (matches reality — scout hasn't run in >6h)
- Next cron job at 30-min boundary updates `scheduler_state.json` → dashboard prints "fresh" within 2 polling cycles (4s)

---

## Implementation Order

| Session | Scope | Risk | Estimate | Verification |
|---------|-------|------|----------|--------------|
| 1 | Fork 2 (read-only TUI only) | None | ~1 hour | Disk state renders |
| 2 | Fork 1 part 1 (harness.java append + ui_feed.jsonl + helper wires) + harness restart | Medium | ~30 min | `ui_feed.jsonl` grows by 1 line per cycle |
| 3 | Fork 1 part 2 (TUI universe_panel + debate_panel + new tab) | None | ~1 hour | Tab 4 shows live data |
| 4 | Fork 3 (read-only TUI panels added to Pipeline tab) | None | ~45 min | Tab 5 shows heartbeat + findings |

**Total:** ~3 hours across 4 sessions. Each session ends with a verifiable state.

---

## Final Verification Gate

After all 4 sessions, confirm:

1. `python3 tui_dashboard.py` opens cleanly
2. Tab 4 "Debate" shows universe top 6 + ADIR votes live updating
3. Tab 5 "Pipeline" shows eval breakdown, pending candidates, deploy gate deltas, research heartbeat
4. Advisor text on Training tab references `eval_score` (not just harness win-rate)
5. No harness cycle crashes introduced — check `data/harness.log` for `ui_feed append failed` debug messages (should be silent or only on transient errors)
6. `data/ui_feed.jsonl` bounded to ~200 lines (~800KB cap), not growing unbounded
7. TUI degrades gracefully when files are missing (no exceptions, always shows "Collecting..." or "—")

---

## Known Limitations

- **Dim #1 (signal_accuracy) is in-distribution** because ground truth comes from `ProgrammaticTeacher`. Not a TUI issue — carries over from `deep_eval.py` design.
- **Alpha-1 entry may reappear** if `mot/coordinator.py::should_promote` fix didn't fully persist (separate from TUI work). Recommend greping for the fix before starting Fork 1.
- **ADIR votes may be empty** for cycles where the debate fails and falls back to heuristic — `_last_debate_results` will be `{}`. Panel should show "Heuristic fallback — no debate votes" in that case.
- **Mobile compatibility**: TUI layout must remain readable at 80-char width. Test from a cramped SSH session.
- **eval_state.json schema**: confirm actual fields before building Fork 2b — assume `{"pending": [...], "last_eval": "..."}` shape. Verify on disk before implementation.

---

## Related Files (on-disk reference)

**Harness side:**
- `harness.py:1545` — `_scout_universe` method (universe picks)
- `harness.py:1291` — `_debate_one_symbol` (ADIR per-symbol vote)
- `harness.py:1679` — `run_cycle()` top
- `harness.py:2413` — end of `run_cycle` (candidate append call site)
- `mot/agents/adir_debate.py:461-467` — `_run_bull` / `_run_bear` (debate vote storage target)

**TUI side:**
- `tui_dashboard.py:53` — `BLOCKS` spark chars (reuse for bars)
- `tui_dashboard.py:108` — `equity_panel()` (style model for new panels)
- `tui_dashboard.py:194` — `training_panel()` (advisor-fix target, line 224)
- `tui_dashboard.py:207` — pattern for reading `*_deep_*.json` reports (reuse for Fork 2a)
- `tui_dashboard.py:236` — `build_overview` (5-tab extension target)
- `tui_dashboard.py:318` — `Live` block (existing key handler extension target)

**Existing state files:**
- `data/eval/reports/Ptolemy-S{1,2,3}_deep_*.json` — per-dim breakdown (Fork 2a)
- `data/adapter_registry.json` — pending/active/scored entries (Fork 2b, 2c, 1e)
- `data/scheduler_state.json` — research heartbeat source (Fork 3a)
- `data/atdl_state.json` — ATDL phase source (Fork 3b)
- `data/training_state.json` — training lifecycle source (Fork 3b)
- `data/eval_state.json` — confirm schema before Fork 2b