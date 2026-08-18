# Residual-stream analysis (scaffold)

40 cells, layers [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 47]. Window vectors are mean-centered per layer over all cells of this set before cosine geometry (anisotropy of mean-pooled states); premise similarity and injection deltas are raw.


## H1 — per-layer geometry (mean over cells; 95% bootstrap CI over cells)

| condition | n | radius L0 | radius L4 | radius L8 | radius L12 | radius L16 | radius L20 | radius L24 | radius L28 | radius L32 | radius L36 | radius L40 | radius L44 | radius L47 | commit layer (idx) | final entropy |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DREAM scaffold | 10 | 0.526 | 0.449 | 0.411 | 0.406 | 0.409 | 0.392 | 0.388 | 0.364 | 0.350 | 0.350 | 0.376 | 0.369 | 0.333 | 10.88 [10.82, 10.96] | 1.08 |
| salience only | 10 | 0.433 | 0.389 | 0.378 | 0.381 | 0.381 | 0.370 | 0.375 | 0.358 | 0.350 | 0.355 | 0.362 | 0.347 | 0.335 | 10.94 [10.83, 11.05] | 0.88 |
| bare + clock reseed | 10 | 0.418 | 0.359 | 0.377 | 0.389 | 0.382 | 0.369 | 0.383 | 0.372 | 0.369 | 0.381 | 0.369 | 0.351 | 0.339 | 10.96 [10.92, 11.00] | 0.42 |
| bare | 10 | 0.131 | 0.163 | 0.201 | 0.214 | 0.221 | 0.225 | 0.237 | 0.244 | 0.246 | 0.252 | 0.235 | 0.222 | 0.242 | 11.12 [11.04, 11.25] | 0.34 |

## H2 — which layer's novelty predicts judged surprise? (179 judged windows)


**novelty vs everything before the window** — Spearman with judged surprise

| layer | ρ pooled | p | ρ within DREAM scaffold | ρ within salience only | ρ within bare + clock reseed | ρ within bare |
|---|---|---|---|---|---|---|
| 0 | +0.47 | 2.5e-11 | -0.21 | -0.03 | -0.08 | +0.47 |
| 4 | +0.35 | 1.7e-06 | -0.23 | -0.18 | -0.02 | +0.35 |
| 8 | +0.21 | 5.5e-03 | -0.31 | -0.26 | -0.08 | +0.27 |
| 12 | +0.20 | 7.8e-03 | -0.31 | -0.23 | -0.08 | +0.24 |
| 16 | +0.19 | 1.1e-02 | -0.29 | -0.25 | -0.03 | +0.26 |
| 20 | +0.16 | 3.8e-02 | -0.31 | -0.27 | -0.04 | +0.24 |
| 24 | +0.15 | 4.9e-02 | -0.29 | -0.27 | -0.04 | +0.23 |
| 28 | +0.11 | 1.4e-01 | -0.32 | -0.31 | +0.00 | +0.22 |
| 32 | +0.10 | 1.9e-01 | -0.32 | -0.30 | +0.00 | +0.22 |
| 36 | +0.09 | 2.5e-01 | -0.33 | -0.32 | -0.02 | +0.22 |
| 40 | +0.11 | 1.5e-01 | -0.33 | -0.37 | +0.02 | +0.22 |
| 44 | +0.10 | 1.6e-01 | -0.31 | -0.38 | +0.02 | +0.23 |
| 47 | -0.04 | 5.9e-01 | -0.35 | -0.53 | -0.01 | +0.17 |

**local step vs the previous 160 tokens** — Spearman with judged surprise

| layer | ρ pooled | p | ρ within DREAM scaffold | ρ within salience only | ρ within bare + clock reseed | ρ within bare |
|---|---|---|---|---|---|---|
| 0 | +0.62 | 1.7e-20 | +0.23 | +0.46 | -0.25 | +0.62 |
| 4 | +0.59 | 7.4e-18 | +0.14 | +0.25 | -0.04 | +0.61 |
| 8 | +0.55 | 1.6e-15 | +0.07 | +0.14 | +0.02 | +0.61 |
| 12 | +0.55 | 2.1e-15 | +0.05 | +0.16 | +0.03 | +0.61 |
| 16 | +0.54 | 8.9e-15 | +0.05 | +0.13 | +0.03 | +0.61 |
| 20 | +0.51 | 2.3e-13 | +0.01 | +0.03 | +0.07 | +0.60 |
| 24 | +0.51 | 1.9e-13 | +0.01 | -0.01 | +0.09 | +0.60 |
| 28 | +0.47 | 2.3e-11 | -0.05 | -0.17 | +0.13 | +0.59 |
| 32 | +0.47 | 4.6e-11 | -0.07 | -0.21 | +0.10 | +0.60 |
| 36 | +0.46 | 9.0e-11 | -0.07 | -0.21 | +0.09 | +0.59 |
| 40 | +0.47 | 2.8e-11 | -0.06 | -0.22 | +0.11 | +0.60 |
| 44 | +0.48 | 1.0e-11 | -0.03 | -0.17 | +0.08 | +0.60 |
| 47 | +0.41 | 8.1e-09 | -0.14 | -0.34 | +0.16 | +0.59 |

