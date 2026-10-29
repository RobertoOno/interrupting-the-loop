# A2 — consolidação da forma em pesos (pré-registro, 2026-09-13, 17:40; aprovado em princípio pelo Roberto às 17:05)

*Pergunta de A2: o operador que poupa ≈ 2 bits em contexto na Opus (A1 v2/v3), o esqueleto curado da prova, pode ser escrito nos pesos
de um modelo aberto e transferir para instâncias novas? Não exige competência de base: a competência é o desfecho. Proposta em
`A2_CONSOLIDACAO_PROPOSTA_V1.md`; este documento fixa o que falta e congela. Nenhuma sessão de teste antes deste registro; os
exemplos de treino foram renderizados e estão em verificação pelo verificador real (nenhum modelo envolvido).*

## Substrato

**Qwen3.8-27B** (`Qwen/Qwen3.8-27B`, pesos BF16, Apache-2.0): no piloto Mathlib foi o único modelo aberto a produzir a forma
(11/144 sem exemplo; 5 das 11 provas com o lema auxiliar separado), com L1–L3 baixos e L4/E em zero: há o que subir em todos os
degraus. Treino e teste nos pesos BF16 com adaptador LoRA servido pelo vLLM (`--enable-lora`) numa H200 (141 GB); o piloto
serviu o checkpoint FP8, diferença registrada como limitação. Fallback técnico, só se o LoRA nesta arquitetura híbrida não servir
no vLLM: Qwen3-30B-A3B-Thinking-2507 (mesmo desenho; registrar antes de qualquer sessão).

## Formato único de treino e teste: modo provador, sem pensamento

Prompt = molde do provador com as definições do mundo inline e `theorem evaluation_solution : ⟨enunciado⟩ := by` (idêntico ao do
piloto, `render_prover_prompt` do workspace sem exemplo); resposta = o arquivo Lean completo (cabeçalho, definições, lemas
auxiliares, teorema com prova), sem cercas. `enable_thinking=false` no template em treino e em teste, para todos os braços,
inclusive a base: o que se grava é a resposta, não o raciocínio; o teto em contexto do 27B com pensamento e ferramenta (plano B
do piloto, E6) entra só como descritivo. Amostragem do cartão para o modo sem pensamento: T 0,7, top-p 0,8. Laço de sessão do
piloto (`mode=prover`): 12 turnos, 16 384 tokens por sessão e por requisição, 900 s, verificador 180 s, mesma extração e mesmo
verificador (tipo por `#check`, axiomas, `sorry` rejeitado), feedback textual.

## Dados (`docs/a2c_data/`, `scripts/a2c_prepare.py`; manifesto com SHA-256 de cada exemplo)

- 48 instâncias de treino (`a2c-train-01..48`, fase `a2_consolidation_train`, `env=mathlib`, seis degraus) e 6 retidas
  (`a2c-held-1..6`, fase `a2_consolidation_heldout`): `S1B050922 S84218E73 S4C4C76BF S80BF22C3 SCCE80B1D SAEF7D571`, nunca vistas
  no treino; constantes novas, mesma família. Ids sem colisão com o piloto. **Retidas verificadas 36/36 (13/09, 17:40:
  `verify_step` + `mutation_check`, `runs/a2/a2c_verify/`)**; as de treino são cobertas pela verificação de cada exemplo.
- **p1** (forma de E/L5): 96 exemplos = referência curada de E e L5 das 48 instâncias (`measure`, `step_measure` por `cases`/`simp
  only`/`grind`, `bridge` por indução, fecho `Int.sq_nonneg` + `grind [measure, start]`).
- **p2** (currículo): 288 exemplos = referência curada dos seis degraus (formas `omega` em L1–L3, `grind` em L4/L5/E).
- **p3** (controle de sintaxe): 288 exemplos = mesmos mundos e cabeçalho, alvo **não indutivo** `∀ s, move_k (move1 s) = s` (os
  movimentos são inversos dois a dois), prova `intro; cases; simp [move1, move_k] <;> omega`: mesmo formato, mesmas táticas, sem
  medida, sem lema do passo, sem ponte.
