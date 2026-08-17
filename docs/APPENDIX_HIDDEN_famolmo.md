# Residual-stream analysis (famolmo)

40 cells, layers [0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36, 39]. Window vectors are mean-centered per layer over all cells of this set before cosine geometry (anisotropy of mean-pooled states); premise similarity and injection deltas are raw.


## H1 — per-layer geometry (mean over cells; 95% bootstrap CI over cells)

| condition | n | radius L0 | radius L3 | radius L6 | radius L9 | radius L12 | radius L15 | radius L18 | radius L21 | radius L24 | radius L27 | radius L30 | radius L33 | radius L36 | radius L39 | commit layer (idx) | final entropy |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DREAM scaffold | 10 | 0.611 | 0.561 | 0.530 | 0.510 | 0.506 | 0.502 | 0.490 | 0.483 | 0.473 | 0.468 | 0.466 | 0.466 | 0.462 | 0.446 | 11.04 [10.91, 11.19] | 1.22 |
| bare + clock reseed | 10 | 0.478 | 0.460 | 0.409 | 0.431 | 0.451 | 0.445 | 0.420 | 0.415 | 0.412 | 0.396 | 0.389 | 0.379 | 0.354 | 0.302 | 9.76 [9.66, 9.88] | 0.65 |
| bare | 10 | 0.361 | 0.363 | 0.369 | 0.388 | 0.397 | 0.396 | 0.381 | 0.379 | 0.373 | 0.363 | 0.363 | 0.364 | 0.363 | 0.352 | 10.43 [10.10, 10.75] | 0.61 |
| bare + habituation | 10 | 0.509 | 0.471 | 0.447 | 0.450 | 0.457 | 0.460 | 0.430 | 0.427 | 0.414 | 0.404 | 0.403 | 0.403 | 0.401 | 0.380 | 10.80 [10.64, 10.96] | 0.97 |

## H2 — which layer's novelty predicts judged surprise? (340 judged windows)


**novelty vs everything before the window** — Spearman with judged surprise

| layer | ρ pooled | p | ρ within DREAM scaffold | ρ within bare + clock reseed | ρ within bare | ρ within bare + habituation |
|---|---|---|---|---|---|---|
| 0 | +0.28 | 1.0e-07 | -0.06 | +0.25 | +0.36 | +0.20 |
| 3 | +0.30 | 2.0e-08 | -0.02 | +0.25 | +0.34 | +0.25 |
| 6 | +0.26 | 9.0e-07 | -0.05 | +0.30 | +0.22 | +0.24 |
| 9 | +0.16 | 2.3e-03 | -0.05 | +0.29 | -0.02 | +0.14 |
| 12 | +0.15 | 5.4e-03 | -0.06 | +0.22 | -0.04 | +0.09 |
| 15 | +0.15 | 4.3e-03 | -0.06 | +0.26 | -0.04 | +0.07 |
| 18 | +0.16 | 3.1e-03 | -0.07 | +0.21 | +0.03 | +0.09 |
| 21 | +0.14 | 8.0e-03 | -0.08 | +0.24 | +0.01 | +0.06 |
| 24 | +0.13 | 1.4e-02 | -0.08 | +0.23 | +0.02 | +0.04 |
| 27 | +0.15 | 7.4e-03 | -0.08 | +0.24 | +0.06 | +0.04 |
| 30 | +0.14 | 1.1e-02 | -0.08 | +0.24 | +0.04 | +0.04 |
| 33 | +0.13 | 1.4e-02 | -0.08 | +0.25 | +0.04 | +0.02 |
| 36 | +0.11 | 3.8e-02 | -0.10 | +0.25 | +0.02 | -0.00 |
| 39 | +0.10 | 6.7e-02 | -0.08 | +0.21 | +0.03 | +0.04 |

**local step vs the previous 160 tokens** — Spearman with judged surprise

