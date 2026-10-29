# A8 — a curadoria estreita o modelo fora da distribuição? (pré-registro, 2026-09-17)

*Decisão do Roberto em 17/09 à noite ("vamos em frente"), depois do A7. O A7 morreu como nó (nenhum candidato era parede), mas deixou um
achado lateral descritivo e forte: num degrau novo, o adaptador treinado nas provas do próprio modelo resolveu 30/48 enquanto o adaptador
treinado nas provas curadas das **mesmas células** resolveu 0/18, sem nunca tentar o tipo de invariante necessário, ficando abaixo da
própria base (6/48). Este nó mede isso direito: uma pergunta, quatro famílias de degrau novas, regra escrita antes dos dados. Nenhuma
sessão antes deste registro. Leitura: `scripts/analysis_a8_narrow.py`.*

## Desenho fixo

**Os dois adaptadores já existem e não são retreinados**: `a2c4-own2` (135 provas que o modelo produziu e o verificador aceitou) e
`a2c4-curm2` (as provas curadas das mesmas 135 células), ambos LoRA r16, 108 passos, semente 2026091502, hashes em
`docs/a2c4_evidence_v1/analysis/adapter_weights.sha256`. A comparação é justa por construção: mesmas células, mesmo treino, fontes
diferentes.

**Alvos**: as quatro famílias de degrau construídas no A7 (`ladder_walls_v1`), nenhuma vista em treino por nenhum dos dois adaptadores:
W1 pell_mod, W2 plane_lattice, W3 hyperbolic4, W4 lattice_mod_p. **Seis instâncias novas por família** (sementes `a8-<W>-1..6`), com
certificado de ausência de atalho limpo e verificadas em Lean 24/24 (`docs/a8_worlds.json`, `docs/a8_verification.json`).

**Braços** (mesmas células, três planos, 72 sessões cada; agente idêntico ao de `a2c2_baset131`: pensamento 131 072 tokens, T 1,0/top-p
0,95, 3600 s, 12 turnos, verificação 180 s): base `qwen3.8-27b`, `a2c4-own2`, `a2c4-curm2`, todos **sem exemplo**, 3 tentativas por
instância.

## Regras pré-declaradas

Subida(x, y, família): diferença pareada de taxas sobre as seis instâncias da família, sign-flip unilateral p < 0,05 (mínimo 0,0156) **e**
diferença agrupada ≥ 0,25. Queda: o espelho.

- **P-estreita**: `curm2` **cai** contra a base em pelo menos **2 das 4** famílias.
- **P-generaliza**: `own2` **sobe** contra a base em pelo menos **2 das 4** famílias.
- Descritivos, sem regra: own2 contra curm2 por família; taxas por família; tipo de invariante tentado.
- **Vereditos**: `curation_narrows_and_self_generalises` | `curation_narrows_only` | `self_generalises_only` | `neither_moves`.
- **Piso**: numa família em que a base fica abaixo de 0,25 a queda não pode atingir o limiar; isso é reportado como piso, não contornado.
  Pelas taxas da triagem do A7 (base 0/8, 4/8, 2/8, 3/8 em W1–W4), W1 deve ficar no piso e W2–W4 têm margem.
- **Critério de morte**: `neither_moves` encerra a linha: o achado do A7 teria sido próprio de um tipo de degrau.

## O que não se afirma

Uma base, dois adaptadores, uma receita de treino, quatro famílias construídas por nós, três tentativas por instância. "Curadoria" aqui
significa exatamente as nossas provas de referência, uniformes no esqueleto; não é uma afirmação sobre curadoria em geral nem sobre
destilação em outros domínios. Um resultado positivo diz que consolidar provas próprias verificadas, heterogêneas, generaliza melhor que
consolidar provas limpas e uniformes das mesmas células, nesta família e nesta escala.

## Operação e custo

Um pod H200 servindo a base e os dois adaptadores (`scripts/a8_pod.sh`, contexto 163 840, 16 sequências), cadeia `scripts/a8_chain.sh`
com laço de retomada (falha de infraestrutura não é observação, refeita até 3 vezes), leitura, arquivamento, commit e remoção do pod;
guarda independente com prazo 18/09 12:00. 216 sessões de pensamento ≈ 11–12 h ≈ US$55; saldo RunPod US$124,15 no registro. Bedrock: zero.
Evidência: `docs/a8_evidence_v1/`, manifesto SHA-256.

## Emendas prospectivas

- **E1 (18/09, 06:54; operacional; nenhuma regra, plano ou limiar muda; leitura ainda não feita).** O Roberto vai desligar o Mac por
  ≈ 2 h. Como o controle do pod depende do Mac (lição do reinício de 17/09, que deixou ≈ 2 h de pod ocioso), a cadeia, o script do pod e o
  guarda foram encerrados e o **pod removido** às 06:53, com saldo US$78,39. Estado: `a8_base_v1` 72/72 e `a8_own2_v1` 72/72 completos;
  `a8_curm2_v1` com os resultados já obtidos preservados, as sessões em voo movidas para `*.interrupted_shutdown` (não são observação) e o
  restante pendente. O braço curado será **retomado num pod novo** quando a máquina voltar, com as mesmas células e o mesmo plano; nada é
  relido nem refeito do que já tem resultado. A leitura só acontece com os três braços no estado final.
