# Architect prompt design — LOCAL model, trained in-house

**Research decision for map "Curriculum forge: GPU1 trains GPU0 via skill curriculum"**
**Correction from the chart:** no cloud model anywhere. The Architect is a
qwen-2.5-7b QLoRA fine-tune, trained on GPU0 (the arsenal) on a
skill-proposal dataset, served on GPU1. Its only input is the weakness report
rendered from local arena outputs; its only output is a validated skill
proposal JSON.

## 1. Pipeline

```
data/arena/arena_state.json + tech_tree.json
        -> render_weakness_report() -> text
        -> prompt (chat format, <|im_start|>)
        -> Architect model (GPU1, local QLoRA adapter)
        -> JSON proposal
        -> validate against skill schema (numeric-only, dedup, prereq check)
        -> if valid: queue as the next curriculum skill for GPU0
```

## 2. Weakness-report renderer

`arena/architect.py: render_weakness_report(state, tech)` — compact text from
the verified arena outputs (iteration, gate margins + consecutive-pass count,
tech-tree lit/missing, battle standings, h2h, war books, regime decomposition,
bear-relabel count). ~15 lines, all numbers, no prose.

## 3. Prompt template

```
You are the Curriculum Architect for the Momentum trading agent. Read the
weakness report and propose the single next skill that sharpens the agent's
trading ability. Propose skills ONLY when they target a measurable weakness
below its pass bar. Output ONLY a JSON object matching this schema:
{id, name, tier, prerequisites, scenario{window,regime,field}, objective,
 pass_bar, metric_source, rationale} — numeric pass bars, no narrative grading.
If no new skill is warranted, output: {"noop": true, "rationale": "..."}.
```

Temperature 0.2, no retries on schema-invalid output (validate and discard),
dedup against existing + attempted skills by scenario+objective.

## 4. Local training

- Dataset: `data/arena/architect_dataset.jsonl` (built by
  `arena/build_architect_dataset.py` from the seed skills in the taxonomy:
  per skill, a rendered weakness report + the skill proposal as the target;
  ~45-60 examples + noop examples).
- Recipe: identical to the momentum-agent QLoRA (qwen-2.5-7b-Instruct, 4-bit,
  LoRA r=8, 2 epochs, GPU0, ~10-15 min), output adapter to
  `data/gpu_scheduler/adapters/architect/`.
- Serving: llama-server with `--lora` on GPU1 (port 5801/5802 class), or the
  harness's set_finetuned_backend path per the fleet map's precedent.

## 5. Honesty rules

Numeric-only proposals: every pass_bar must reference a metric_source that
exists in arena_state.json or a named recomputation (see the taxonomy doc).
No LLM grading of mastery — the arena grades, the Architect only proposes.