- Todo exemplo p1/p2 passa pela extração e pelo verificador real antes do treino (deve ser aceito); todo p3 compila sozinho sem
  `sorry`. Exemplo que falhar é corrigido no renderizador e re-verificado, antes de qualquer treino; registrado em `verification.json`.

## Treino (LoRA, `scripts/a2c_train.py`, na H200)

Um adaptador por braço, mesma receita: LoRA r = 16, α = 32, dropout 0,05, módulos `q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,
down_proj` do modelo de linguagem (atenção e MLP de todas as camadas; as projeções DeltaNet ficam intactas, o que evita o bug
conhecido do vLLM com LoRA parcial nessas projeções); AdamW, lr 2e-4, cosseno, warmup 5 %, lote efetivo 8, perda só nos tokens da
resposta, comprimento máximo 4 096, bf16, semente 2026091301. **Passos iguais entre braços: 108 passos** (p2 e p3: 3 épocas de
288; p1: 9 épocas de 96). Nenhuma seleção de checkpoint por desempenho de teste; fica o último. Adaptadores baixados para a
evidência (hash).

## Teste (planos `docs/a2c_{base,p1,p2,p3}_plan_v1.json`, 144 sessões cada = 576)

Seis instâncias retidas × seis degraus × 4 tentativas, sem exemplo, em cada braço: base (modelo servido `qwen3.8-27b`, sem
adaptador) e os três adaptadores (`a2c-p1`, `a2c-p2`, `a2c-p3`, módulos LoRA do vLLM). Mesmo servidor, mesma ordem embaralhada
(semente 2026091301), 8 em paralelo, Lean no Mac. Preflight `--no-lean` por plano; fumaça de uma requisição por adaptador (não lida).

## Regras pré-declaradas (`scripts/analysis_a2_consolidation.py`, escrito antes dos dados; testes sintéticos)

- **sobe(braço, degrau)**: diferença de taxa contra a base por instância retida, permutação por sinal unilateral p < 0,05 (mínimo
  0,0156) **e** diferença agrupada ≥ 0,25.
- **P1 (forma gravada transfere dentro da forma)**: p1 sobe em E ou L5 e em nenhum de L1–L4.
- **P2 (currículo)**: p2 sobe em ≥ 4 dos seis degraus.
- **P3 (controle)**: p3 não sobe em degrau nenhum. Se subir, o que se grava é sintaxe, não forma: veredito `syntax_not_form`,
  independentemente de P1/P2.
- Vereditos: `form_written_and_form_specific` (P1 e P3 limpo) · `form_written_not_specific` (p1 sobe fora de E/L5, P3 limpo) ·
  `curriculum_only` (P2 sem P1) · `partial_rise_below_rules` · `nothing_written` (nenhum braço sobe: a forma não é gravável com
  esta dose e escala; limite de A2 neste domínio) · `syntax_not_form`. Descritivo: bits poupados por braço e degrau; taxa do p1 em
  L5 contra o teto em contexto do piloto (plano B, E6).
- Falhas de infraestrutura não são observadas; uma rodada parada por falha técnica é retomada só pelas células sem resultado, com o
  mesmo adaptador e servidor, registrada.

## Operação e custo

Uma H200 (Secure, ≈ US$4,6/h) com SSH: instalar dependências, treinar os três adaptadores em sequência (≈ 10–20 min cada), servir
BF16 + LoRA com vLLM, rodar os quatro planos, remover o pod. ≈ 4–5 h ≈ US$20–25 de GPU; zero Bedrock. Evidência em
`docs/a2c_evidence_v1/` (dados, adaptadores por hash, sessões, logs, leitura).

## O que não se afirma

Nada sobre progressão ou invenção: é A1 v3 transposto para pesos. Nada sobre outros domínios nem sobre o 4B. Um positivo diz que o
órgão que falta pode ser alimentado por consolidação curada e que a transferência respeita a forma; um negativo diz que, nesta dose,
não. Ambos entram no paper 5 (alavanca e limites).

## Emendas prospectivas

(registrar aqui, com hora, antes de qualquer célula afetada)
