# Model-Agnostic Agent & Routing Architecture

## Design Principle

Models change weekly. Infrastructure must not. Agents request capabilities, not model names. The router selects the best fit from whatever's available.

---

## Layer 1: Model Registry

```yaml
# ~/.config/opencode/model-registry.yaml
# Source of truth for all available models

models:
  - id: auto           # Reserved: means "router decides"
    
  - id: any-8b-tools   # Virtual: smallest model with tools (currently gemma)
    aliases: [gemma-agentic-32k, qwen2.5-coder-7b]
    blueprint:         # What to pull if nothing matches
      pull: "bartowski/Qwen2.5-Coder-7B-Instruct-GGUF:Q4_K_M"
      ctx: 32768
      gpu: 0           # RTX 3070
    
  - id: any-14b-reasoning  # Virtual: mid-size reasoning model
    aliases: [qwythos-9b-mtp, phi-4-14b, qwen3.5-moe-14b]
    blueprint:
      pull: "bartowski/Phi-4-mini-instruct-GGUF:Q4_K_M"
      ctx: 16384
      gpu: 0
    
  - id: any-27b-heavy  # Virtual: large model for hard problems
    aliases: [qwen35-opus-distil-27b, deepseek-coder-v2-lite-16b]
    blueprint:
      pull: "bartowski/Qwen2.5-32B-Instruct-GGUF:IQ3_XXS"
      ctx: 8192
      gpu: 1           # RX 7900 (when not gaming)
    
  - id: any-small-fast  # Virtual: tiny model for quick tasks
    blueprint:
      pull: "bartowski/Qwen2.5-1.5B-Instruct-GGUF:Q8_0"
      ctx: 4096
      gpu: 0
```

## Layer 2: Capability Router (llama-swap)

```
                   ┌─────────────────────┐
                   │   llama-swap :8080   │
                   │   (capability-based) │
                   └──────────┬──────────┘
                              │
            ┌─────────────────┼──────────────────┐
            ▼                 ▼                   ▼
     ┌────────────┐   ┌────────────┐     ┌──────────────┐
     │ Ollama     │   │ llama-srv  │     │ llama-srv    │
     │ :11434     │   │ :5801      │     │ :5802 (future)│
     │ GPU:0      │   │ GPU:0      │     │ GPU:1        │
     │ small/med  │   │ med/large  │     │ large only   │
     └────────────┘   └────────────┘     └──────────────┘

Routing logic:
  1. Request arrives with capability requirements:
     {tools: true, thinking: true, min_ctx: 8192}
  
  2. Router checks registry for matching models
     Key: aliases point to real model IDs
  
  3. Score each match:
     - GPU affinity (is target GPU free?)
     - VRAM available (is model already loaded? needs swap?)
     - Context match (can model handle requested context?)
     - Latency preference (fast model for simple, slow for complex)
  
  4. If best model is not loaded:
     - Unload current from target GPU
     - Load requested model (~15s for 7B, ~30s for 14B)
     - Route request
```

## Layer 3: Agent Capability Profiles

```jsonc
// opencode.jsonc — agents request capabilities, not models

"agent": {
  "supervisor": {
    "capability": {
      "tools": true,
      "thinking": true,
      "min_context": 8192,
      "prefer": "reasoning"    // prefers reasoning-capable models
    },
    "prompt": "You are Opentrader's Portfolio Manager...",
    "steps": 25
  },
  
  "builder": {
    "capability": {
      "tools": true,
      "min_context": 8192,
      "prefer": "fast"         // prefers fast models for coding
    },
    "steps": 40
  },
  
  "manager": {
    "capability": {
      "tools": true,
      "thinking": true,
      "min_context": 4096,
      "prefer": "reasoning"    // needs decision quality over speed
    }
  },
  
  "qwen-worker": {
    "capability": {
      "tools": true,
      "prefer": "fast"         // speed over everything
    }
  }
}
```

## Layer 4: OpenCode + Router Integration

```
OpenCode session starts
  │
  ▼
Supervisor asks: "I need {tools, thinking, 8K ctx}"
  │
  ▼
Router on :8080 checks registry:
  ├── any-8b-tools matches  →  gemma-agentic-32k (loaded?) N
  ├── any-14b-reasoning     →  phi-4-14b (loaded?) N
  └── any-27b-heavy         →  GPU:1, need to check if free
  
Router scores:
  gemma: score=9 (fits GPU:0, 7.4GB, supports tools+think, fast load)
  phi-4: score=6 (needs download, bigger GPU hit)
  27B:   score=2 (GPU:1 may be gaming, huge VRAM)
  │
  ▼
Router: "Loading gemma-agentic-32k on GPU:0..."
  │
  ▼
Request → Ollama :11434 → gemma-agentic-32k → tool call → done

  ...time passes, gemma idle for 10 min...
  
  │
  ▼
Builder asks: "I need {tools, fast, 4K ctx}"
  │
  ▼
Router: gemma is loaded and matches → use it, no swap needed

  ...later, gemma idle for 30 min, auto-unloaded...
  
  │
  ▼  
Supervisor asks: "I need {thinking, 32K ctx}"
  │
  ▼
Router: gemma too small context. any-14b-reasoning matches.
  Unload gemma → load qwythos-9b-mtp (~15s) → response
```

## Layer 5: Model Lifecycle

```
                          Pull Trigger
  ┌────────────┐          (blueprint.missing)
  │ Registry   │─────────▶ Pull from HF (GGUF)
  │ YAML       │          │
  └────────────┘          ▼
       │            ┌──────────┐
       │ registers  │ Ollama / │
       ▼            │ llama.cpp│
  ┌────────────┐    └────┬─────┘
  │ Router     │◀────────┘ registers
  │ :8080      │
  └─────┬──────┘
        │
        ├──▶ GPU:0 (RTX 3070) — small/medium models
        │    ⤷ Hot-swap between agent/trading models
        │
        └──▶ GPU:1 (RX 7900) — large models, training
             ⤷ Only when not gaming
```

## GPU Allocation Strategy

```
Priority levels for GPU:0 (RTX 3070, 8GB):

  1. OpenCode session active?
     → Load: any-8b-tools (agent model, ~7.5GB)
     → Trading harness pauses during interactive sessions
     
  2. Trading harness running?
     → Load: any-14b-reasoning (trading model, ~5.5GB)
     → OpenCode sessions wait ~15s for model swap
     
  3. Neither active?
     → Unload all, free VRAM
```

## What This Breaks Free From

| Old Way | New Way |
|---------|---------|
| "gemma-agentic-32k" hardcoded in config | Router selects best match from registry |
| Model changes = config edits | Model changes = registry update only |
| One model per agent | Agents request capabilities, router picks |
| GPU locked to one model | Models swap between GPUs by demand |
| Deleted model = crash | Router falls back to next best match |
| "Bad gateway" on cold load | Router pre-loads or queues until ready |
