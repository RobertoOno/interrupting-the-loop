# A2 sem curador, iteração 2 — a escada sobe sem curador? (pré-registro, 2026-09-15, 16:30)

*Continuação aprovada pelo Roberto ("vamos seguir esta linha") após a leitura da iteração 1 (`docs/A2_SEM_CURADOR_RESULTADOS_V1.md`,
`self_consolidation_moves`): as provas próprias verificadas de L1–L3, consolidadas sem curador, transferem a instâncias novas dos mesmos
degraus e, com raciocínio, igualam o curado; em L4, L5 e E ficam em zero porque nada foi produzido ali. Pergunta desta iteração: o
adaptador próprio com raciocínio produz provas verificadas em L4/L5/E de instâncias de treino e, consolidadas de forma cumulativa, elas
sobem o modelo nesses degraus em instâncias retidas? Nenhuma célula antes deste registro; leitura pelo script escrito antes dos dados
(`scripts/analysis_a2_own2.py`).*

## Desenho fixo

**Fase 1 — produção (noite de 15→16/09), servidor com a base + `a2c3-own`.**
- Produção: `a2c3-own` (o adaptador da iteração 1, hashes em `docs/a2c3_evidence_v1/analysis/adapter_weights.sha256`) com pensamento
  ligado, 131 072 tokens, T 1,0/top-p 0,95, 3600 s, 12 turnos, verificação 180 s (a configuração dos braços de pensamento), em **L4, L5 e E
  das 48 instâncias de treino**, uma tentativa por célula (144 células, `docs/a2c4_prod_plan_v1.json`, 12 em paralelo). Sem seleção: toda
  prova aceita pelo verificador entra.
- Comparador: a **base com o mesmo pensamento em L4, L5 e E das seis instâncias retidas**, quatro tentativas (72 células,
  `docs/a2c4_baset131_plan_v1.json`), no mesmo servidor, depois da produção. Completa o braço baset131 (que só tinha L2/L3).
- Scripts: `scripts/a2c4_serve_pod.sh` (H200, mesma pilha, LoRA), `scripts/a2c4_prod.sh` (laço de retomada), `scripts/a2c3_guard.sh`.
- **Portão de produção**: se a produção render **menos de 12** provas verificadas em L4/L5/E (somadas), o nó encerra sem treinar com o
  veredito `stalls_at_production` (o laço estaciona: o adaptador com raciocínio não produz nos degraus seguintes).

**Conjunto de treino cumulativo (sem seleção).** `own.jsonl` = as 60 linhas próprias da iteração 1 (byte-idênticas) + uma linha por
célula nova aceita, renderizada como antes (`scripts/a2c4_prepare.py`, que reutiliza `a2c3_prepare`). `curm.jsonl` = as linhas curadas de
`docs/a2c2_data/p2.jsonl` das mesmas células (antigas e novas). Portão de dados: 100 % recompiladas.

**Fase 2 — consolidação e teste (16/09).** Dois LoRA com a receita da consolidação (r 16, α 32, dropout 0,05, atenção + MLP, AdamW 2e-4,
cosseno, batch efetivo 8, 4096 tokens, bf16, **108 passos**, semente **2026091502**, treino sem pensamento): `a2c4-own2` (cumulativo
próprio) e `a2c4-curm2` (curado pareado cumulativo). Quatro braços nas seis instâncias retidas, células idênticas às já lidas
(configuração do agente conferida igual à de `a2c2_base` e `a2c2_baset131`; só o nome do modelo muda): `a2c4_own2_v1` e `a2c4_curm2_v1`
(sem pensamento, 16k, seis degraus × 4 = 144 cada); `a2c4_own2t131_v1` e `a2c4_curm2t131_v1` (pensamento 131k, **L2–E** × 4 = 120 cada;
L2/L3 medem retenção). Ordem: own2, own2t131, curm2, curm2t131. Comparadores já lidos: base, p2, own (iteração 1), p2t131, ownt131
(L2/L3), baset131 (L2/L3 de 14/09 + L4/L5/E desta fase 1).

## Regras pré-declaradas (`scripts/analysis_a2_own2.py`)

Subida(x, y, degrau): diferença pareada de taxas sobre as seis instâncias, sign-flip unilateral p < 0,05 (mínimo 0,0156) **e**
diferença agrupada ≥ 0,25; queda: o espelho.

- **P-subida-pensamento**: own2t131 sobe contra baset131 em L4, L5 ou E.
- **P-subida-simples**: own2 sobe contra base em L4, L5 ou E.
- **Retenção** (descritivo): own2t131 cai contra ownt131 em L2 ou L3, ou own2 cai contra own em L1 (os dados novos apagaram a forma antiga?).
- **Valor da curadoria** (descritivo): curm2 sobe contra own2 em algum degrau, ou curm2t131 contra own2t131.
- **Veredito**: `ladder_climbs_without_curator` se P-subida-pensamento ou P-subida-simples; senão `consolidation_does_not_climb`
  (produziu e consolidou, mas nada sobe em L4/L5/E); `stalls_at_production` se o portão de produção falha (sem leitura).