- **E2 (18/09, 12:11; operacional; nenhuma regra, plano ou limiar muda; leitura NÃO feita).** Duas tentativas de retomar o braço
  curado falharam antes de qualquer célula: o envio do adaptador (304 MB) para o pod novo foi interrompido pelo link local às 09:30 e, na
  segunda tentativa, nas quatro repetições (12:02–12:09). Os dois pods foram removidos pelos próprios scripts; custo somado ≈ US$2.
  Por decisão do Roberto ("acho melhor parar"), tudo foi encerrado às 12:11 e **nenhum pod ficou ligado**. Estado congelado:
  `a8_base_v1` 72/72 e `a8_own2_v1` 72/72 completos; `a8_curm2_v1` com **27/72 observadas** (19 das 24 instâncias com ao menos uma), as
  sessões em voo preservadas como `*.interrupted_*` e as falhas de transporte como `*.failed<n>`; nada relido nem refeito. A cadeia em uso
  passou a ser `scripts/a8_fill_curm2.sh`, que só coleta e **nunca dispara a leitura**, justamente para que uma interrupção não consuma a
  leitura única com o braço parcial. Retomada quando o link estiver estável: subir pod, completar as 45 células pendentes, e só então ler.
  Se a retomada não valer o custo, a alternativa registrada é ler com o braço curado incompleto, dizendo o n observado; a regra P-estreita
  perde poder, a P-generaliza não depende dele.
- **E3 (19/09, 06:18; operacional; nenhuma regra, plano ou limiar muda; leitura NÃO feita).** A terceira tentativa de completar o
  braço curado (pod `490bbzaj61lvb0`, 18/09 21:42) **não rodou nenhuma célula**, por erro meu de orquestração: a instalação no pod levou
  1 h 40 (antes, 10 min) e o envio em pedaços mais o servidor levaram mais 1 h 20, de modo que o servidor só ficou pronto às 00:42; a cadeia
  de coleta esperava o endpoint por no máximo 2 h e desistiu às 23:42. Eu tinha verificado o estado às 23:28 e não percebi que o prazo da
  cadeia venceria antes do servidor. O pod ficou ocioso das 00:42 até o guarda (05:30) e o teto de 8 h (05:44) o removerem. Custo dessa
  tentativa ≈ US$37 sem dado novo; saldo US$77 → US$40,81. Estado do braço curado inalterado: 27/72 observadas em 19 de 24 instâncias.
  Correção prospectiva: a espera pelo endpoint na cadeia passa de 2 h para 6 h. Decisão para o Roberto: (a) uma última tentativa com a
  correção (≈ US$25–35, exige recarga para ter margem) e só então a leitura com os três braços completos; ou (b) ler agora com o braço
  curado incompleto, como já previsto em E2, sabendo que com 27 células a regra P-estreita quase não pode passar (poucas instâncias com
  dados por família) e a leitura ficaria dominada pela P-generaliza, que tem os dois braços completos.
- **E4 (19/09, 07:54; A8-c: SEGUNDA leitura, declarada antes de qualquer célula nova; nenhuma regra, plano ou limiar muda).** A leitura
  única do nó foi feita em 19/09 às 07:01 com o braço curado incompleto (27/72), como previsto na E2, e **permanece a leitura do nó**
  (`self_generalises_only`, `docs/A8_CURADORIA_ESTREITA_RESULTADOS_V1.md`). O Roberto recarregou o RunPod (saldo US$190,81) e tem ≈ 24 h de
  máquina ligada. As 45 células pendentes de `a8_curm2_v1` são completadas num pod novo, com o mesmo plano, o mesmo agente, o mesmo comando de
  instalação e as mesmas flags de serviço (`scripts/a9_pod.sh`, fase 1; cadeia `scripts/a9_chain.sh` com o mesmo laço de retomada; falha de
  infraestrutura não é observação e é refeita até 3 vezes, contagem acumulada em `retries.json`). A **A8-c** é uma segunda leitura com o mesmo
  script e as mesmas regras, gravada em arquivos próprios (`docs/a8_results/narrow_c.{md,json}`), sem tocar os da primeira. Como base e own2 não
  mudam, P-generaliza não pode mudar; o único veredito que pode diferir do primeiro é `curation_narrows_and_self_generalises`, se curm2 cair
  contra a base em ≥ 2 das 4 famílias. Ressalvas declaradas: as 45 células novas rodam em outro dia e outro pod que as 27 primeiras (mesma
  pilha por comando; versões no log); W1 e W4 seguem no piso, onde a queda não pode atingir o limiar. Evidência própria
  `docs/a8c_evidence_v1/` (braço curado completo e a segunda leitura; base e own2 seguem em `docs/a8_evidence_v1/`).
(registrar aqui, com hora do relógio ou do commit, antes de qualquer célula afetada)