| layer | ρ pooled | p | ρ within DREAM scaffold | ρ within bare + clock reseed | ρ within bare | ρ within bare + habituation |
|---|---|---|---|---|---|---|
| 0 | +0.41 | 2.6e-15 | +0.01 | +0.14 | +0.70 | +0.28 |
| 3 | +0.46 | 3.8e-19 | +0.06 | +0.27 | +0.72 | +0.38 |
| 6 | +0.47 | 4.4e-20 | +0.01 | +0.54 | +0.74 | +0.42 |
| 9 | +0.43 | 7.3e-17 | -0.00 | +0.52 | +0.70 | +0.29 |
| 12 | +0.43 | 4.3e-17 | -0.02 | +0.57 | +0.67 | +0.29 |
| 15 | +0.42 | 3.0e-16 | -0.05 | +0.61 | +0.66 | +0.25 |
| 18 | +0.42 | 3.0e-16 | -0.05 | +0.65 | +0.66 | +0.26 |
| 21 | +0.41 | 1.8e-15 | -0.05 | +0.64 | +0.65 | +0.24 |
| 24 | +0.40 | 9.9e-15 | -0.06 | +0.63 | +0.66 | +0.22 |
| 27 | +0.40 | 1.2e-14 | -0.06 | +0.64 | +0.65 | +0.22 |
| 30 | +0.39 | 5.7e-14 | -0.06 | +0.63 | +0.65 | +0.23 |
| 33 | +0.39 | 4.8e-14 | -0.06 | +0.67 | +0.65 | +0.23 |
| 36 | +0.38 | 2.1e-13 | -0.07 | +0.67 | +0.65 | +0.22 |
| 39 | +0.40 | 1.7e-14 | -0.03 | +0.65 | +0.65 | +0.32 |

Commitment layer (mean first-agreeing captured layer) vs surprise: ρ=+0.31 (p=6.3e-09); final entropy vs surprise: ρ=+0.52 (p=3.4e-25).
- within DREAM scaffold: commit ρ=-0.00 (p=9.6e-01), final entropy ρ=+0.11 (p=2.3e-01), mean commit 11.03, mean surprise 2.95
- within bare + clock reseed: commit ρ=+0.26 (p=4.6e-02), final entropy ρ=+0.29 (p=2.7e-02), mean commit 10.18, mean surprise 3.11
- within bare: commit ρ=+0.64 (p=1.3e-12), final entropy ρ=+0.82 (p=6.5e-25), mean commit 10.28, mean surprise 1.13
- within bare + habituation: commit ρ=+0.34 (p=1.6e-02), final entropy ρ=+0.53 (p=1.0e-04), mean commit 10.75, mean surprise 1.90

## H1b — similarity of the stream to the premise state, per layer (mean over windows, then cells)

| condition | L0 | L3 | L6 | L9 | L12 | L15 | L18 | L21 | L24 | L27 | L30 | L33 | L36 | L39 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DREAM scaffold | 0.536 | 0.445 | 0.357 | 0.401 | 0.427 | 0.390 | 0.353 | 0.363 | 0.336 | 0.331 | 0.326 | 0.329 | 0.398 | 0.732 |
| bare + clock reseed | 0.556 | 0.446 | 0.333 | 0.367 | 0.391 | 0.360 | 0.363 | 0.383 | 0.373 | 0.378 | 0.379 | 0.380 | 0.493 | 0.829 |
| bare | 0.479 | 0.377 | 0.311 | 0.355 | 0.378 | 0.345 | 0.326 | 0.338 | 0.313 | 0.312 | 0.312 | 0.314 | 0.380 | 0.711 |
| bare + habituation | 0.492 | 0.405 | 0.325 | 0.372 | 0.397 | 0.359 | 0.325 | 0.334 | 0.305 | 0.300 | 0.297 | 0.299 | 0.371 | 0.720 |

## H3 — how deep does an interruption reach? (before/after cosine distance minus random-position control; and return to the premise)

| condition | n cells | injections | Δ L0 | Δ L3 | Δ L6 | Δ L9 | Δ L12 | Δ L15 | Δ L18 | Δ L21 | Δ L24 | Δ L27 | Δ L30 | Δ L33 | Δ L36 | Δ L39 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DREAM scaffold | 8 | 16 | +0.196 | +0.242 | +0.297 | +0.295 | +0.291 | +0.312 | +0.340 | +0.348 | +0.379 | +0.385 | +0.389 | +0.390 | +0.354 | +0.205 |
| bare + clock reseed | 10 | 290 | +0.018 | +0.032 | +0.047 | +0.044 | +0.047 | +0.057 | +0.055 | +0.052 | +0.053 | +0.052 | +0.049 | +0.047 | +0.040 | +0.012 |

**Return to the premise** (Δ similarity to the premise state, after − before, minus control):

| condition | L0 | L3 | L6 | L9 | L12 | L15 | L18 | L21 | L24 | L27 | L30 | L33 | L36 | L39 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DREAM scaffold | +0.139 | +0.129 | +0.125 | +0.117 | +0.122 | +0.142 | +0.153 | +0.156 | +0.175 | +0.175 | +0.171 | +0.174 | +0.195 | +0.193 |
| bare + clock reseed | +0.007 | +0.003 | +0.001 | +0.006 | +0.004 | +0.002 | +0.001 | +0.001 | +0.003 | +0.003 | +0.003 | +0.004 | +0.009 | +0.014 |
