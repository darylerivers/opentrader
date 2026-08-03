# OpenTrader codebase — physical molecular model recipe

Build a ball-and-stick model: each **module is a colored atom**, each
**dependency (import) is a bond stick**. Colors match the render.

## Atoms (modules)

| # | Atom (module) | Role | Element | Kit color |
|---|---------------|------|---------|-----------|
| 1 | harness.py | hub | N | #e63946 |
| 2 | mcp_server.py | service | F | #457b9d |
| 3 | dashboard.py | ui | F | #a8dadc |
| 4 | tui_dashboard.py | ui | F | #a8dadc |
| 5 | mot | agents | O | #f4a261 |
| 6 | exchange | data-io | S | #2a9d8f |
| 7 | risk | risk | S | #e9c46a |
| 8 | setup_search | research | P | #9b5de5 |
| 9 | training | training | P | #f15bb5 |
| 10 | data | core | C | #4cc9f0 |
| 11 | state | core | C | #4cc9f0 |
| 12 | agent | agents | O | #f4a261 |
| 13 | tools | util | F | #8d99ae |
| 14 | charts | ui | F | #a8dadc |
| 15 | scripts | util | F | #8d99ae |
| 16 | coordinator.py | training | P | #f15bb5 |
| 17 | connections.py | core | C | #4cc9f0 |
| 18 | model_manager.py | training | P | #f15bb5 |
| 19 | onchain.py | data-io | S | #2a9d8f |
| 20 | gpu_sync.py | service | F | #457b9d |
| 21 | run_harness.py | service | F | #457b9d |
| 22 | tests | util | F | #8d99ae |
| 23 | data_mgmt.py | core | C | #4cc9f0 |

## Bonds (dependencies)

- harness.py → mot
- harness.py → exchange
- harness.py → risk
- harness.py → setup_search
- harness.py → training
- harness.py → data
- harness.py → state
- harness.py → agent
- mcp_server.py → mot
- mcp_server.py → exchange
- mcp_server.py → risk
- mcp_server.py → data
- mcp_server.py → state
- mcp_server.py → tools
- mcp_server.py → charts
- mot → exchange
- mot → setup_search
- mot → training
- mot → data
- mot → tools
- mot → tests
- exchange → risk
- exchange → data
- exchange → state
- risk → data
- risk → state
- setup_search → data
- training → data
- training → state
- training → agent
- data → state
- data → agent
- data → model_manager.py
- data → gpu_sync.py

## Color legend

- hub: #e63946
- service: #457b9d
- ui: #a8dadc
- agents: #f4a261
- data-io: #2a9d8f
- risk: #e9c46a
- research: #9b5de5
- training: #f15bb5
- core: #4cc9f0
- util: #8d99ae
