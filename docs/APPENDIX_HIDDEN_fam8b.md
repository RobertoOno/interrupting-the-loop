# Residual-stream analysis (fam8b)

40 cells, layers [0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 35]. Window vectors are mean-centered per layer over all cells of this set before cosine geometry (anisotropy of mean-pooled states); premise similarity and injection deltas are raw.


## H1 — per-layer geometry (mean over cells; 95% bootstrap CI over cells)

| condition | n | radius L0 | radius L3 | radius L6 | radius L9 | radius L12 | radius L15 | radius L18 | radius L21 | radius L24 | radius L27 | radius L30 | radius L33 | radius L35 | commit layer (idx) | final entropy |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DREAM scaffold | 10 | 0.542 | 0.404 | 0.451 | 0.457 | 0.435 | 0.428 | 0.427 | 0.423 | 0.428 | 0.434 | 0.431 | 0.417 | 0.322 | 10.35 [10.23, 10.47] | 0.96 |
| bare + clock reseed | 10 | 0.461 | 0.345 | 0.371 | 0.367 | 0.340 | 0.354 | 0.372 | 0.391 | 0.388 | 0.353 | 0.334 | 0.310 | 0.225 | 9.45 [9.35, 9.55] | 0.35 |
| bare | 10 | 0.145 | 0.138 | 0.166 | 0.185 | 0.195 | 0.210 | 0.233 | 0.246 | 0.224 | 0.213 | 0.192 | 0.186 | 0.157 | 9.47 [9.21, 9.78] | 0.18 |
| bare + habituation | 10 | 0.333 | 0.284 | 0.321 | 0.343 | 0.329 | 0.343 | 0.361 | 0.375 | 0.347 | 0.337 | 0.315 | 0.307 | 0.232 | 9.92 [9.71, 10.14] | 0.49 |

## H2 — which layer's novelty predicts judged surprise? (342 judged windows)


**novelty vs everything before the window** — Spearman with judged surprise

| layer | ρ pooled | p | ρ within DREAM scaffold | ρ within bare + clock reseed | ρ within bare | ρ within bare + habituation |
|---|---|---|---|---|---|---|
| 0 | +0.57 | 1.5e-30 | +0.21 | -0.17 | +0.55 | +0.43 |
| 3 | +0.48 | 1.8e-21 | +0.19 | +0.01 | +0.43 | +0.18 |
| 6 | +0.48 | 7.1e-21 | +0.19 | +0.01 | +0.45 | +0.19 |
| 9 | +0.42 | 4.1e-16 | +0.17 | +0.13 | +0.39 | +0.07 |
| 12 | +0.38 | 5.7e-13 | +0.19 | +0.09 | +0.31 | -0.01 |
| 15 | +0.34 | 1.0e-10 | +0.19 | +0.07 | +0.26 | -0.07 |
| 18 | +0.32 | 2.2e-09 | +0.19 | +0.10 | +0.25 | -0.12 |
| 21 | +0.31 | 5.3e-09 | +0.18 | +0.09 | +0.28 | -0.14 |
| 24 | +0.36 | 4.0e-12 | +0.19 | +0.10 | +0.35 | -0.09 |
| 27 | +0.35 | 2.6e-11 | +0.17 | +0.14 | +0.36 | -0.06 |
| 30 | +0.38 | 4.2e-13 | +0.17 | +0.15 | +0.40 | -0.03 |
| 33 | +0.34 | 1.5e-10 | +0.15 | +0.16 | +0.34 | -0.09 |
| 35 | +0.14 | 8.7e-03 | +0.05 | +0.24 | -0.05 | -0.35 |

**local step vs the previous 160 tokens** — Spearman with judged surprise

