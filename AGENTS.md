# AGENTS — OpenTrader

OpenTrader is a self-improving trading system: a Mixture of Traders (rule floor +
value-head experts) trained by an adversarial arena. Read `ARCHITECTURE.md` and
`CONTEXT.md` before working — they are the single sources of truth for design and
language. All changes are proven in the sandbox (`opentrader-sandbox`) first; the
live tree and the GPU stay untouched until validated.

## Agent skills

### Issue tracker

Issues live as GitHub issues on `darylerivers/opentrader` (gh CLI). See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical roles, labels equal to their names: `needs-triage`, `needs-info`,
`ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` (glossary) + `docs/adr/` at the repo root, with
`ARCHITECTURE.md` as the canonical design doc. See `docs/agents/domain.md`.
