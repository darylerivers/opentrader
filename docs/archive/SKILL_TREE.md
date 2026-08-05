# Skill Tree — Live Training Evolution Visualization

Pixel-art neural network visualization showing Ptolemy model evolution
as training progresses. Each neuron = one pixel, connections = lines
between pixels. Colors shift as weights update.

## Layout

32 × 32 pixel grid (1024 neurons). Each pixel's RGB value maps to:
- R: activation strength (0-255, higher = more active)
- G: weight gradient direction (0-127 = decreasing, 128-255 = increasing)
- B: training age (0=first epoch, 255=most recent)

## Layer Architecture

```
  Input(8) → L1(16) → L2(16) → Output(4)
     ↓         ↓         ↓         ↓
  [market] [trend]  [signal]  [action]
```

Each layer is a horizontal band. Connections between layers drawn as
semi-transparent lines colored by weight magnitude.

## Evolution Frames

Snapshot taken every 100 training steps. Stored as `data/skill_tree/frame_NNNN.png`.
Assembled into `data/skill_tree/evolution.gif` or served as live canvas.

Frames are 256×256 px, enlarged from 32×32 with nearest-neighbor (pixel-perfect).

## Implementation

1. `training/skill_tree.py` — generates frames from adapter weights
2. Dashboard renders latest frame as sidebar canvas
3. Click frame → expand into timeline view
