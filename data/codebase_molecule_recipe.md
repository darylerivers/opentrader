# OpenTrader codebase — physical molecular model recipe

Build a ball-and-stick model: each **module is a colored atom**, each
**dependency (import) is a bond stick**. Colors match the render.

## Atoms (modules)

| # | Atom (module) | Role | Element | Kit color |
|---|---------------|------|---------|-----------|
| 1 | harness.py | hub | N | #1f6feb |
| 2 | mcp_server.py | service | H | #f8f9fa |
| 3 | dashboard.py | ui | Cl | #2a9d8f |
| 4 | tui_dashboard.py | ui | Cl | #2a9d8f |
| 5 | mot | agents | O | #d62828 |
| 6 | exchange | data-io | S | #f4d35e |
| 7 | risk | risk | Cl | #2a9d8f |
| 8 | setup_search | research | P | #8338ec |
| 9 | training | training | O | #d62828 |
| 10 | data | core | C | #222222 |
| 11 | state | core | C | #222222 |
| 12 | agent | agents | O | #d62828 |
| 13 | tools | util | C | #222222 |
| 14 | charts | ui | Cl | #2a9d8f |
| 15 | scripts | util | C | #222222 |
| 16 | coordinator.py | training | O | #d62828 |
| 17 | connections.py | core | C | #222222 |
| 18 | model_manager.py | training | O | #d62828 |
| 19 | onchain.py | data-io | S | #f4d35e |
| 20 | gpu_sync.py | service | H | #f8f9fa |
| 21 | run_harness.py | service | H | #f8f9fa |
| 22 | tests | util | C | #222222 |
| 23 | data_mgmt.py | core | C | #222222 |

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

- hub: #1f6feb
- core: #222222
- agents: #d62828
- data-io: #f4d35e
- risk: #2a9d8f
- research: #8338ec
- training: #d62828
- service: #f8f9fa
- ui: #2a9d8f
- util: #222222