| layer | ρ pooled | p | ρ within DREAM scaffold | ρ within bare + clock reseed | ρ within bare | ρ within bare + habituation |
|---|---|---|---|---|---|---|
| 0 | +0.65 | 2.5e-42 | +0.16 | -0.02 | +0.68 | +0.59 |
| 3 | +0.67 | 5.4e-46 | +0.27 | +0.11 | +0.68 | +0.61 |
| 6 | +0.65 | 3.4e-43 | +0.25 | +0.10 | +0.67 | +0.61 |
| 9 | +0.64 | 3.5e-40 | +0.21 | +0.20 | +0.67 | +0.59 |
| 12 | +0.61 | 1.5e-36 | +0.19 | +0.19 | +0.66 | +0.58 |
| 15 | +0.60 | 2.4e-35 | +0.19 | +0.20 | +0.65 | +0.58 |
| 18 | +0.58 | 4.6e-32 | +0.20 | +0.24 | +0.61 | +0.55 |
| 21 | +0.57 | 4.1e-31 | +0.19 | +0.18 | +0.62 | +0.54 |
| 24 | +0.60 | 3.8e-35 | +0.19 | +0.13 | +0.64 | +0.54 |
| 27 | +0.60 | 1.9e-34 | +0.19 | +0.18 | +0.65 | +0.56 |
| 30 | +0.60 | 3.0e-35 | +0.17 | +0.15 | +0.66 | +0.60 |
| 33 | +0.59 | 9.8e-34 | +0.17 | +0.16 | +0.65 | +0.60 |
| 35 | +0.57 | 8.4e-31 | +0.12 | +0.36 | +0.61 | +0.56 |

Commitment layer (mean first-agreeing captured layer) vs surprise: ρ=+0.42 (p=8.4e-16); final entropy vs surprise: ρ=+0.52 (p=9.3e-25).
- within DREAM scaffold: commit ρ=+0.21 (p=1.6e-02), final entropy ρ=+0.30 (p=4.6e-04), mean commit 10.21, mean surprise 2.65
- within bare + clock reseed: commit ρ=-0.17 (p=2.0e-01), final entropy ρ=-0.11 (p=3.9e-01), mean commit 9.31, mean surprise 2.73
- within bare: commit ρ=+0.61 (p=1.3e-11), final entropy ρ=+0.65 (p=4.0e-13), mean commit 9.37, mean surprise 0.38
- within bare + habituation: commit ρ=+0.63 (p=8.4e-07), final entropy ρ=+0.65 (p=3.2e-07), mean commit 9.80, mean surprise 1.04

## H1b — similarity of the stream to the premise state, per layer (mean over windows, then cells)

| condition | L0 | L3 | L6 | L9 | L12 | L15 | L18 | L21 | L24 | L27 | L30 | L33 | L35 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DREAM scaffold | 0.907 | 0.850 | 0.856 | 0.680 | 0.702 | 0.664 | 0.653 | 0.618 | 0.698 | 0.743 | 0.821 | 0.890 | 0.856 |
| bare + clock reseed | 0.914 | 0.850 | 0.857 | 0.675 | 0.690 | 0.641 | 0.620 | 0.570 | 0.683 | 0.738 | 0.830 | 0.889 | 0.859 |
| bare | 0.910 | 0.838 | 0.843 | 0.656 | 0.672 | 0.625 | 0.603 | 0.555 | 0.661 | 0.721 | 0.816 | 0.880 | 0.749 |
| bare + habituation | 0.901 | 0.835 | 0.842 | 0.652 | 0.672 | 0.628 | 0.608 | 0.562 | 0.655 | 0.714 | 0.806 | 0.878 | 0.793 |

## H3 — how deep does an interruption reach? (before/after cosine distance minus random-position control; and return to the premise)

| condition | n cells | injections | Δ L0 | Δ L3 | Δ L6 | Δ L9 | Δ L12 | Δ L15 | Δ L18 | Δ L21 | Δ L24 | Δ L27 | Δ L30 | Δ L33 | Δ L35 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DREAM scaffold | 10 | 26 | +0.027 | +0.037 | +0.030 | +0.074 | +0.081 | +0.088 | +0.087 | +0.099 | +0.075 | +0.061 | +0.043 | +0.033 | +0.047 |
| bare + clock reseed | 10 | 290 | +0.010 | +0.012 | +0.009 | +0.016 | +0.017 | +0.020 | +0.025 | +0.030 | +0.024 | +0.017 | +0.011 | +0.007 | +0.005 |

**Return to the premise** (Δ similarity to the premise state, after − before, minus control):

| condition | L0 | L3 | L6 | L9 | L12 | L15 | L18 | L21 | L24 | L27 | L30 | L33 | L35 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DREAM scaffold | +0.014 | +0.030 | +0.024 | +0.052 | +0.055 | +0.066 | +0.080 | +0.104 | +0.074 | +0.053 | +0.034 | +0.025 | +0.064 |
| bare + clock reseed | +0.009 | +0.009 | +0.006 | +0.011 | +0.010 | +0.013 | +0.010 | +0.013 | +0.010 | +0.008 | +0.008 | +0.006 | +0.013 |
