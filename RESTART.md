# OpenTrader — Autonomous Improvement Loop
**Date:** 2026-07-24 | **Phase:** RESTART | **Session:** Full autonomous cycle

---

## INFRASTRUCTURE STATE

| GPU | Port | Model | Context | Purpose |
|-----|------|-------|---------|---------|
| RTX 3070 (8GB) | :5803 | Qwen2.5-7B-Q4_K_M | 24K | Architect + subagents (manager, qwen-worker) |
| RX 7900 GRE (16GB) | :5802 | Ternary Bonsai 27B-Q2_0 | 262K | Builder + supervisor + harness+trading |

```bash
# Verify both servers alive
curl -s http://localhost:5802/health > /dev/null && echo ":5802 OK" || echo ":5802 DOWN"
curl -s http://localhost:5803/health > /dev/null && echo ":5803 OK" || echo ":5803 DOWN"
```

---

## PHASED LOOP INSTRUCTIONS

You operate in a continuous 5-phase loop. Each phase produces artifacts that feed the next. Track state in `data/loop_state.json`. After each phase, record what was done and transition.

### PHASE 1: BUG HUNTING

**Goal:** Find and fix code issues, configuration errors, race conditions, and logic bugs.

**Method:**
1. Run `python3 -m py_compile` on ALL Python files in `mot/`, `risk/`, `agent/`, `exchange/`, `training/`, `data/`, `state/`, `scripts/`. Report any compilation failures.
2. Read `data/paper_state.json` — verify positions, cash, PnL make arithmetic sense.
3. Read `data/agent_state.json` — check `_trade_journal` has entries, `_signal_scores` is populating, `_committee` stats are sane.
4. Grep for `TODO`, `FIXME`, `HACK`, `XXX` across the codebase. Prioritize by severity.
5. Check `data/` for orphaned `.tmp` files, stale locks (`training.lock` with no process holding it), zero-byte state files.
6. Run existing tests: `python3 tools/ab_debate_test.py` and `python3 training/signal_quality_test.py`. Report failures.
7. Read `data/coach_report.json` — if it exists, extract failure patterns and cross-reference with recent trades.

**Artifacts produced:** List of bugs found + fixes applied. Write to `data/loop_state.json` under `bug_hunt`.

**Exit condition:** No more critical bugs found OR 3 consecutive passes with no new findings.

---

### PHASE 2: DEEP RESEARCH

**Goal:** Gather market context, research signals, and extract trading rules.

**Method:**
1. Fetch latest arXiv papers: `python3 -c "from data.arxiv import fetch_arxiv, extract_features; fetch_arxiv(); features = extract_features(); print(f'{len(features)} new trading rules')"`
2. Run feature integrator: `python3 -c "from data.feature_integrator import validate_and_integrate; v, _ = validate_and_integrate(state_dir='data', trade_history=None); print(f'validated: {v}')"`
3. Fetch market news: `python3 -c "from data.news import fetch_all_news; import json; n = fetch_all_news(); print(json.dumps(n, indent=2)[:500])"`
4. Fetch social sentiment: `python3 -c "from data.social_sentiment import get_social_sentiment; s = get_social_sentiment(['BTC/USDT','ETH/USDT','SOL/USDT']); print(s)"`
5. Run research scout sweep: `python3 -m training.research_runner --verbose`
6. Check if research model training is warranted: `python3 -m training.research_model --check-gate`

**Artifacts produced:** New trading rules in feature backlog, updated market context. Write to `data/loop_state.json` under `research`.

**Exit condition:** All data sources consumed, features integrated, sweep complete.

---

### PHASE 3: DATA COLLECTION & AGGREGATION

**Goal:** Build and curate training datasets from all available sources.

**Method:**
1. Build DPO preference pairs: `python3 -m training.dpo_builder --min-trades 5`
2. Build legacy training data: `python3 -m training.legacy_data_builder --max-cycles 500`
3. Build ADIR debate training data: `python3 -m training.adir_data_builder --max-examples 50`
4. Extract real trade patterns: `python3 -m training.real_pattern_bank --summary`
5. Capture opencode agent episodes (if any recent sessions): `python3 training/opencode_episode_recorder.py --export`
6. Check training scheduler: `python3 -m training.train_scheduler --evaluate`
7. Run capability distillation: `python3 -m training.capability_distiller --verbose`
8. Verify all datasets: count examples in each `data/training/*.jsonl` file. Report counts.

**Artifacts produced:** Training datasets at `data/training/training_data_*.jsonl`. Updated `data/agent_state.json` with `code_diffs`. Write to `data/loop_state.json` under `data_collection`.

**Exit condition:** All datasets built/rebuilt, counts verified.

---

### PHASE 4: TRADING WITH OPENTRADER HARNESS

**Goal:** Run the trading harness and monitor performance.

**Method:**
1. Check harness is running: `pgrep -f 'harness\.py'` — if not, start it:
   ```bash
   cd /home/mrc/opentrader && setsid python3 run_harness.py \
     --live --exchange kraken --stage 2 --cash 100 \
     --max-daily-trades 500 --parallel-debate \
     --llama-host http://127.0.0.1:5802 \
     </dev/null >>/tmp/harness.log 2>&1 &
   ```
2. Wait 60 seconds. Check portfolio state:
   ```bash
   python3 -c "import json; s=json.load(open('data/paper_state.json')); print(f'cash=\${s[\"cash\"]:.2f} pos={len(s.get(\"positions\",[]))} value=\${s.get(\"total_value\",s.get(\"portfolio_value\",0)):.2f}')"
   ```
