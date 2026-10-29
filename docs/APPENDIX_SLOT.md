# Programa 4 — Encaixe: a mesma ideia em dois lugares (leitura única, gerada por `scripts/analysis_slot.py`)

beatavg (L = 5000), Qwen3-Coder-30B-A3B-Instruct em vLLM (bf16), braço BD, 120 amostras por corrida, 4 sementes RNG. `família` = escada geométrica rumo ao topo (≥ 3 degraus, razões consecutivas em [0,2; 0,95], CV ≤ 0,35, primeiro degrau ≥ 100 posições abaixo do topo) E átomo em zero (p[0] ≥ 0,1); `escada` = só a escada; `cópia` = mesma pmf do programa entregue; `quase-cópia` = mesmo conjunto de átomos. Taxas sobre as propostas válidas.

## 1. Final por braço e semente

| braço | s11 | s12 | s13 | s14 | mediana | mín–máx | escore da semente | subida mediana |
|---|---|---|---|---|---|---|---|---|
| nohint | 0.3411 | 0.3627 | 0.3535 | 0.3744 | 0.3581 | 0.3411–0.3744 | 0.2708 | 0.0873 |
| words | 0.3478 | 0.3393 | 0.3408 | 0.3408 | 0.3408 | 0.3393–0.3478 | 0.2708 | 0.0701 |
| words_g0 | 0.3429 | 0.3421 | 0.3389 | 0.3377 | 0.3405 | 0.3377–0.3429 | 0.2708 | 0.0697 |
| wordseed | 0.3352 | 0.3319 | 0.3407 | 0.3402 | 0.3377 | 0.3319–0.3407 | 0.2708 | 0.0669 |
| wordseed_pin | 0.3454 | 0.3467 | 0.3295 | 0.3630 | 0.3461 | 0.3295–0.3630 | 0.2708 | 0.0753 |
| famseed | 0.3579 | 0.3700 | 0.3619 | 0.3633 | 0.3626 | 0.3579–0.3700 | 0.2734 | 0.0892 |
| famseed_pin | 0.3815 | 0.3457 | 0.3764 | 0.3389 | 0.3611 | 0.3389–0.3815 | 0.2734 | 0.0877 |
| codehint | 0.3732 | 0.3704 | 0.3746 | 0.3730 | 0.3731 | 0.3704–0.3746 | 0.2708 | 0.1023 |
| codehint_g0 | 0.3722 | 0.3712 | 0.3650 | 0.3808 | 0.3717 | 0.3650–0.3808 | 0.2708 | 0.1009 |
| famseed_words | 0.3469 | 0.3423 | 0.3473 | 0.3409 | 0.3446 | 0.3409–0.3473 | 0.2734 | 0.0712 |
| selfseed | 0.3424 | 0.3499 | 0.3513 | 0.3720 | 0.3506 | 0.3424–0.3720 | 0.3284 | 0.0222 |
| oracle | 0.3742 | 0.3816 | 0.3812 | 0.3742 | 0.3777 | 0.3742–0.3816 | 0.3742 | 0.0035 |

## 2. O que o modelo propôs (por proposta válida; média das sementes)

