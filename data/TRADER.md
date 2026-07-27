# TRADER.md — Autonomous Trading Knowledge Base

> This document is written by the model itself. Coach reviews distill patterns;
> ATDL lifecycle events capture lessons. It is injected into every debate cycle
> as institutional memory. Pruned and consolidated automatically.

Last updated: 2026-07-16T12:18:39Z
Total entries: 14

## Patterns — reproducible market behaviors
- **[PATTERN]** (c259, conf=70%): Portfolio earned grade B with 60% win rate at cycle 259. Strategy is working — preserve current risk parameters and debate configuration.  _2026-07-16T04:16:24_

- **[PATTERN]** (c1759, conf=64%): Portfolio earned grade B with 54% win rate at cycle 1759. Strategy is working — preserve current risk parameters and debate configuration.  _2026-07-16T10:38:09_

- **[PATTERN]** (c2359, conf=64%): Portfolio earned grade B with 54% win rate at cycle 2359. Strategy is working — preserve current risk parameters and debate configuration.  _2026-07-16T12:18:39_

- **[PATTERN]** (c66935, conf=54%): Portfolio earned grade B with 44% win rate at cycle 66935. Strategy is working — preserve current risk parameters and debate configuration.  _2026-07-14T19:24:54_

- **[PATTERN]** (c66936, conf=54%): Portfolio earned grade B with 44% win rate at cycle 66936. Strategy is working — preserve current risk parameters and debate configuration.  _2026-07-14T22:42:50_


## Rules — hard-won risk management principles
- **[RULE]** (c57200, conf=100%): max_position_cycles=0 (disabled). Positions hold indefinitely unless stop-loss/take-profit/risk-manager trigger exit. No mechanical timeouts.  _2026-07-13T02:14:58_

- **[RULE]** (c57200, conf=90%): Goal: accumulate $270 for MI60 GPU + 64GB RAM + 2TB NVMe hardware upgrade. Current progress tracked per-cycle. Every trade should move toward this target.  _2026-07-13T02:14:58_


## Edges — quantified statistical advantages
- **[EDGE]** (c0, conf=85%): Fee-aware round-trip calculation shows ~0.5% cost on $5 positions via Kraken. Minimum viable position size ~$5-10 to overcome fee drag. Target position notional $10-20 for meaningful returns.  _2026-07-13T02:14:58_


## Lessons — mistakes learned and corrections
- **[LESSON]** (c65545, conf=85%): Portfolio earned failing grade D with 44% win rate. Current strategy is NOT working — retraining or parameter adjustment needed.  _2026-07-13T15:19:17_

- **[LESSON]** (c66932, conf=85%): Portfolio earned failing grade F with 44% win rate. Current strategy is NOT working — retraining or parameter adjustment needed.  _2026-07-14T17:32:44_

- **[LESSON]** (c1059, conf=85%): Portfolio earned failing grade D with 54% win rate. Current strategy is NOT working — retraining or parameter adjustment needed.  _2026-07-16T08:40:56_

- **[LESSON]** (c1700, conf=70%): ADIR risk agent sometimes fails HTTP calls to llama-server (oversized prompts). Heuristic synthesis fallback provides adequate risk voting when this occurs.  _2026-07-13T02:14:58_


## Regime — market state observations
- **[REGIME]** (c57200, conf=90%): Current regime: crypto basket (BTC/ETH/SOL) with ADIR adversarial debate. Stage 2 (unlock: 24h +5% return). MoT force=increase (max_position_pct=0.20, kelly=0.35).  _2026-07-13T02:14:58_


## Skills — capabilities developed
- **[SKILL]** (c54500, conf=80%): Alpha-1 LoRA adapter trained on 189 balanced BUY/SELL/HOLD examples from ~57000 cycle history. Loss converged to 0.725 (from 2.65).  _2026-07-13T02:14:58_