3. Check for stuck agent (all HOLD):
   ```bash
   python3 -c "import json,sys; sys.path.insert(0,'.'); from training.reward_builder import detect_behavioral_loop; s=json.load(open('data/agent_state.json')) or {}; sigs=s.get('_signal_history',[]); stuck,d=detect_behavioral_loop(sigs); print(f'stuck={stuck} type={d.get(\"loop_type\")} dominant={d.get(\"dominant_action\")} ratio={d.get(\"dominant_ratio\")}')"
   ```
4. Check trade journal has recent entries: count trades in last 50 cycles.
5. Check coach report: `python3 -c "import json; r=json.load(open('data/coach_report.json')); print(f'grade={r.get(\"grade\")} retrain={r.get(\"retrain_recommended\")} confidence={r.get(\"confidence\",0)}')"`
6. If stuck OR grade is D/F: trigger behavioral RL training: `python3 -c "import sys; sys.path.insert(0,'.'); from training.rl_trainer import BehavioralRLTrainer; t=BehavioralRLTrainer(state_dir='data',min_examples=1); s,r=t.should_train(); print(f'{s} {r}'); [print(t.step()) if s else None]"`
7. Check dashboard is reachable: `curl -s http://localhost:8098/ | head -1`

**Artifacts produced:** Trading signals, trade journal entries, coach reports, portfolio state updates. Write to `data/loop_state.json` under `trading`.

**Exit condition:** Harness running, signals producing, >5 trades in journal OR explicit issue detected.

---

### PHASE 5: ITERATION & IMPROVEMENTS

**Goal:** Apply RL training, update adapters, tune configuration.

**Method:**
1. Check if behavioral RL training should run:
   ```bash
   python3 -c "from training.idle_trainer import IdleTrainer, check_llama_idle; i,_=check_llama_idle(); print(f'GPU idle: {i}')"
   ```
2. If GPU idle and training warranted: `python3 training/idle_trainer.py --force --mode trading`
3. For coding agent improvement: `python3 training/idle_trainer.py --force --mode coding`
4. Check adapter registry: `python3 -c "from mot.adapter_registry import AdapterRegistry; r=AdapterRegistry('data'); print(r.get_adapter_for_dashboard())"`
5. If new adapter trained and eval score > current: `python3 scripts/load_adapter.py` (hot-loads if supported, otherwise marks for next restart)
6. Run parameter optimizer: `python3 -c "from risk.param_optimizer import run_cycle; run_cycle('data', 0, force=True)"`
7. Tune risk config based on recent performance: read `data/coach_report.json` → if `position_sizing` says "increase" or "decrease", adjust `risk/manager.py` `RiskConfig` accordingly.
8. Update `data/loop_state.json` with iteration results.
9. Check ATDL lifecycle state: `python3 -c "import json; a=json.load(open('data/atdl_state.json')); print(f'phase={a.get(\"phase\")} variants={len(a.get(\"variants\",[]))}')"`
10. If ATDL in MONITOR with D/F grade for >500 cycles, trigger PLAN transition.

**Artifacts produced:** Trained adapters, updated parameters, config changes. Write to `data/loop_state.json` under `iteration`.

**Exit condition:** Training completed OR cooldown active OR insufficient data. Return to Phase 1.

---

## LOOP CONTROL

At the start of each session, read `data/loop_state.json`. If it doesn't exist, create it:

```json
{
  "session": "2026-07-24",
  "cycle": 0,
  "phase": "bug_hunt",
  "bug_hunt": {"passes": 0, "bugs_found": 0, "bugs_fixed": 0},
  "research": {"papers_fetched": 0, "features_extracted": 0},
  "data_collection": {"datasets_built": 0, "examples_total": 0},
  "trading": {"cycles_run": 0, "trades_executed": 0, "grade": "N/A"},
  "iteration": {"trainings_run": 0, "adapters_trained": 0, "adapters_loaded": 0}
}
```

Each phase updates its section. After Phase 5, increment `cycle` and return to Phase 1. The loop never terminates — it's continuous improvement.

## PRIORITY RULES

1. **Bug hunting always comes first** — a buggy system trains on garbage data.
2. **If harness is down, prioritize restart** over all else.
3. **If stuck agent detected (all HOLD, coach grade D/F), skip to Phase 5** to trigger behavioral RL.
4. **VRAM training lock** — training and trading cannot coexist. Training takes priority if agent is stuck; trading takes priority if agent is profitable.
5. **Every 10 cycles**, check for new llama-server releases or model improvements via `modelfixer`.

## QUICK HEALTH CHECK

```bash
cd /home/mrc/opentrader && python3 -c "
import json, os, subprocess, time
state = {}
for f in ['paper_state.json','agent_state.json','coach_report.json','atdl_state.json']:
    p = f'data/{f}'
    if os.path.exists(p):
        state[f] = json.load(open(p))
    else:
        state[f] = None

p = state.get('paper_state.json',{})
a = state.get('agent_state.json',{})
c = state.get('coach_report.json',{})
atdl = state.get('atdl_state.json',{})

print(f\"Portfolio: \${p.get('total_value',p.get('portfolio_value','?')):.2f}\")
print(f\"Cash: \${p.get('cash','?'):.2f}\")
print(f\"Positions: {len(p.get('positions',[]))}\")
print(f\"Trades (journal): {len(a.get('_trade_journal',[]))}\")
print(f\"Signals (history): {len(a.get('_signal_history',[]))}\")
print(f\"Coach grade: {c.get('grade','N/A')}\")
print(f\"ATDL phase: {atdl.get('phase','N/A')}\")
print(f\"Loop state exists: {os.path.exists('data/loop_state.json')}\")

# Harness alive?
try:
    r = subprocess.run(['pgrep','-f','harness.py'], capture_output=True, text=True)
    print(f\"Harness: {'RUNNING' if r.returncode==0 else 'STOPPED'}\")
except:
    print('Harness: UNKNOWN')
"
```
