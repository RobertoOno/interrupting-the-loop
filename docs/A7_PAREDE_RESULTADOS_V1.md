# A7 — instrumento com parede real: resultados (leituras únicas, 2026-09-17; status: LIMITE, com achado lateral forte)

*Pré-registro `docs/A7_PAREDE_V1.md` (16/09, 21:18), emendas E1 (21:24, antes da primeira célula) e E2 (17/09, 13:22, operacional), mais
três observações registradas antes das leituras. Pergunta: existe nesta família um degrau que a base com pensamento pleno não atravessa, e
o laço sem curador o atravessa? Leituras pelos scripts escritos antes dos dados (`analysis_a7_screen.py`, `analysis_a7_confirm.py`).
Evidência: `docs/a7_screen_evidence_v1/` (616 arquivos) e `docs/a7_confirm_evidence_v1/` (1 150 arquivos), manifestos verificados.*

## Triagem (17/09, 02:20): um candidato entre quatro

| candidato | base, sem exemplo | base com prova irmã | own2 | classe |
|---|---|---|---|---|
| W1 Pell módulo primo | **0/8** | 6/8 | 7/8 | `wall_candidate` |
| W2 rede no plano | 4/8 | 7/8 | 3/8 | `not_a_wall` |
| W3 hiperbólica em 4 campos | 2/8 | 8/8 | 7/8 | `not_a_wall` |
| W4 primo grande | 3/8 | 7/8 | 7/8 | `not_a_wall` |

Três dos quatro candidatos caem na primeira medida: a base com pensamento pleno os resolve. Só W1, a composição de forma quadrática com
resíduo, passa à confirmação.

## Confirmação de W1 (17/09, 16:51): não é parede em escala

Seis instâncias retidas novas, verificadas em Lean 6/6.

| braço | resolvidas | mediana de tokens | mediana de submissões | sessões que tentam algo modular |
|---|---|---|---|---|
| base, sem exemplo (8 tentativas × 6) | **6/48** | 131 072 (teto) | 3 | 29/48 |
| own2, laço sem curador (8 × 6) | **30/48** | 70 039 | 9 | 46/48 |
| base com a prova irmã (4 × 6) | 19/24 | 90 582 | 4 | 23/24 |
| curm2, curado pareado (4 × 6, interrompido) | **0/18** | 131 072 (teto) | 1 | **0/18** |

**Veredito pré-declarado: `not_a_wall_at_scale`; veredito do programa: `no_crossing`.** Basta um acerto da base para o degrau deixar de
ser parede, e ela acertou 6. O 0/8 da triagem era compatível com uma taxa de ≈ 10 % por tentativa; a confirmação existia exatamente para
isso, e funcionou. O contraste own2 contra base sobe pela regra (+0,50, p = 0,016), mas a regra de travessia só se aplica a uma parede
confirmada, e não há.

## O achado lateral, que é o resultado forte desta rodada

Os dois adaptadores foram treinados **nas mesmas células** (mesmas instâncias e degraus): um com as provas que o próprio modelo produziu e
o verificador aceitou, o outro com as provas curadas por nós. Num degrau novo, que nenhum dos dois viu no treino:

- o adaptador **do laço** resolve 30/48 e tenta um invariante modular em 46 das 48 sessões;
- o adaptador **curado** resolve 0/18 e **nunca tenta nada modular**: escreve uma vez o esqueleto rígido que aprendeu (medida, lema de
  passo, igualdade exata), que não pode funcionar aqui, e queima os 131 mil tokens; mediana de uma submissão por sessão;
- a **base** fica em 6/48, com a ideia certa em 29 das 48 sessões e falhando na forma da prova em Lean.

Ou seja: **consolidar as provas curadas estreita o modelo abaixo da própria base num degrau novo, e consolidar as provas próprias o
amplia.** As provas próprias são heterogêneas (táticas variadas, `Int.ModEq`, lemas por movimento); as curadas são todas o mesmo esqueleto.
A curadoria comprava eficiência dentro da distribuição treinada (iterações 1 e 2); fora dela, cobra caro. É a transferência negativa da
curadoria, medida contra o controle certo.

Ressalva: o braço curado ficou em 18 das 24 células porque o guarda removeu o pod no prazo (16:30) enquanto ele ainda rodava. 0/18 com
zero tentativas modulares é sinal claro, mas é um braço descritivo e incompleto.

## Sobre a pergunta "novo para o sistema"

Não foi respondida, e o instrumento é que falhou. Nenhum dos quatro candidatos foi parede para a base com pensamento pleno. O que
chamávamos de parede na triagem era falta de amostra. Mais: o diagnóstico de W1 mostra que, quando a base falha, ela falha **na forma da
prova em Lean**, não na ideia; o teste operacional de "parede de ideia" (a prova irmã destrava) não separa as duas coisas, porque a prova
irmã entrega ideia e forma juntas. Construir uma parede real nesta família exigiria um degrau cuja ideia a base não produz em dezenas de
tentativas, e não soubemos construí-lo com invariantes conservados.

## Registro operacional honesto

- **Reinício do Mac (11:22)**: derrubou cadeia, guarda e arquivamento; o pod sobreviveu cobrando ≈ 2 h sem controle (≈ US$9). O braço
  curado foi refeito do zero no mesmo servidor (E2); as 13 sessões interrompidas estão preservadas como `*.interrupted_reboot` e não são
  observação. Uma autodestruição dentro do pod foi tentada e não funcionou: o `runpodctl` da imagem não autoriza com a chave do pod.
- **Viés de transporte** (registrado antes da leitura): os cortes do proxy caem em sessões longas, que são as que falham; refazer troca
  uma sessão longa por um sorteio novo. Na base, 4/17 células refeitas acertaram contra 2/31 nunca cortadas, então a taxa de 12,5 % está
  inflada e a taxa sem corte é ≈ 6,5 %. A conclusão "não é parede" sobrevive: há acerto também no subconjunto nunca cortado.
- **Horários**: quatro vezes escrevi horários estimados errados nos documentos e corrigi cada um; a regra agora é ler o relógio ou o commit.
- **Custo**: triagem ≈ US$23, confirmação ≈ US$68 (inclui as 2 h sem controle e a retomada); saldo RunPod US$212 → US$124,15.

## Status: LIMITE para a pergunta do nó, PROVEITOSO como achado lateral

O A7 morre como desenhado: `no_wall_in_family` na prática, porque o único candidato caiu na confirmação. Fica registrado o que o nó
custou e o que ensinou. Decisões com o Roberto: (i) uma parede real exige outro domínio (Mathlib real ou a fronteira do paper 3) ou outra
família de invariantes, e é caro; (ii) o achado de curadoria estreita contra própria amplia merece uma medida limpa, com o braço curado
completo e um degrau novo por família, e é barato; (iii) o paper separado do A2 ganha esta seção, que é o teste mais duro que fizemos da
consolidação sem curador.