| braço | válidas/corrida | família | escada | família na ger. 0 | cópia | quase-cópia | melhor em família | melhor fora | final em família |
|---|---|---|---|---|---|---|---|---|---|
| nohint | 115.0 | 0.09 | 0.13 | 0.00 | 0.00 | 0.00 | 0.3744 | 0.3715 | 2/4 |
| words | 118.2 | 0.76 | 0.76 | 0.14 | 0.00 | 0.00 | 0.3478 | 0.3429 | 3/4 |
| words_g0 | 118.0 | 0.10 | 0.10 | 0.30 | 0.00 | 0.00 | 0.3377 | 0.3429 | 1/4 |
| wordseed | 113.8 | 0.02 | 0.02 | 0.00 | 0.00 | 0.00 | 0.3308 | 0.3407 | 0/4 |
| wordseed_pin | 118.5 | 0.07 | 0.07 | 0.00 | 0.00 | 0.00 | 0.3630 | 0.3441 | 3/4 |
| famseed | 117.0 | 0.27 | 0.36 | 0.39 | 0.00 | 0.00 | 0.3633 | 0.3700 | 2/4 |
| famseed_pin | 117.0 | 0.29 | 0.44 | 0.29 | 0.00 | 0.00 | 0.3815 | 0.3490 | 2/4 |
| codehint | 118.5 | 0.86 | 0.89 | 0.48 | 0.00 | 0.00 | 0.3746 | 0.3395 | 4/4 |
| codehint_g0 | 117.2 | 0.29 | 0.31 | 0.54 | 0.00 | 0.00 | 0.3808 | 0.3706 | 4/4 |
| famseed_words | 116.8 | 0.86 | 0.86 | 0.80 | 0.00 | 0.01 | 0.3473 | 0.3447 | 3/4 |
| selfseed | 110.8 | 0.17 | 0.18 | 0.33 | 0.00 | 0.01 | 0.3720 | 0.3709 | 2/4 |
| oracle | 117.0 | 0.39 | 0.45 | 0.31 | 0.00 | 0.00 | 0.3816 | 0.3646 | 4/4 |

## 3. Fatorial forma × lugar × persistência — efeitos principais (diferenças pareadas entre células que só diferem no fator; 4 pares × sementes)

| fator (nível − nível) | final: mediana | final: sinais +/− | final: média | família: mediana | família: sinais +/− | família ger. 0: mediana | família ger. 0: sinais +/− |
|---|---|---|---|---|---|---|---|
| forma (code − words) | +0.0292 | 14/2 de 16 | +0.0258 | +0.21 | 15/1 de 16 | +0.33 | 14/1 de 16 |
| lugar (seed − hint) | -0.0027 | 6/10 de 16 | -0.0051 | -0.29 | 2/14 de 16 | -0.17 | 2/12 de 16 |
| persistência (transient − persistent) | -0.0026 | 6/10 de 16 | -0.0022 | -0.31 | 3/13 de 16 | +0.00 | 7/4 de 16 |

## 4. Contrastes pré-registrados (final, por semente; unidade = semente RNG)

| contraste | s11 | s12 | s13 | s14 | mediana da diferença | sinais (+/−/0) | faixas se sobrepõem? |
|---|---|---|---|---|---|---|---|
| C1: famseed_words − famseed | -0.0110 | -0.0277 | -0.0146 | -0.0224 | -0.0185 | 0/4/0 | não |
| C4: selfseed − words | -0.0054 | +0.0107 | +0.0104 | +0.0312 | 0.0105 | 3/1/0 | sim |
| R: famseed − words | +0.0101 | +0.0308 | +0.0210 | +0.0224 | 0.0217 | 4/0/0 | não |

## 5. Lugar na geração 0 (o portão da tomografia): taxa de família na geração 0, agrupando os dois níveis de persistência (prompts idênticos na geração 0)

| contraste | grupo A (média, n corridas) | grupo B (média, n corridas) | diferença | faixas se sobrepõem? |
|---|---|---|---|---|
| S0a: codehint+codehint_g0 vs famseed+famseed_pin | 0.51 (8) | 0.34 (8) | +0.17 | sim |
| S0b: wordseed+wordseed_pin vs words+words_g0 | 0.00 (8) | 0.22 (8) | -0.22 | sim |

Leitura registrada (PLANO 2026-09-09): no final, H-forma prevê o efeito principal de forma (código > palavras) dominante; H-encaixe, o de lugar (semente > dica); H-persistência, o de persistência (transitório > persistente). Dominante = maior mediana pareada com ≥ 12/16 sinais concordantes; sem dominante = misto, registrado com as taxas por proposta. Tomografia só se o lugar tiver efeito na geração 0 (S0a/S0b com faixas disjuntas e o mesmo sinal), porque patching precisa de contraste num único forward com tokens idênticos; um efeito só de persistência é propriedade do laço, não alvo de patching.

