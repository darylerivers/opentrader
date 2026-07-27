graph TB
    subgraph HARNESS["HARNESS LOOP — every ~10s (2612 lines)"]
        H1["Fetch OHLCV<br/>+ regime + macro"] --> H2["Build Context<br/>(bars, indicators, portfolio)"]
        H2 --> H3
        subgraph H3["ADIR DEBATE — 4-phase adversarial (762 lines)"]
            A1["Bull Agent<br/>—role: bullish"] --> A4
            A2["Bear Agent<br/>—role: bearish<br/>+ falsification"] --> A4
            A4["Risk Arbiter<br/>Bayesian synthesis<br/>Toulmin evidence_quality"] --> A5["Signal:<br/>BUY/SELL/HOLD<br/>+ confidence"]
        end
        A5 --> H4["Execute Trade<br/>(paper or live)"]
        H4 --> H5["Journal + Reflect<br/>→ reflection_log.json"]
        H5 --> H6["Monitor Committee<br/>(234 lines, no LLM)"]
        H6 --"drawdown breach"--> CB["CIRCUIT BREAKER<br/>auto-pause + recover"]
        H6 --"healthy"--> H1
        H5 -.->|"outcome feedback"| A2
    end

    subgraph TRAIN["TRAINING LOOP — ATDL Lifecycle (496 lines)"]
        T1["Coach<br/>(365 lines)<br/>reviews journal<br/>grades A-F"] --> T2["Research Scout<br/>arXiv + HF Hub sweep<br/>(824 lines)"]
        T2 --> T3["Capability Distiller<br/>findings → scenarios"]
        T3 --> T4["Programmatic Teacher<br/>6 scenario types<br/>ground-truth labels"]
        T4 --> T5["Fine-tune<br/>QLoRA + Unsloth<br/>(finetune_cycle.py)"]
        T5 --> T6["Deep Eval<br/>7 dimensions<br/>(deep_eval.py)"]
        T6 --"score ≥ active + 3.0"--> T7["Deploy Gate<br/>promote + update<br/>llama-dynamic script"]
        T6 --"score < gate"--> T8["Rollback / iterate"]
        T7 --> T9["Adapter Registry<br/>version lineage<br/>(282 lines)"]
        T9 -.->|"new LoRA"| H3
    end

    subgraph AUTO["AUTONOMY LAYER"]
        C1["MoT Coordinator<br/>(322 lines)<br/>6h self-scheduling"] --> C2["Model Pool<br/>(519 lines)<br/>VRAM-aware LoRA swap"]
        C1 --> C3["Ensemble<br/>(296 lines)<br/>5-persona voting"]
        M1["MCP Server<br/>19 tools"] -.-> H1
        M1 -.-> T5
        DOT["DOT Telemetry<br/>pixel-encoded<br/>tool calls"] -.-> H3
    end

    T7 -.->|"SIGHUP reload"| LS["llama-swap :8080<br/>smart-router<br/>one model in VRAM"]
    LS -.-> H3

    style H3 fill:#1a1a2e,stroke:#e94560,stroke-width:2px,color:#fff
    style T6 fill:#16213e,stroke:#0f3460,stroke-width:2px,color:#fff
    style CB fill:#533483,stroke:#e94560,stroke-width:2px,color:#fff
    style LS fill:#0f3460,stroke:#00adb5,stroke-width:2px,color:#fff