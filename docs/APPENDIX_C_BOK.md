# Appendix — Battery C equal-budget analyses (best-of-k, pass@k, quantiles)

Held-out variants, cycle-5 arms, test excess of valid candidates. best-of-k: mean over 2000 subsamples of k candidates per variant (variants with fewer than k valid candidates are skipped for that k). pass@k: probability that a subsample of k contains a candidate beating min(BF, FF) on test.


## k = 10

| arm | variants used | best-of-k (mean excess of subsample best) | pass@k vs classics |
|---|---|---|---|
| base | 1/8 | 0.0449 | 0.0000 |
| attract | 8/8 | 0.0311 | 0.0000 |
| random | 8/8 | 0.0381 | 0.0000 |

## k = 20

| arm | variants used | best-of-k (mean excess of subsample best) | pass@k vs classics |
|---|---|---|---|
| attract | 8/8 | 0.0311 | 0.0000 |
| random | 8/8 | 0.0338 | 0.0000 |

## k = 40

| arm | variants used | best-of-k (mean excess of subsample best) | pass@k vs classics |
|---|---|---|---|
| random | 3/8 | 0.0289 | 0.0000 |

## Quantiles of valid-candidate test excess (pooled over held-out variants)

| arm | n | p10 | p50 | p90 | p99 |
|---|---|---|---|---|---|
| base | 47 | 0.0285 | 0.0483 | 0.1075 | 0.1169 |
| attract | 226 | 0.0257 | 0.0283 | 0.0676 | 0.1075 |
| random | 287 | 0.0283 | 0.0754 | 0.1063 | 0.1169 |
