# Chinese-lab RL foundations: GRPO for the trading arena + a neural market-path generator

**Status:** Research foundation — extracted from primary sources, ready for the iteration-protocol grilling to consume.
**Date:** 2026-08-05
**Builds on:** [Arena reward + war-relabeling protocol](arena-reward-protocol.md) (the `δ_t = (r_t − V(s_t)) + (r_t − r_field_t)` advantage and the value-head loop).
**Destination:** (a) a real GRPO trainer for the small-MLP policy over the arena's engineered state features; (b) a conditional GAN (DoppelGANger-style) or diffusion generator over the **16-symbol × OHLCV** feature space, to fabricate many market scenarios for robustness training.

## Summary

Everything below is quoted from the papers themselves (arXiv HTML / ar5iv / official proceedings / authors' official code). Three of the arXiv IDs I was given were wrong and are corrected here (see Sources): DoppelGANger is **arXiv 1909.13403** (IMC 2020), TimeGAN has **no arXiv version** (NeurIPS 2019 proceedings only), and the best-cited financial GAN is Quant GANs, **arXiv 1907.06673** (Quantitative Finance 2020).

The two load-bearing facts for OpenTrader:

1. **GRPO needs no critic.** The advantage is computed purely *inside each sampled group* as the z-score of the outcome reward, `A_i = (r_i − mean(r_1..r_G)) / std(r_1..r_G)`. This *is* the arena's field-relative margin `(r_t − r_field_t)` from the protocol doc — the "field" is just the group. The critic term `(r_t − V(s_t))` can be kept as a **learned value baseline added to the group-normalized term**, but GRPO's entire point is that it is optional.
2. **The generator should be DoppelGANger, not a bare GAN.** Its three mechanisms — (i) batch generation `S` samples per RNN step (length `T/S ≈ 50`), (ii) per-series auto-normalization with the min/max stored as learned "fake" metadata, (iii) an auxiliary metadata-only discriminator — are exactly the fixes that make a GAN produce long, realistic, non-mode-collapsed multi-dim OHLCV paths on a consumer GPU.

---

## 1. GRPO — DeepSeekMath (arXiv 2402.03300)

DeepSeekMath: Pushing the Limits of Mathematical Reasoning in Open Language Models — Shao, Wang, Zhu, Xu, Song et al., DeepSeek-AI (v3, 2024). GRPO is §4.1; the RL experiment settings are §4.1.4; the appendix A.1.6 gives the gradient form used when there is a single update per exploration.

### 1.1 Why GRPO exists (from PPO, §4.1.1)

PPO optimizes (Eq. 1 of the paper):

`J_PPO(θ) = E[q~P(Q), o~π_θ_old(O|q)] · (1/|o|) Σ_t min[ (π_θ(o_t|q,o_<t)/π_θ_old(o_t|q,o_<t)) · A_t,  clip(π_θ(o_t|q,o_<t)/π_θ_old(o_t|q,o_<t), 1−ε, 1+ε) · A_t ]`

where the advantage `A_t` comes from GAE on a **learned value function** `V_ψ`, which in the LLM setting is a model of the same size as the policy — a huge memory cost. PPO also puts the KL penalty *into the reward* per token (Eq. 2):

`r_t = r_φ(q,o_≤t) − β·log[ π_θ(o_t|q,o_<t) / π_ref(o_t|q,o_<t) ]`

The paper's stated motivation for GRPO (§4.1.1): the value function is "another model of comparable size as the policy model, [which] brings a substantial memory and computational burden," and "in the LLM context, usually only the last token is assigned a reward score by the reward model, which may complicate the training of a value function that is accurate at each token."

### 1.2 The GRPO objective (Eq. 3) and the unbiased KL (Eq. 4)

For each prompt/question `q`, sample a **group** `{o_1,…,o_G}` from the *old* policy `π_θ_old`, then maximize:

`J_GRPO(θ) = E[q~P(Q), {o_i}~π_θ_old(O|q)] · (1/G) Σ_i (1/|o_i|) Σ_t { min[ r_i_t · Â_i,t,  clip(r_i_t, 1−ε, 1+ε) · Â_i,t ]  −  β·D_KL[π_θ || π_ref] }`

with `r_i_t = π_θ(o_i,t|q,o_i,<t)/π_θ_old(o_i,t|q,o_i,<t)` the importance ratio. **Three properties worth quoting exactly:**

1. The KL term is **added directly to the loss, not to the reward** — the paper: "instead of adding KL penalty in the reward, GRPO regularizes by directly adding the KL divergence between the trained policy and the reference policy to the loss, avoiding complicating the calculation of Â_i,t."
2. The KL is the **unbiased estimator** (Eq. 4, after Schulman 2020), guaranteed positive:
   `D_KL[π_θ||π_ref] = (π_ref(o_i,t|q,o_i,<t)/π_θ(o_i,t|q,o_i,<t)) − log[π_ref(o_i,t|q,o_i,<t)/π_θ(o_i,t|q,o_i,<t)] − 1`
3. `ε` and `β` are hyper-parameters; `π_ref` is the reference policy, "usually the initial SFT model."

### 1.3 The group-relative advantage (the core fact)

**Outcome supervision (§4.1.2).** Each of the `G` outputs gets one reward `r_i` from the reward model; normalize the whole group's rewards, then broadcast to every token:

`Â_i,t = r̃_i = (r_i − mean(r)) / std(r)`

**Process supervision (§4.1.3).** Step rewards are normalized the same way (`r̃_i^index(j) = (r_i^index(j) − mean(R))/std(R)`) and the token advantage is the sum of the normalized step rewards at and after the token:

`Â_i,t = Σ_{index(j) ≥ t} r̃_i^index(j)`

### 1.4 Iterative RL (Algorithm 1) and hyper-parameters (§4.1.4)

Iterative GRPO (Algorithm 1): at the start of each **iteration**, copy the current policy to the reference `π_ref ← π_θ`; per step, sample a batch, freeze the old policy `π_θ_old ← π_θ`, sample `G` outputs per question, score them, compute group advantages, then run **μ GRPO update steps** on `π_θ`. Reward model is continuously trained with a replay mechanism.

Exact settings used for DeepSeekMath-RL 7B (§4.1.4, quoted):

> "For GRPO, we set the learning rate of the policy model as 1e-6. The KL coefficient is 0.04. For each question, we sample 64 outputs. The max length is set to 1024, and the training batch size is 1024. The policy model only has a single update following each exploration stage."

So: **G = 64, β = 0.04, policy LR = 1e-6, max len = 1024, batch = 1024, μ = 1.** RL data = ~144K CoT-format GSM8K+MATH questions; the reward model (when used) is trained on DeepSeekMath-Base 7B at LR 2e-5. Result: GSM8K 82.9→88.2, MATH 46.8→51.7 over the Instruct baseline.

### 1.5 The single-update simplification (Appendix A.1.6, Eq. 21)

With **μ = 1** (one update after each exploration stage), `π_θ_old = π_θ` at the moment the update begins, so the ratio is 1 on the first step and the `min`/`clip` machinery is *inactive* for that step. The paper's appendix gradient (Eq. 21) is then:

`∇_θ J_GRPO = E[(1/G) Σ_i (1/|o_i|) Σ_t ( Â_i,t + β·( π_ref(o_i,t|o_i,<t)/π_θ(o_i,t|o_i,<t) − 1 ) ) · ∇_θ log π_θ(o_i,t|q,o_i,<t) ]`

This is the form OpenTrader should implement: **a policy-gradient with per-sample coefficient `Â_i,t + β·(π_ref/π_θ − 1)`**, no critic, no ratio-clip needed for the first epoch of each update.

### 1.6 Start-from hyper-parameters for OpenTrader's small MLP

| Hyper-parameter | DeepSeekMath value | OpenTrader starting point |
|---|---|---|
| Group size G | 64 | 8–16 (small MLP, cheap rollouts; Qwen2.5 used 8) |
| KL coefficient β | 0.04 | 0.04 (scale if KL explodes) |
| Policy LR | 1e-6 | 1e-4–1e-3 (MLP, not LLM — tune via held-out gate) |
| GRPO updates per rollout μ | 1 | 1 |
| Advantage | `(r_i − mean)/std` within group | `(r_i − mean)/std` over the round's field |
| Clip ε | not numerically published | 0.2 (standard PPO/GRPO practice; see notes) |

*Note on ε:* the DeepSeekMath/R1/V3 papers define `ε` symbolically in the objective but never publish its numeric value; 0.2 is the value used across the PPO/GRPO literature (Schulman et al. 2017, and the TRL GRPO reference implementation). Treat it as inherited, not paper-published.

---

## 2. DeepSeek-R1 — arXiv 2501.12948

DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning — DeepSeek-AI (2025; also Nature 645, 633–638).

### 2.1 GRPO as used for RL (§2.2.1)

Same algorithm, written at the **sequence level** in this paper (Eq. 1–3):

`J_GRPO(θ) = E[q~P(Q), {o_i}~π_θ_old(O|q)] · (1/G) Σ_i ( min(π_θ(o_i|q)/π_θ_old(o_i|q)·A_i,  clip(...,1−ε,1+ε)·A_i) − β·D_KL(π_θ||π_ref) )`

`D_KL(π_θ||π_ref) = π_ref(o_i|q)/π_θ(o_i|q) − log[π_ref(o_i|q)/π_θ(o_i|q)] − 1`

`A_i = (r_i − mean({r_1,…,r_G})) / std({r_1,…,r_G})`

### 2.2 Rule-based rewards — why no learned reward model (§2.2.2)

R1-Zero trains with **only two reward types**:

- **Accuracy rewards:** deterministic verification — math answers in a specified box, LeetCode answers run through a compiler against test cases.
- **Format rewards:** the reasoning must sit inside `<think>…</think>` tags, answer inside `<answer>…</answer>` (Table 1 template).

The authors **deliberately avoid outcome/process neural reward models**: "we find that the neural reward model may suffer from reward hacking in the large-scale reinforcement learning process, and retraining the reward model needs additional training resources and it complicates the whole training pipeline." This is the "verifiable" definition: **a reward is verifiable when the correctness check is rule/program-based, so the reward cannot be gamed and needs no learned model.** For OpenTrader the analogue is the realized forward return and head-to-head P&L — computed, not learned.

### 2.3 The multi-stage recipe (§2.1–2.4)

R1-Zero: RL directly on the base model, no SFT (AIME pass@1 15.6%→71.0%). R1 instead:

1. **Cold-start SFT:** thousands of long-CoT examples fine-tune DeepSeek-V3-Base (readability + a better RL starting point).
2. **Reasoning RL:** same GRPO as R1-Zero on math/code/science/logic, with a language-consistency reward summed into the accuracy reward.
3. **Rejection sampling + SFT (~800k samples):** ~600k reasoning trajectories sampled from the converged RL checkpoint (only correct ones kept) + ~200k non-reasoning samples; fine-tune V3-Base for 2 epochs.
4. **RL for all scenarios:** second GRPO stage with rule rewards for reasoning data + reward-model/preference data for general helpfulness/harmlessness.

### 2.4 Distillation — the small-model path (§2.4, §4.1)

The distilled models (1.5B/7B/8B/14B/32B/70B) are made by **plain SFT on the 800k R1-curated samples**, no RL stage: "For distilled models, we apply only SFT and do not include an RL stage." Base models: Qwen2.5-Math-1.5B/7B, Qwen2.5-14B/32B, Llama-3.1-8B, Llama-3.3-70B-Instruct. §4.1 makes the strategic point for OpenTrader's small models: RL from scratch on a 32B base (~10k+ steps) matched QwQ-32B-Preview, but **distillation from a stronger teacher beat RL on the same small model** — i.e. for a small policy, teacher (distilled/imitation) signal is usually more efficient than pure on-policy RL.

---

## 3. DeepSeek-V3 — arXiv 2412.19437 (engineering-scheme context)

DeepSeek-V3 Technical Report — DeepSeek-AI (2024). We will not build these, but each has a "small-model on consumer GPU" read.

### 3.1 Multi-Token Prediction (MTP), §2.2

`D` sequential modules predict `D` extra future tokens per position; module `k` combines the previous depth's representation with the embedding of the token at position `i+k` (Eq. 21–23), and the extra loss is (Eq. 24–25):

`L_MTP = (λ/D) Σ_k CrossEntropy(P^k_{2+k:T+1}, t_{2+k:T+1})`

with a shared embedding and shared output head (kept physically on one pipeline rank for memory). Ablation (§4.5.1): MTP helps data efficiency and downstream benchmarks. **Consumer-GPU read:** only the *idea* is transferable — predicting `K` future returns from the same head-embedding is a cheap data-efficiency trick, but the sequential-module machinery is LLM-scale.

### 3.2 Fine-grained MoE + shared expert, §2.1.2

`h'_t = u_t + Σ_{i=1}^{N_s} FFN_i^(s)(u_t) + Σ_{i=1}^{N_r} g_{i,t}·FFN_i^(r)(u_t)` (Eq. 12), with sigmoid token-expert affinity `s_{i,t} = Sigmoid(u_t^T e_i)` (Eq. 15) and top-K routing. Load balance is achieved **auxiliary-loss-free** via a per-expert routing bias `b_i` adjusted by ±γ at each step (Eq. 16), plus a tiny sequence-wise balance loss `L_Bal = α Σ f_i P_i` (Eq. 17). **Consumer-GPU read:** an "MLP of experts with a learned router" could give the arena's generator/actor more capacity per FLOP, but for 8–16GB a single dense MLP is the right first build.

### 3.3 FP8 training, §3.3

Fine-grained FP8 mixed precision: FP8 GEMMs (Fprop/Dgrad/Wgrad) with FP32 accumulate and master weights/optimizer states in higher precision; activations cached and dispatched in FP8; embedding/output-head/gating/norm/attention kept in BF16/FP32. Validated at ~1T tokens: **relative loss error vs BF16 baseline < 0.25%** (§3.3). **Consumer-GPU read:** torch `bfloat16` autocast + `torch.compile` is the free version of this — keep master weights and optimizer states in fp32, cast activations on the fly. This is the one V3 scheme worth copying directly for the MLP actor and the GAN.

### 3.4 GRPO in V3 post-training, §5.2

Same GRPO equations as R1 (sequence-level objective, unbiased KL, `A_i = (r_i − mean)/std`). Rule-based RM is preferred wherever possible: "By leveraging rule-based validation wherever possible, we ensure a higher level of reliability, as this approach is resistant to manipulation or exploitation" (§5.2.1).

---

## 4. Qwen2.5 — arXiv 2412.15115 (small-model base training)

Qwen2.5 Technical Report — Qwen Team (2024). Full text read via the report's Hugging Face mirror (ar5iv/arXiv HTML are broken for this paper).

### 4.1 What makes the small models (0.5B/1.5B/3B/7B) usable as LoRA/QLoRA bases

- **Same high-quality pre-training at every scale:** 18T tokens (up from 7T), with better data filtering (Qwen2-Instruct as a quality scorer), math/code data sourced from Qwen2.5-Math/Coder, synthetic data from Qwen2-72B-Instruct filtered by reward models, and a rebalanced domain mixture (down-sample e-commerce/social, up-sample science/tech/academic) (§3.1).
- **Scaling-law-tuned hyper-parameters** for each size, including batch size and LR, so even 0.5B trains stably (§3.2).
- **The post-training tie-in is the point for us:** the abstract states it directly — "In terms of post-training, we implement intricate supervised finetuning with over 1 million samples, as well as multistage reinforcement learning, including offline learning DPO and online learning GRPO." The base models are *built to be fine-tuned and RL'd*; R1's distilled 1.5B/7B models are literally Qwen2.5 bases, which is why they LoRA/QLoRA cleanly.
- Results: Qwen2.5-3B hits 65.6 MMLU / 42.6 MATH / 79.1 GSM8K; 0.5B beats Gemma2-2.6B on math/coding (§5.1, Table 5).

### 4.2 Their online GRPO settings (§4.3)

Online RL uses GRPO with a preference-trained reward model. Two numbers worth copying:

- **8 responses sampled per query** (G = 8 — the small-model group size; DeepSeekMath used 64 at 7B).
- Global batch size 2048, 2048 samples per episode; queries prioritized by reward-model score variance (high-variance queries first). SFT: 1M+ samples, 2 epochs, seq len 32,768, LR 7e-6→7e-7, weight decay 0.1, grad clip 1.0. Offline stage = DPO on ~150k preference pairs.

---

## 5. DoppelGANger — arXiv 1909.13403 (the generator reference architecture)

⚠️ *The supplied ID 2103.06495 is ABINet (scene-text recognition), not DoppelGANger.* The paper is "Using GANs for Sharing Networked Time Series Data: Challenges, Initial Promise, and Open Questions" — Lin, Jain, Wang, Fanti, Sekar, **IMC 2020, arXiv 1909.13403** (the "DoppelGANger: Generating High Fidelity Time Series with GANs" title is the later/renamed presentation of the same work).

Data model (§3.1): a sample `O = (A, R)` = `m` metadata attributes + a variable-length time series `R` of `K` measurements per record. The goal: learn a generative model of the full joint so downstream (predictive models, algorithm comparison) transfers to real data.

### 5.1 The three design mechanisms (exactly why we build it this way)

1. **Batch generation for long sequences (§4.1).** A plain LSTM generator emits one record per RNN pass; beyond a few hundred steps it "takes too many passes … the more passes taken, the more temporal correlation RNNs tend to forget." Instead each RNN pass emits **`S` records at once**, cutting passes by `S`. "Even a small (but larger than 1) S gives substantial improvements in signal quality"; **`S = 5` works well**, and the practical rule is to set `S` so `T/S ≈ 50` RNN steps (§4.4).
2. **Auto-normalization against mode collapse (§4.2).** Financial/measurement series have wildly different ranges across samples; training on globally-normalized data keeps the mode-collapse problem. Fix: **normalize each series individually** and store `(max − min)/2` (i.e. the min/max) as **"fake" metadata** that the generator learns to output; the normalized series are then rescaled back by the generated limits. All series now share a range at generation time → no collapse.
3. **Auxiliary discriminator for metadata (§4.3).** Jointly generating metadata+series over-concentrates the discriminator's judgment; when sequences are long, metadata fidelity collapses. Fix: a **second discriminator over metadata only**, losses combined as `min_G max_D1,D2  L_1(G,D_1) + α·L_2(G,D_2)`, both Wasserstein (WGAN) losses, `α` a weighting parameter. Generator flow (§4.3): MLP generates real metadata → a second MLP generates the fake min/max metadata from it → the LSTM-with-batch generator produces measurements conditioned on the metadata at every step (§4.4, Figure 7). Timestamps, when important, become metadata (sample start time) + a measurement (inter-arrival times) (§4.1).

### 5.2 What they report (§5.2)

- **Autocorrelation fidelity:** DG reproduces the WWT dataset's weekly spikes and ~1-year peak; autocorrelation MSE is **91.2% lower than the closest baseline (RCGAN)**.
- **Attribute distributions:** (max+min)/2 histogram matched with the auxiliary discriminator (tails preserved); Wasserstein-1 distance between generated and real CDFs of total bandwidth per ISP-tech class.
- **Downstream "train on synthetic, test on real":** predictors trained on DG data beat baselines with test accuracy **up to 43% higher**.
- Resource note: DG trained on only 500 samples still beats baselines trained on 50,000 on autocorrelation MSE.

### 5.3 Start-from hyper-parameters

| Hyper-parameter | DoppelGANger | OpenTrader start |
|---|---|---|
| Batch size S (records per RNN step) | 5 (or T/S ≈ 50) | 5–10 on 24-bar OHLCV windows |
| Discriminator | auxiliary metadata D + main series D, Wasserstein | same, α = 1 |
| Generator | LSTM (or GRU), metadata MLPs | GRU + 2 MLPs |
| Preprocessing | per-series min-max normalization, limits as fake metadata | per-symbol/feature min-max, per-symbol limits |
| WGAN | Wasserstein loss | WGAN-GP (gradient penalty) if unstable |

---

## 6. TimeGAN — NeurIPS 2019 proceedings (no arXiv)

⚠️ *The supplied ID 1909.11659 is "Duality family of scalar field" (physics).* TimeGAN has **no arXiv preprint**; the primary source is the NeurIPS 2019 proceedings (paper hash `c9efe5f26cd17ba6216bbe2a7d26d490`, "Time-series Generative Adversarial Networks", Yoon, Jarrett, van der Schaar). Equations below are from the paper (as reflected in the authors' official `jsyoon0823/TimeGAN` implementation).

### 6.1 Embedder / Supervisor / Recovery / Adversarial setup

Four networks operate on a learned latent space rather than raw data:

- **Embedder** `E: X → H` maps real sequences to embeddings; **Recovery** `R: H → X̃` maps embeddings back to the original space.
- **Generator** `G: Z → Ê` produces embeddings from noise; **Supervisor** `S: H → Ĥ` produces the *next-step* embedding, enforcing temporal dynamics; the **Discriminator** `D` classifies real-vs-fake in embedding space.

### 6.2 Losses (per the paper / official code)

- Reconstruction: `L_Recon = E[ ||X − X̃||_2 ]` (embedder+recovery trained first on this alone).
- Supervised next-step loss: `L_Sup = E[ || H_{t+1} − S(H_t) ||_2 ]` — the "control" that keeps dynamics faithful.
- Adversarial: `min_G max_D E[log D(H)] + E[log(1 − D(Ĥ))]`.
- Joint objective combines all three (embedding + supervision + adversarial).

### 6.3 Training procedure (official code)

1. **Embedder-only**: reconstruct X from H (recovery). 2. **Supervised-only**: train generator+supervisor on `L_Sup`. 3. **Joint**: alternate — 2 generator updates per discriminator update; the discriminator is only updated when its loss exceeds 0.15. Defaults: GRU/LSTM, `hidden_dim` = sequence dim, iterations 50k, batch 128, Adam. Every sequence is min-max scaled per feature to [0,1]; generation renormalizes with the training min/max.

### 6.4 "Train on synthetic, test on real" evaluation

The official `metrics/` code defines the two metrics OpenTrader should reuse for its generator:

- **Discriminative score**: train a post-hoc RNN to classify synthetic vs real; lower score (≈0.5) = more realistic.
- **Predictive score**: train a post-hoc RNN on synthetic to predict one-step-ahead features, evaluate on real data; lower MAE = better dynamics. (This is the TimeGAN/DoppelGANger "train on synthetic, test on real" paradigm.)

---

## 7. Quant GANs — arXiv 1907.06673 (financial, optional reference)

⚠️ *The supplied ID 1907.06643 is an asteroid paper.* The most-cited financial time-series GAN is "Quant GANs: Deep Generation of Financial Time Series" — Wiese, Knobloch, Korn, Kretschmer, Quantitative Finance 2020, **arXiv 1907.06673**.

### 7.1 Architecture

Generator = **SVNN (Stochastic Volatility Neural Network)**, built on **TCNs** (dilated causal convolutions, WaveNet-style) for both generator and discriminator (§3.2, §5.1). Log-return process is decomposed exactly like a stochastic-volatility model:

`R_t,θ = σ_t,α ⊙ ε_t,β + μ_t,α`

where the volatility `σ_t,α = |h_{t,1:N_X}|` and drift `μ_t,α = h_{t,(N_X+1):2N_X}` come from a TCN over the *past* latent window `Z_{t−T(g):t−1}`, and the innovation `ε_t,β = g_β^(ε)(Z_t)` from a network over the *current* noise (§5.1, Eq. 1). Receptive field `T^(f) = 1 + (K−1)·(D^L − 1)/(D − 1)` (§3.2) sets how far back the generator can see. Heavy tails (volatility clustering, leverage effect, fat tails — the stylized facts of §2) are handled by a **Lambert W × F_X transformation** applied to the log-returns before training (§5.3), since a Gaussian-input neural process otherwise has all moments finite.

### 7.2 What to borrow vs. skip

- **Borrow:** the volatility-innovation decomposition (`R = σ⊙ε + μ`) is a natural inductive bias for OHLCV — let a TCN (or GRU) read the last `W` bars and emit the next bar's location + scale, with a separate innovation path. This is effectively a conditional generator and is the closest thing the financial literature has to a "regime-aware" conditioning: it conditions on the *past window of the path itself*.
- **Skip (for now):** the risk-neutral transition machinery and Lambert W estimation are pricing-domain extras. A conditional DoppelGANger-style GAN already conditions on a real past window; if regime conditioning is needed later, feed a regime label (bear/bull/range from the arena's regime windows) in as metadata the DoppelGANger way.

---

## 8. How this maps to OpenTrader

### 8.1 GRPO → replace `arena/agent.py`'s MSE-relabel with policy gradient

Current loop (`arena/agent.py`): `ArenaMLP` regresses per-row targets (war-relabeled `r̃_t = r_t + η·δ_t`) with `MSELoss`; the protocol's `δ_t = (r_t − V(s_t)) + (r_t − r_field_t)` is a *target augmentation*. The GRPO read:

- The **group-relative term is already in the protocol**: `(r_t − r_field_t)` *is* `(r_i − mean(r_1..r_G))` when the group = the round's field. GRPO's normalization within a group (§1.3, Eq: `A_i = (r_i − mean)/std`) is exactly the arena's field-relative z-score from the reward-protocol doc.
- **Drop the critic, or keep it as an optional learned baseline.** GRPO's design point (§1.1) is that the value head is the expensive/fragile part; the group baseline replaces it. For a small MLP the honest build is: `A_i,t = (r_i − mean(r_1..r_G))/std(r_1..r_G)` (outcome supervision), with the policy gradient loss `−Σ Â_i,t · log π_θ(a_t|s_t) + β·D_KL(π_θ||π_ref)` (Eq. 3/21). The value head `V(s_t)` can be *kept* by adding `(r_i − V(s_i))` inside the normalization's numerator — a PPO/GRPO hybrid — but the paper says the group mean suffices.
- **The policy is stochastic, not a threshold.** `make_agent` currently returns `(1 if v ≥ theta else 0)`. GRPO needs `π_θ(a|s)` — e.g. a 2-output softmax over {TAKE, SKIP}, or a Bernoulli head — so `log π_θ(a_t|s_t)` exists for the gradient. The value/theta head can remain as the *gate*, separately.
- **Ground-truth hyper-parameters:** start `G = 8` (Qwen2.5, §4.2), `β = 0.04` (DeepSeekMath §1.4), `μ = 1`, advantage as the group z-score, clip 0.2 only if doing multi-epoch updates. Keep the held-out discrimination gate exactly as the protocol doc defines it — GRPO changes the *update*, not the *gate*.

### 8.2 Generator → conditional DoppelGANger-style GAN in torch over 16-symbol × OHLCV

Over the arena's 16-symbol × OHLCV feature space (however it is currently tensored in `arena/candidates.py` / the data loader):

- Sample = one symbol's `T`-bar OHLCV window + a small metadata vector (symbol id, regime label, maybe session). 
- Generator: metadata MLP → per-symbol min/max "fake metadata" MLP → GRU with **batch generation** (`S = 5`, `T/S ≈ 50` on a 24–250 bar window) outputting normalized OHLCV, rescaled by the generated limits (DoppelGANger §4.1–4.3).
- Discriminators: a WGAN discriminator on the (normalized) series + an auxiliary discriminator on the metadata, losses combined `L_1 + α·L_2` (§4.3).
- Evaluation is the TimeGAN/DoppelGANger pair: **autocorrelation MSE** over lags vs real data, **discriminative score** (post-hoc RNN classifying real vs synthetic), and **predictive score** ("train the value head on synthetic, gate it on real" — the exact "train on synthetic, test on real" protocol of §5.2/§6.4, which is the robustness-training goal). 
- If a pure-diffusion path is preferred later, the DoppelGANger metadata/batch ideas transfer; but the conditional-GAN with these three mechanisms is the cheapest high-fidelity first build and has been validated on consumer GPUs.

### 8.3 Engineering carry-overs from the Chinese-lab stack

- FP8/bfloat16 mixed precision with fp32 master weights + optimizer states (V3 §3.3) — `torch.autocast(bfloat16)` + `torch.compile` is the free version for both the MLP actor and the GAN.
- Two-stage RL (offline imitation/preference then online GRPO) is the Qwen2.5/R1 pattern; for the arena that maps to: SFT-like distillation from the rule playbook first, then GRPO in the arena (R1 §2.4's "distill, then optionally RL" ordering).

---

## Sources

Primary sources (arXiv abs pages / ar5iv HTML / official proceedings / authors' official code), one line each:

- **DeepSeekMath: Pushing the Limits of Mathematical Reasoning in Open Language Models** — arXiv **2402.03300** — GRPO objective Eq. 3, unbiased KL Eq. 4, outcome/process advantage §4.1.2–4.1.3, iterative RL Alg. 1, hyper-parameters §4.1.4, single-update gradient Appendix A.1.6 Eq. 21.
- **DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning** — arXiv **2501.12948** — GRPO Eqs. 1–3, rule-based reward §2.2.2, multi-stage recipe §2.3, distillation §2.4/§4.1.
- **DeepSeek-V3 Technical Report** — arXiv **2412.19437** — MTP Eqs. 21–25, fine-grained MoE + shared expert Eqs. 12–17, FP8 §3.3, GRPO/rule-based RM §5.2.
- **Qwen2.5 Technical Report** — arXiv **2412.15115** — 18T-token pre-training §3.1, small-model results §5.1, post-training SFT + offline DPO + online GRPO (G=8, batch 2048) §4.
- **Using GANs for Sharing Networked Time Series Data: Challenges, Initial Promise, and Open Questions** (DoppelGANger) — arXiv **1909.13403** (IMC 2020) — batch generation §4.1, auto-normalization §4.2, auxiliary discriminator §4.3, fidelity results §5.2. *Note: supplied ID 2103.06495 was ABINet.*
- **Time-series Generative Adversarial Networks (TimeGAN)** — NeurIPS 2019 proceedings (no arXiv), paper hash `c9efe5f26cd17ba6216bbe2a7d26d490` — embedder/supervisor/recovery/adversarial + losses; equations as implemented in official repo `github.com/jsyoon0823/TimeGAN`. *Note: supplied ID 1909.11659 was a physics paper.*
- **Quant GANs: Deep Generation of Financial Time Series** — arXiv **1907.06673** (Quantitative Finance 2020) — TCNs §3.2, SVNN/log-return neural process §5.1, Lambert W §5.3, stylized facts §2. *Note: supplied ID 1907.06643 was an astronomy paper.*

## Access notes (verify manually)

- Qwen2.5 (2412.15115): ar5iv and arXiv HTML both broken; full text read via the HF Papers mirror of the report.
- TimeGAN: no arXiv; ar5iv broken; abstract from NeurIPS proceedings page, equations from the authors' official code repo (primary but not the typeset paper).
- DeepSeekMath/R1/V3: ar5iv full text fetched successfully; equations cross-checked between the three papers (identical GRPO forms).
- Clip epsilon `ε`: not numerically published in any of the three DeepSeek papers; 0.2 is the inherited PPO/GRPO value.
