# A2 — piloto de competência de modelos abertos com Lean: leitura única, 2026-09-13 — **sem instrumento no ambiente sem Mathlib**

*Pré-registro `A2_PILOTO_COMPETENCIA_V1.md` (regras: competência L1 ≥ 0,5; margem; efeito do exemplo em L4/L5; admissão de A2 só
com as três). Leituras por `scripts/analysis_a2_pilot.py` → `APPENDIX_A2_PILOT1_V1.md`, `..._PILOT2_V1.md`,
`..._PILOT3_CODER_V1.md`, `..._PILOT3_THINKING_V1.md`. Evidência integral em `docs/a2_pilot_evidence_v1/` (manifesto SHA-256).
Infraestrutura nova: `openai_session_v1.py` (mesmo protocolo de A1 sobre API compatível com OpenAI), `a2_vllm_pod.sh`
(vLLM na H100 pelo proxy, remoção garantida), despacho por provedor no executor; 21 testes.*

## Resultados (taxas = provas verificadas / sessões)

| piloto | modelo, orçamento, nota | sem exemplo L1 / L2 / L3 / L4 / L5 / E | L4 esqueleto / referência | L5 esqueleto / referência | decisão pela regra |
|---|---|---|---|---|---|
| 1 | Qwen3-Coder-30B-A3B-Instruct, 8k | 0 / 0 / 0 / 0 / 0 / 0 (de 24) | 0/24 / 0/24 | 0/24 / 0/24 | sem competência: trocar de modelo |
| 2 | Qwen3-30B-A3B-Thinking-2507, 8k | 0 / 0 / 0 / 0 / 0 / 0 (de 24) | 0/24 / 0/24 | 0/24 / **8/24** | sem competência: parar neste ambiente |
| 3a | Coder + nota de ambiente, 8k (L1–L3) | 0 / 0 / 0 (de 24) | — | — | sem competência |
| 3b | Thinking + nota, 16k (L1–L3; 24 de 72, parado por 524 do proxy) | 0 (de 24 sessões) | — | — | sem competência (parcial) |

Total: 552 sessões abertas, zero falhas de infraestrutura fora do 524; ≈ 2,3 h de H100 ≈ US$7; zero Bedrock.

## Leitura

1. **Os dois modelos abertos não escrevem Lean 4 válido neste ambiente (Std, sem Mathlib) sob este protocolo.** O Coder
   formula a ideia certa em quase toda sessão (a diferença conservada, a preservação por passo, a indução) e falha na
   forma: táticas do Mathlib inexistentes aqui (`ring`, `linarith`: 285 de 537 submissões com exemplo), `sorry`,
   sintaxe (`unexpected token`, `⟨…⟩` sem tipo esperado), importações. A nota de ambiente removeu quase toda a
   "tática desconhecida" (6 contra 285) e não removeu a sintaxe. A Thinking gasta o orçamento pensando (143/144 sessões
   no teto de saída sem exemplo) e, quando submete, erra a sintaxe de nível superior (`unexpected identifier; expected
   command`).
2. **O efeito de forma existe na Thinking, mais fraco que na Opus e só na forma exata.** Com a prova curada de E (mesma
   forma quadrática que L5), 8/24 em L5 (+0,72 bits, p = 0,0625, quatro de seis instâncias), em uma requisição cada,
   5–7k tokens; com o esqueleto genérico do P3, 0/24; em L4, 0/24 com ambos. Confirma A1 v3 num segundo modelo: o que
   transfere é a forma da prova, e transfere tanto melhor quanto mais próxima do alvo.
3. **A2 não tem instrumento no ambiente sem Mathlib**, pela regra pré-declarada. Não é falta de ideia nem de exemplo: é
   que o Lean que os modelos abertos conhecem é o do Mathlib. A Opus, que conhece os dois, não precisou de nada disso.

## Instrumento, correções e limites

- Varredor de tokens proibidos passou a ignorar comentários (a Opus não sofreu isso em 820 verificações; o Coder
  escreve comentários com a palavra `constant`). Fumaças não lidas: uma sessão por modelo.
- O proxy HTTP do RunPod corta respostas que passam de ≈ 120 s (HTTP 524): parou o piloto 3b por regra. Streaming SSE
  implementado no laço depois disso (`assemble_stream`, testado), não usado em nenhuma leitura deste documento.
- Nota de ambiente (`a2_task_note_std_only_v1.md`): informação sobre o ambiente, igual para todos os braços, no hash da
  entrada; a Opus não a recebeu. Comparações entre a Opus e os abertos são descritivas (tokenizações e amostragens
  diferentes); as regras do piloto são internas a cada modelo.
- Seis instâncias; o teste exato de sinal tem p mínimo 0,0156. Dois modelos, uma família de mundos.

## Ambiente Mathlib, pronto e não executado

Sonda: Mathlib `v4.33.1` existe para o toolchain, cache de oleans em 2,5 min (7,5 GB), `ring`/`nlinarith`/`omega`
compilam. Implementado (`ebf12ee`): pacotes compartilhados fora do repositório (`CM_LAKE_SHARED`), gancho no
verificador e no gerador, sabor `env=mathlib` dos mundos (Base importa Mathlib; lakefile com a dependência fixada);
uma instância verificada de ponta a ponta (referências pelo verificador das sessões e mutações; ≈ 55 s por mundo).
Nenhuma sessão de modelo sob Mathlib foi executada. É mudança de instrumento: exige pré-registro do zero e a Opus
re-lida no mesmo ambiente para comparabilidade.

## Próximo passo (decisão com o Roberto)

(a) **Piloto Mathlib**: mesmos degraus, mundos `env=mathlib`, Thinking-2507 com streaming e 16k (e, se quiser, um
provador aberto especializado em Lean como segundo modelo), braços nenhum em L1–L5/E e esqueleto/referência em L4/L5,
mesmas regras; ≈ US$8 de GPU; mais a Opus nos mesmos mundos em L4/L5 (≈ US$15 de Bedrock) para o teto de referência.
(b) Encerrar A2 neste domínio e voltar à árvore (C4 com verificador, ou a escrita).

## Correção posterior (13/09, antes do piloto Mathlib; nenhuma decisão muda)

O script de leitura `analysis_a2_pilot.py` fixava o rótulo de orçamento `b8k` ao contar as sessões por degrau. O piloto 3b (Thinking + nota)
rodou com `b16k`, e o JSON arquivado `a2_pilot3_thinking_results_v1.json` tem por isso a tabela por degrau vazia (n = 0 em todos os degraus;
a linha "0 (de 24 sessões)" acima veio do log, e está certa). O script passa a ler o rótulo do plano (`main_budget_label`), com teste; as
leituras dos pilotos 1, 2 e 3a reproduzem byte a byte, e a releitura de 3b (`a2_pilot3_thinking_results_v1_reread.json`, o arquivado fica
intacto) dá L1 0/8, L2 0/5, L3 0/10 (23 observadas: 22 no teto de saída, 1 orçamento esgotado; 1 falha de infraestrutura excluída).
Decisão pré-declarada inalterada: sem competência.
