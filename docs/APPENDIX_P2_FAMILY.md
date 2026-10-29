# Programa 2 — famílias do beat-the-average nos finais existentes

36 programas executados, 0 falhas. Rótulos: `ladder` = classificador do paper 3 (≤ 50 átomos, massa ≥ 0,3 em {0..3}, ≥ 3 bandas log10 de distância ao topo); `sparse-single-scale` = ≤ 50 átomos em ≤ 2 bandas; `sparse-other`; `dense` = > 50 átomos (limiar 1e-4).

| programa | L | score | átomos | suporte | massa {0..3} | massa top-10 | massa meio | bandas | rótulo |
|---|---|---|---|---|---|---|---|---|---|
| runs/frontier/record/beatavg20k_claude_t60/best.py | 20000 | 0.3899 | 27 | 27 | 0.22 | 0.12 | 0.25 | 4 [0, 1, 2, 3] | sparse-other |
| runs/frontier/record/beatavg20k_claude/best.py | 20000 | 0.3897 | 42 | 43 | 0.24 | 0.09 | 0.24 | 4 [0, 1, 2, 3] | sparse-other |
| runs/frontier/FP/beatavg_D/best.py | 5000 | 0.3876 | 15 | 15 | 0.47 | 0.00 | 0.05 | 3 [1, 2, 3] | ladder |
| runs/frontier/record27/beatavg_E600/best.py | 5000 | 0.3876 | 16 | 16 | 0.22 | 0.00 | 0.32 | 3 [1, 2, 3] | sparse-other |
| runs/frontier/claude/beatavg_E300/best.py | 5000 | 0.3872 | 40 | 40 | 0.22 | 0.00 | 0.32 | 2 [2, 3] | sparse-single-scale |
| runs/frontier/FP/beatavg_A/best.py | 5000 | 0.3862 | 18 | 18 | 0.25 | 0.00 | 0.31 | 1 [3] | sparse-single-scale |
| runs/frontier/FP/beatavg_B/best.py | 5000 | 0.3839 | 13 | 13 | 0.25 | 0.00 | 0.31 | 2 [2, 3] | sparse-single-scale |
| runs/frontier/record/beatavg_E600/best.py | 5000 | 0.3816 | 15 | 16 | 0.50 | 0.23 | 0.00 | 4 [0, 1, 2, 3] | ladder |
| runs/frontier/kimi/beatavg_E300/best.py | 5000 | 0.3808 | 111 | 112 | 0.21 | 0.00 | 0.36 | 2 [2, 3] | dense |
| runs/frontier/F/beatavg_BD/best.py | 5000 | 0.3806 | 18 | 18 | 0.46 | 0.17 | 0.04 | 4 [0, 1, 2, 3] | ladder |
| runs/frontier/F/beatavg_E_s1/best.py | 5000 | 0.3759 | 32 | 32 | 0.32 | 0.27 | 0.13 | 4 [0, 1, 2, 3] | ladder |
| docs/hint/seed_family_oracle.py | 5000 | 0.3742 | 13 | 13 | 0.45 | 0.14 | 0.05 | 4 [0, 1, 2, 3] | ladder |
| runs/frontier/F/beatavg_BD_s1/best.py | 5000 | 0.3660 | 14 | 14 | 0.53 | 0.39 | 0.00 | 4 [0, 1, 2, 3] | ladder |
| runs/frontier/F/beatavg_BC_s1/best.py | 5000 | 0.3619 | 7 | 7 | 0.50 | 0.00 | 0.50 | 0 [] | sparse-single-scale |
| runs/frontier/record27/beatavg_E_smoke/best.py | 5000 | 0.3588 | 5 | 7 | 0.00 | 0.00 | 0.50 | 2 [2, 3] | sparse-single-scale |
| runs/frontier/record/beatavg20k_E600/best.py | 20000 | 0.3561 | 19 | 19 | 0.31 | 0.31 | 0.22 | 4 [0, 1, 2, 3] | ladder |
| runs/frontier/F/beatavg_D/best.py | 5000 | 0.3547 | 14 | 14 | 0.48 | 0.50 | 0.00 | 3 [0, 1, 3] | ladder |
| runs/frontier/L/beatavg_baseD/best.py | 5000 | 0.3520 | 20 | 20 | 0.52 | 0.00 | 0.48 | 0 [] | sparse-single-scale |
| runs/frontier/record/beatavg_D600/best.py | 5000 | 0.3514 | 16 | 16 | 0.52 | 0.00 | 0.48 | 0 [] | sparse-single-scale |
| runs/frontier/F/beatavg_BC/best.py | 5000 | 0.3513 | 120 | 120 | 0.10 | 0.05 | 0.40 | 3 [0, 1, 2] | dense |
| runs/frontier/F/beatavg_E/best.py | 5000 | 0.3500 | 12 | 12 | 0.52 | 0.48 | 0.00 | 1 [0] | sparse-single-scale |
| runs/frontier/F/beatavg_C_s1/best.py | 5000 | 0.3477 | 36 | 36 | 0.46 | 0.24 | 0.09 | 3 [0, 2, 3] | ladder |
| runs/frontier/F/beatavg_D_s1/best.py | 5000 | 0.3448 | 5 | 5 | 0.50 | 0.20 | 0.00 | 2 [0, 3] | sparse-single-scale |
| runs/frontier/F/beatavg_CD_s1/best.py | 5000 | 0.3428 | 7 | 7 | 0.46 | 0.47 | 0.00 | 1 [0] | sparse-single-scale |
| runs/frontier/F/beatavg_B/best.py | 5000 | 0.3422 | 8 | 8 | 0.52 | 0.48 | 0.00 | 1 [0] | sparse-single-scale |
| runs/frontier/F/beatavg_CD/best.py | 5000 | 0.3392 | 5000 | 5000 | 0.27 | 0.00 | 0.37 | 4 [0, 1, 2, 3] | dense |
| runs/frontier/F/beatavg_C/best.py | 5000 | 0.3287 | 7 | 7 | 0.44 | 0.23 | 0.11 | 2 [0, 3] | sparse-single-scale |
| runs/frontier/L/beatavg_pool/best.py | 5000 | 0.3000 | 16 | 16 | 0.66 | 0.00 | 0.34 | 0 [] | sparse-single-scale |
| runs/frontier/F/beatavg_B_s1/best.py | 5000 | 0.2993 | 5 | 5 | 0.62 | 0.00 | 0.38 | 0 [] | sparse-single-scale |
| runs/frontier/L/beatavg_consD/best.py | 5000 | 0.2967 | 6 | 6 | 0.81 | 0.00 | 0.19 | 0 [] | sparse-single-scale |
| runs/frontier/F/beatavg_A/best.py | 5000 | 0.2963 | 3 | 3 | 0.67 | 0.33 | 0.00 | 1 [0] | sparse-single-scale |
| runs/frontier/L/beatavg_base/best.py | 5000 | 0.2954 | 5 | 5 | 0.88 | 0.00 | 0.12 | 0 [] | sparse-single-scale |
| runs/frontier/F/beatavg_A_s1/best.py | 5000 | 0.2925 | 20 | 20 | 0.75 | 0.00 | 0.25 | 0 [] | sparse-single-scale |
| runs/frontier/L/beatavg_cons/best.py | 5000 | 0.2917 | 14 | 15 | 0.79 | 0.00 | 0.21 | 0 [] | sparse-single-scale |
| runs/frontier/L/beatavg_rand/best.py | 5000 | 0.2908 | 10 | 10 | 0.82 | 0.00 | 0.18 | 0 [] | sparse-single-scale |
| docs/hint/seed_family_poor.py | 5000 | 0.2734 | 4 | 4 | 0.25 | 0.00 | 0.00 | 2 [2, 3] | sparse-single-scale |