- **Critérios de morte do nó**: `stalls_at_production` e `consolidation_does_not_climb`. Status: proveitoso se sobe; limite se morre.
  Nada é escolhido pelo tamanho do efeito; leitura única.

## O que não se afirma

Uma família, seis instâncias retidas, um modelo, uma semente por iteração, duas iterações. Se subir, é a primeira subida de degrau sem
curador nesta família, não descoberta em problema alheio; se não subir, o laço precisa de mais tentativas, de outro sinal ou de um
curador, e o próximo passo é decidido com o Roberto antes de gastar no mundo real. Não há controle de "a base produz em L4/L5/E de
treino" (custaria mais uma noite); a comparação limpa é no teste retido, contra a base com o mesmo pensamento.

## Operação e custo

Fase 1: ≈ 40 min de subida + 216 células de pensamento (144 + 72) a ≈ 30 min com 12/8 em paralelo ≈ 8–10 h → ≈ US$40–45; cap do pod
14 h; guarda com prazo 16/09 10:00. Fase 2: pod ≈ 1,5 h + testes (288 células curtas + 240 com pensamento) ≈ 10–12 h → ≈ US$50–60.
Total ≈ US$95–105; saldo RunPod US$175 no registro. Bedrock: zero. Evidência: `docs/a2c4_evidence_v1/`, manifesto SHA-256. A fase 2 é
encadeada automaticamente (`scripts/a2c4_phase2.sh`), como na E1 da iteração 1.

## Emendas prospectivas

- **Observação registrada em 15/09, 23:05 (NÃO é emenda: nenhuma regra, plano, célula ou limiar muda).** A produção terminou às 21:00
  com **75/144** provas verificadas (E 38/48, L5 35/48, **L4 2/48**), muito acima do portão de 12; o conjunto cumulativo terá 135 exemplos.
  O comparador (base com pensamento, retidas) ia em 25/72 células às 22:50: E 7/10, L5 5/9, L4 2/9. Duas coisas ficam registradas agora,
  antes de qualquer célula de teste, para que não sejam lidas depois como explicação posterior: (i) **L4 é parede dos dois lados** — o
  laço quase não produz ali (2/48) e a base com pensamento também não resolve (2/9), exatamente o degrau onde a forma curada bastava
  (p2 24/24 em 14/09); (ii) **em E e L5 a base com pensamento já resolve bastante**, de modo que a margem para a subida pré-declarada
  (≥ 0,25) é estreita em E (0,30 com as células lidas) e média em L5 (0,44). As regras e os limiares ficam exatamente como estão; se a
  subida com pensamento não passar por teto, isso será dito como teto, não como ausência de efeito, e o contraste sem pensamento
  (own2 contra base, que tem margem larga: base 0/24 em E, 1/24 em L5) segue como a outra metade da leitura.
- **Correção da observação acima, 16/09, 02:10 (também NÃO é emenda; nenhuma regra, plano, célula ou limiar muda).** A observação das
  23:05 estava errada em dois pontos, por ter sido escrita com 25 das 72 células do comparador. Com 67 células lidas, a base com
  pensamento nas instâncias retidas faz **E 12/22 (0,55), L5 10/23 (0,43), L4 9/22 (0,41)**, com acerto em todas as seis instâncias de L4.
  Logo: (i) **não há teto** — a margem para a subida pré-declarada é 0,45 em E, 0,57 em L5 e 0,59 em L4, e a regra está inteiramente
  viva; (ii) **L4 não é parede dos dois lados**: é parede só do adaptador. Sob a mesma configuração de pensamento, a base resolve L4 em
  0,41 e o `a2c3-own` resolve 0,04 (2/48) na produção, enquanto supera a base em E (0,79) e L5 (0,73). Diagnóstico das primeiras
  submissões de L4 da produção: **50 de 50 não declaram `measure`** — o adaptador aplica o estilo que aprendeu das próprias provas de
  L1–L3 (indução direta, sem lema auxiliar) num degrau que exige medida quadrática com deslocamentos. Isso é indício de **transferência
  negativa da autoconsolidação**, o mesmo fenômeno do p1 em L1, agora vindo do produto do próprio modelo. Ressalva: produção e
  comparador correm em conjuntos de instâncias diferentes (treino e retidas), então a comparação acima é sugestiva, não estabelecida; a
  leitura pré-registrada testa isso nas mesmas células (own2 contra base, own2t131 contra baset131, com queda medida pela regra
  espelhada). Nada foi alterado em função destes números.
(registrar aqui, com hora, antes de qualquer célula afetada)
