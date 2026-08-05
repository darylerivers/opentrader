# TOOL.md — DOT Vision Tool Timing System

Tool-call telemetry encoded as pixel DOT values for 10x token density.
Inspired by DeepSeek Vision's research: image-encoded state holds 10x more
information than text tokens, enabling dense instrumentation without context
window pollution.

## DOT Encoding

Each tool interaction produces a 64px × 64px RGB image where each pixel's
color channels encode a specific metric:

```
┌──────────────┬──────────────┬──────────────┐
│ R (tool_id)  │ G (duration) │ B (outcome)  │
├──────────────┼──────────────┼──────────────┤
│ 0=LLM call   │ 0-255:       │ 0=no change  │
│ 1=file read  │ ms/10 mapped │ 1-127: worse │
│ 2=file write │ to 0-255     │ 128=neutral  │
│ 3=bash cmd   │ (max=2.55s)  │ 129-255:     │
│ 4=web fetch  │              │ improved     │
│ 5=MCP tool   │              │ (higher=more)│
│ 6=delegation │              │              │
│ 7=compress   │              │              │
└──────────────┴──────────────┴──────────────┘
```

Each row = one tool invocation (Nth call in session).
First DOT in each row (x=0) is brighter for higher confidence delta.

## Frame Layout

A 512px → 1024px wide strip. Leftmost column = call index. Each tool call
occupies one pixel row. White border marks session boundaries.

Color intensity increases with usage frequency:
- 1-5 calls:  dark tint
- 6-20 calls: medium tint
- 20+ calls:  bright tint

## Agent View

The snake reads DOT strips as: "Tool 3 was used 47 times, average gain +23,
peak improvement after call 31 followed by tool 2 which worsened results."
This is the pixel equivalent of 500+ words of analytic text.

## Implementation

1. `training/tool_dot.py` — writes DOT pixel data to `data/dot_timing.png`
2. Each harness cycle appends new DOT rows for any tool calls made
3. The PNG serves as both analytics and an agent-readable summary
4. Dashboard renders the latest DOT strip as a live-updating canvas