Contagem: sparse-single-scale 21, ladder 9, dense 3, sparse-other 3

## Leitura (2026-09-03, noite): a parede do beat-the-average é a resolução, não uma ideia

Bellec–Fritz (arXiv:2412.15179, lido no PDF): a medida ν = p·δ₀ + (1−p)/N·Σᵢ δ_{1−2^{−i}}
(escada diádica + átomo em zero) dá P[estrita] → p(1−p)(2−p) = **0,3804** (Prop. 4.1);
o 0,400695 vem da Prop. 3.3, que **realoca a massa perdida nos empates**
X₁+X₂+X₃ = 2X₄ por meio da mistura auto-similar Y = X₁ + ηX₂ + η²X₃ + … (cópias da
escada em escalas geométricas, infinitas): valor p(2−p)/(1+p+p²+p³) = 0,400695. O
próprio artigo: "a finitely supported distribution cannot be optimal".

Numericamente (`scripts/bf_ladder_limit.py`, `scripts/bf_mixture_grid.py`, objetivo
exato para átomos esparsos e o verificador do harness com FFT):

| construção | valor |
|---|---|
| escada só (K = 1), contínua, N = 30, pesos otimizados | 0,3814 |
| escada só na grade L = 5000 / 20000 (N = 12 / 14) | 0,3754 / 0,3769 |
| mistura K = 2–3 na grade: L = 5k / 20k / 131k / 1M / 4M | 0,3850 / 0,3867 / 0,3878 / 0,3886 / 0,3888 |
| **finais do laço**: 30B/27B em L = 5000; Claude em L = 20000 | **0,3876; 0,3899** |

Os finais do laço têm exatamente a estrutura de Bellec–Fritz: escada diádica no topo
(razões ≈ 2), **cópia da escada em escala menor** perto de zero ({0, 4, 6, 7} = 8·(1−2^{−i}))
e átomos desdobrados (136/137, 282/284/288) que quebram empates — e superam as
minhas instanciações manuais na mesma grade. Ou seja: a "família do recorde" **já
está nas mãos do laço**; o que falta (0,011) é o limite do contínuo, que nenhuma
grade finita alcança e que cresce devagar com L (0,385 → 0,389 de 5 mil a 4 milhões
de pontos). Consequências: (1) o paper 3 leu a parede como "família de construção
(uma ideia)" — a leitura correta neste problema é **resolução/limite do contínuo**;
a nota entra na v2; (2) beat-the-average deixa de ser alvo do Programa 2 (não há
ideia a transferir) e passa a ser **fonte** de famílias auto-similares para a biblioteca.

## Sum-difference III: parede de ideia com folga dentro do teto

Família do recorde (Gerbicz 2505.16105; Zheng 2506.01896): U = {Σ xₖ(2B+1)ᵏ : x ∈ W(m,L,B)},
W = vetores com soma ≤ L e dígitos ≤ B — codificação **sem vai-um** (base > 2B), que
torna a soma e a diferença injetivas. A família dos nossos finais é "somas de ≤ 3
potências de 2" (= base 2, com vai-um). Dentro do teto do harness (|U| ≤ 4000): a
família do recorde dá **θ = 1,1236** (m = 8, L = 6, B = 4, |U| = 2931) > 1,1123 (nosso
melhor, 20 corridas), e o AlphaEvolve reportou **1,1479 com 2003 inteiros** — logo há
uma ideia melhor ainda cabendo no teto. Alvo do piloto do Programa 2: **sumdiff3**.
