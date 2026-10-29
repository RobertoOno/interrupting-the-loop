# A2 — piloto de competência de um modelo aberto com Lean (pré-registro, 2026-09-13)

*Pré-condição de A2 (consolidar esqueletos curados em pesos). A1 mediu em Opus 5: forma vence ideia; a referência curada
poupa ≈ 2,3 bits por degrau. A2 precisa de um modelo aberto, ajustável, que (i) resolva algo dos degraus sem exemplo,
(ii) tenha margem, e (iii) mostre o efeito do exemplo em contexto, o teto que os pesos tentarão gravar. Sem isso, A2
não tem instrumento. Nenhuma sessão antes deste registro.*

## Desenho fixo

- **Modelo**: Qwen3-Coder-30B-A3B-Instruct (o propositor do paper 3), servido por vLLM (`vllm/vllm-openai:latest`, API
  compatível com OpenAI, `--tool-call-parser qwen3_coder`) numa H100 do RunPod pelo proxy HTTP, sem SSH; amostragem
  T 0,7, top-p 0,8 (cartão do modelo). Laço de sessão `openai_session_v1.py`: mesmo prompt de sistema, mesma ferramenta
  `check_solution`, um chamado por turno, ≤ 12 turnos, 600 s por sessão, 300 s por requisição, orçamento de saída 8 192
  por sessão e por requisição; Lean local no Mac pelo mesmo verificador (tipo exato, axiomas). Registro por sessão
  idêntico ao de A1 (sem custo por token; horas de GPU pelo lançador `a2_vllm_pod.sh`, teto de 3 h e remoção
  garantida).
- **Instâncias**: `a2p-1`…`a2p-6` (fase `a2_pilot`, com E; 36 mundos verificados e falsificáveis; excluídas de A2).
- **Plano A** (`a2_pilot_none_v1`): nenhum exemplo × {L1, L2, L3, L4, L5, E} × 4 tentativas = 144 sessões.
- **Plano B** (`a2_pilot_examples_v1`): esqueleto (o exemplo genérico de P3) e referência (a prova curada de E, no formato
  de A1 v3) × {L4, L5} × 4 = 96 sessões.
- Oito sessões em paralelo (o servidor agrupa). Ordem embaralhada por semente.

## Regras pré-declaradas (`scripts/analysis_a2_pilot.py`)

- **Competência**: taxa agrupada sem exemplo em L1 ≥ 0,5. Abaixo disso o modelo não escreve nem a prova mais simples
  neste protocolo, e o piloto encerra com "sem competência": trocar de modelo uma vez (Qwen3-30B-A3B-Thinking-2507) e,
  se repetir, parar A2 neste domínio.
- **Margem**: pelo menos um degrau entre L3, L4, L5 e E com taxa agrupada estritamente entre 0 e 1.
- **Efeito do exemplo**: em L4 e L5, referência ou esqueleto poupam bits sobre nenhum (permutação por sinal sobre as seis
  instâncias, unilateral, p < 0,05; com seis instâncias o mínimo é 0,0156); descritivo: diferença agrupada ≥ 0,25.
- **Admissão de A2**: as três regras passam. Se competência e margem passam mas o exemplo não move, A2 não tem teto a
  gravar e encerra com isso como resultado. Nada é escolhido pelo tamanho do efeito; a decisão é binária por regra.

## Correção prospectiva do instrumento (13/09, 08:45, antes do plano A)

Na fumaça, a primeira submissão do modelo aberto foi rejeitada por "forbidden constructs: constant": a palavra estava num
comentário em inglês. O varredor de tokens proibidos passa a ignorar comentários de linha e de bloco (teste adicionado).
A1 com a Opus não teve nenhuma rejeição desse tipo em 820 verificações; nenhum resultado arquivado depende disso. A
fumaça (uma sessão em L1, quatro turnos, 17 s, `tool_calls` estruturado, ideia certa e forma errada em Lean) não é lida.

## O que não se afirma

Nada sobre consolidação ainda; nada sobre outros modelos; comparação com a Opus é descritiva (tokenizações e
amostragens diferentes). É o instrumento de A2 sendo calibrado, não A2.

## Operação e custo

H100 a ≈ US$2,7/h, estoque alto; subida do servidor ≈ 15 min (imagem + 61 GB); 240 sessões ≈ 30–40 min. Estimativa
≈ US$4–6 de GPU; zero Bedrock. Saldo RunPod US$33 no registro. Fumaça obrigatória antes do plano A: uma chamada com
ferramenta ao endpoint para confirmar o parser (`tool_calls` estruturado). Evidência em `docs/a2_pilot_evidence_v1/`.

## Piloto 3 (proposta, 13/09 09:45; NÃO executado sem decisão do Roberto, porque a regra pré-declarada manda parar)

Piloto 1 (Qwen3-Coder-30B-A3B-Instruct): 240 sessões, zero soluções, com e sem exemplo; falha dominante "unknown tactic"
(táticas do Mathlib num ambiente Std) e `sorry`. Piloto 2 (Qwen3-30B-A3B-Thinking-2507): em curso, todas as sessões no
teto de 8k pensando, poucas submissões. Proposta mínima que ataca as duas falhas sem mudar mundos, verificador ou
esqueletos: (a) nota fixa de ambiente no `TASK.md` (`a2_task_note_std_only_v1.md`: sem Mathlib; táticas disponíveis;
`sorry` rejeitado), igual para todos os braços e incluída no hash da entrada; (b) para a Thinking, orçamento de 16k por
sessão (os tokens de raciocínio contam). Planos `a2_pilot3_coder_note_plan_v1.json` e `a2_pilot3_thinking_note_plan_v1.json`:
L1–L3, sem exemplo, 4 tentativas, 72 sessões cada; regra: competência = taxa(L1) ≥ 0,5 em algum dos dois; se passar, o
piloto completo (planos A e B) roda para esse modelo com a nota e o orçamento fixados; se não, A2 encerra neste domínio
sem Mathlib, e a alternativa é um ambiente com Mathlib (mudança de instrumento, a pré-registrar do zero). Custo ≈ US$4.
A nota é informação sobre o ambiente, não forma de prova; a Opus não a recebeu, e as comparações de A2 são internas ao
modelo aberto.
