# Residual-stream analysis (fam8b)

40 cells, layers [0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 35]. Window vectors are mean-centered per layer over all cells of this set before cosine geometry (anisotropy of mean-pooled states); premise similarity and injection deltas are raw.


## H1 — per-layer geometry (mean over cells; 95% bootstrap CI over cells)

| condition | n | radius L0 | radius L3 | radius L6 | radius L9 | radius L12 | radius L15 | radius L18 | radius L21 | radius L24 | radius L27 | radius L30 | radius L33 | radius L35 | commit layer (idx) | final entropy |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DREAM scaffold | 10 | 0.542 | 0.404 | 0.451 | 0.457 | 0.435 | 0.428 | 0.427 | 0.423 | 0.428 | 0.434 | 0.431 | 0.417 | 0.322 | 10.35 [10.23, 10.47] | 0.96 |
| bare + clock reseed | 10 | 0.461 | 0.345 | 0.371 | 0.367 | 0.340 | 0.354 | 0.372 | 0.391 | 0.388 | 0.353 | 0.334 | 0.310 | 0.225 | 9.45 [9.35, 9.55] | 0.35 |
| bare | 10 | 0.145 | 0.138 | 0.166 | 0.185 | 0.195 | 0.210 | 0.233 | 0.246 | 0.224 | 0.213 | 0.192 | 0.186 | 0.157 | 9.47 [9.21, 9.78] | 0.18 |
| bare + habituation | 10 | 0.333 | 0.284 | 0.321 | 0.343 | 0.329 | 0.343 | 0.361 | 0.375 | 0.347 | 0.337 | 0.315 | 0.307 | 0.232 | 9.92 [9.71, 10.14] | 0.49 |

## H2 — which layer's novelty predicts judged surprise? (187 judged windows)


**novelty vs everything before the window** — Spearman with judged surprise

| layer | ρ pooled | p | ρ within DREAM scaffold | ρ within bare + clock reseed | ρ within bare | ρ within bare + habituation |
|---|---|---|---|---|---|---|
| 0 | +0.58 | 2.3e-18 | +0.19 | -0.46 | +0.58 | +0.51 |
| 3 | +0.50 | 2.1e-13 | +0.19 | -0.31 | +0.42 | +0.36 |
| 6 | +0.49 | 6.6e-13 | +0.17 | -0.30 | +0.41 | +0.44 |
| 9 | +0.42 | 2.1e-09 | +0.17 | -0.23 | +0.32 | +0.26 |
| 12 | +0.37 | 1.4e-07 | +0.22 | -0.16 | +0.24 | +0.16 |
| 15 | +0.33 | 3.7e-06 | +0.22 | -0.15 | +0.19 | +0.07 |
| 18 | +0.30 | 2.9e-05 | +0.21 | -0.16 | +0.18 | -0.03 |
| 21 | +0.29 | 4.3e-05 | +0.19 | -0.15 | +0.21 | +0.00 |
| 24 | +0.36 | 3.9e-07 | +0.19 | -0.17 | +0.30 | +0.08 |
| 27 | +0.34 | 2.6e-06 | +0.18 | -0.11 | +0.30 | +0.07 |
| 30 | +0.39 | 4.7e-08 | +0.19 | -0.11 | +0.34 | +0.18 |
| 33 | +0.33 | 3.7e-06 | +0.18 | -0.08 | +0.28 | +0.09 |
| 35 | +0.11 | 1.5e-01 | +0.08 | -0.01 | +0.03 | -0.37 |

**local step vs the previous 160 tokens** — Spearman with judged surprise

| layer | ρ pooled | p | ρ within DREAM scaffold | ρ within bare + clock reseed | ρ within bare | ρ within bare + habituation |
|---|---|---|---|---|---|---|
| 0 | +0.62 | 5.9e-21 | +0.06 | -0.26 | +0.67 | +0.44 |
| 3 | +0.67 | 7.1e-26 | +0.24 | -0.08 | +0.67 | +0.65 |
| 6 | +0.64 | 2.6e-23 | +0.19 | +0.02 | +0.65 | +0.65 |
| 9 | +0.62 | 3.0e-21 | +0.19 | +0.03 | +0.66 | +0.62 |
| 12 | +0.59 | 3.3e-19 | +0.19 | +0.05 | +0.65 | +0.61 |
| 15 | +0.59 | 8.3e-19 | +0.19 | +0.06 | +0.64 | +0.63 |
| 18 | +0.57 | 1.9e-17 | +0.22 | +0.06 | +0.59 | +0.59 |
| 21 | +0.57 | 2.1e-17 | +0.20 | -0.02 | +0.59 | +0.61 |
| 24 | +0.60 | 2.0e-19 | +0.20 | -0.12 | +0.63 | +0.62 |
| 27 | +0.58 | 1.6e-18 | +0.19 | -0.10 | +0.65 | +0.61 |
| 30 | +0.59 | 9.0e-19 | +0.17 | -0.12 | +0.66 | +0.63 |
| 33 | +0.57 | 1.5e-17 | +0.17 | -0.09 | +0.65 | +0.63 |
| 35 | +0.54 | 1.8e-15 | +0.13 | +0.24 | +0.63 | +0.55 |

Commitment layer (mean first-agreeing captured layer) vs surprise: ρ=+0.37 (p=2.3e-07); final entropy vs surprise: ρ=+0.47 (p=1.0e-11).
- within DREAM scaffold: commit ρ=+0.11 (p=3.6e-01), final entropy ρ=+0.17 (p=1.4e-01), mean commit 10.17, mean surprise 2.68
- within bare + clock reseed: commit ρ=+0.09 (p=6.2e-01), final entropy ρ=+0.27 (p=1.4e-01), mean commit 9.31, mean surprise 3.12
- within bare: commit ρ=+0.56 (p=6.8e-06), final entropy ρ=+0.63 (p=1.5e-07), mean commit 9.37, mean surprise 0.39
- within bare + habituation: commit ρ=+0.63 (p=6.6e-04), final entropy ρ=+0.70 (p=9.4e-05), mean commit 9.88, mean surprise 1.00

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