**Cluster-robust intervals** (bootstrap over cells, 2,000 resamples) for the pooled Spearman with surprise:

- novelty vs the past, layer 0: rho = +0.47, cell-bootstrap 95% CI [+0.22, +0.67]
- novelty vs the past, layer 24: rho = +0.15, cell-bootstrap 95% CI [-0.06, +0.34]
- novelty vs the past, layer 47: rho = -0.04, cell-bootstrap 95% CI [-0.26, +0.17]
- local step, layer 0: rho = +0.62, cell-bootstrap 95% CI [+0.41, +0.77]
- local step, layer 24: rho = +0.51, cell-bootstrap 95% CI [+0.28, +0.70]
- local step, layer 47: rho = +0.41, cell-bootstrap 95% CI [+0.15, +0.62]

Commitment layer (mean first-agreeing captured layer) vs surprise: ρ=-0.40 (p=3.8e-08); final entropy vs surprise: ρ=+0.51 (p=2.5e-13).
- within DREAM scaffold: commit ρ=-0.13 (p=4.1e-01), final entropy ρ=+0.24 (p=1.2e-01), mean commit 10.98, mean surprise 3.18
- within salience only: commit ρ=-0.24 (p=1.6e-01), final entropy ρ=+0.47 (p=4.4e-03), mean commit 10.97, mean surprise 2.60
- within bare + clock reseed: commit ρ=-0.16 (p=2.5e-01), final entropy ρ=+0.19 (p=1.8e-01), mean commit 10.92, mean surprise 2.68
- within bare: commit ρ=-0.54 (p=5.1e-05), final entropy ρ=+0.50 (p=2.2e-04), mean commit 11.12, mean surprise 0.28

## H1b — similarity of the stream to the premise state, per layer (mean over windows, then cells)

| condition | L0 | L4 | L8 | L12 | L16 | L20 | L24 | L28 | L32 | L36 | L40 | L44 | L47 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DREAM scaffold | 0.923 | 0.750 | 0.685 | 0.640 | 0.528 | 0.584 | 0.608 | 0.614 | 0.657 | 0.701 | 0.655 | 0.768 | 0.847 |
| salience only | 0.919 | 0.732 | 0.663 | 0.614 | 0.505 | 0.559 | 0.580 | 0.583 | 0.625 | 0.662 | 0.618 | 0.737 | 0.786 |
| bare + clock reseed | 0.935 | 0.767 | 0.671 | 0.616 | 0.503 | 0.550 | 0.563 | 0.546 | 0.581 | 0.601 | 0.574 | 0.708 | 0.667 |
| bare | 0.896 | 0.679 | 0.600 | 0.544 | 0.442 | 0.489 | 0.499 | 0.498 | 0.527 | 0.538 | 0.502 | 0.630 | 0.549 |

## H3 — how deep does an interruption reach? (before/after cosine distance minus random-position control; and return to the premise)

| condition | n cells | injections | Δ L0 | Δ L4 | Δ L8 | Δ L12 | Δ L16 | Δ L20 | Δ L24 | Δ L28 | Δ L32 | Δ L36 | Δ L40 | Δ L44 | Δ L47 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DREAM scaffold | 7 | 13 | +0.016 | +0.090 | +0.118 | +0.137 | +0.155 | +0.155 | +0.163 | +0.154 | +0.147 | +0.172 | +0.213 | +0.154 | +0.206 |
| bare + clock reseed | 10 | 290 | +0.003 | +0.012 | +0.011 | +0.013 | +0.014 | +0.013 | +0.018 | +0.019 | +0.017 | +0.022 | +0.027 | +0.017 | +0.010 |

**Return to the premise** (Δ similarity to the premise state, after − before, minus control):

| condition | L0 | L4 | L8 | L12 | L16 | L20 | L24 | L28 | L32 | L36 | L40 | L44 | L47 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DREAM scaffold | +0.023 | +0.094 | +0.113 | +0.132 | +0.151 | +0.143 | +0.159 | +0.158 | +0.158 | +0.175 | +0.197 | +0.133 | +0.183 |
| bare + clock reseed | +0.000 | +0.002 | -0.000 | -0.000 | +0.005 | +0.003 | +0.002 | -0.006 | -0.005 | -0.009 | -0.003 | -0.001 | -0.012 |
