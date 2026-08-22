# A distância em bits — por que "estimular o modelo" tem teto

*Nota de discussão, Roberto & Claude, 2026-08-20 (noite da Bateria V).
Contexto: dezoito dias de programa creative-machine; paper 1 submetido ao
arXiv; baterias B, S, M, M+ concluídas; V em execução.*

## A pergunta

> "É bem provável que a resposta para vários problemas em aberto esteja
> dentro destes modelos, só não conseguimos estimular da forma correta.
> Concorda?" — Roberto

## A resposta: concordo pela metade

### No sentido fraco, sim

Esses modelos são a compressão de quase todo o conhecimento escrito. Para
problemas cuja solução é uma **recombinação curta de ideias já conhecidas**,
as peças estão lá dentro, e até a montagem está ao alcance — o FunSearch
achou construções matemáticas novas (cap sets) com um modelo pequeno, e os
nossos cadernos de bin packing escreveram centenas de heurísticas plausíveis
em uma noite. Nesse sentido, sim: há respostas "dentro", esperando.

### Mas "estimular da forma correta" é a formulação errada

Estimular é *recuperação*: pressupõe que a resposta existe como item
armazenado e só falta a chave. Um modelo generativo, porém, não é um cofre —
é uma **distribuição de probabilidade**. Nesse sentido trivial, a prova da
hipótese de Riemann "está dentro" de qualquer modelo (tem probabilidade
não-nula), como está dentro de um macaco com máquina de escrever.

A pergunta certa não é "está dentro?". É: **quanta massa de probabilidade o
modelo põe perto da resposta?** — quantos *bits de busca* faltam entre o
prior dele e o alvo.

- Para recombinações próximas, faltam poucos bits: amostragem + verificador
  chegam lá. (É o nicho onde um escritório compete.)
- Para o genuinamente novo, faltam muitos — e nenhum prompt encurta isso,
  porque **o prompt não muda o prior**.

Vimos isso em miniatura o programa inteiro: cada estímulo comprou variação
(interrupção: 3–4× mais candidatos válidos) ou integração (memória
esquemática: recorde no nível do documento), nunca valor; e o conhecimento
do modelo agiu como *atrator* — quanto mais contexto acumulado, mais ele
volta ao conhecido (auto-cópia, entrainment, os poços de degeneração). O
"estímulo certo", nos nossos dados, tem teto: reorganiza a superfície de um
prior fixo.

### A peça que a inferência não tem, estruturalmente

Quem descobre não só busca: **consolida**. Cada resultado intermediário
verificado vira parte permanente de quem busca — o humano dorme e acorda
diferente; o AlphaGo se re-treinava no próprio jogo. Na inferência, o modelo
termina a noite exatamente igual a como começou. O *Accumulate* do DREAM
falhou em todas as versões testadas (contexto verbatim, reset, esquema,
agenda, portão de juiz) porque acumulação de verdade é **atualização de
pesos**, não de contexto.

A versão treinável disso — fine-tune do modelo nos próprios achados
verificados, um "auto-destilar descobertas" — é onde a intuição do "está
dentro, falta estimular" volta a ser verdadeira: aí o estímulo de hoje muda
o que é recuperável amanhã.

## Síntese

As respostas para *alguns* problemas em aberto estão a poucos bits de
distância dentro desses modelos — os problemas **verificáveis e com formato
de recombinação** — e para esses o gargalo não é o estímulo, é o **loop de
busca + verificação** (Bateria V). Para o resto, a resposta não "está
dentro" em nenhum sentido útil: o modelo é o melhor mapa já feito do
território conhecido, e mapa nenhum contém o que ainda não foi pisado — mas
encurta brutalmente a caminhada de quem sabe onde está a fronteira.

O trabalho, do escritório, é: **escolher fronteiras que estejam a poucos
bits — e medir com honestidade quantos bits faltam.**

## Regras práticas que decorrem disso

1. Preferir problemas com **verificador barato** e solução plausivelmente
   recombinatória (bin packing → cap set → desigualdades → limites
   combinatórios), a problemas que exigem conceito novo.
2. Gastar orçamento em **busca + seleção**, não em engenharia de estímulo:
   variação é barata (a interrupção já a multiplica); valor só nasce do
   funil.
3. O próximo salto de capacidade não é um prompt: é **consolidação**
   (treinar no que o verificador aprovou). Se o programa continuar, é para
   lá que ele vai.
4. Evidências que sustentam cada frase acima estão nas baterias do
   `PLANO.md` (B, S, M, M+, gate, V) e no paper 1 — nada aqui é opinião
   solta; onde faltou dado, está dito.

*Referências de ancoragem: FunSearch (Romera-Paredes et al., 2024);
AlphaEvolve (Novikov et al., 2025); Schmidhuber (progresso de compressão
como interesse intrínseco); os resultados do creative-machine (PLANO.md,
2026-08-03 → hoje).*

---

*P.S. (2026-08-20, 21:40) — a Bateria V fechou horas depois desta nota e a
confirmou: o verificador dentro do fluxo não produziu progressão (V1 p =
0,48; V2 na direção oposta), e o fenômeno colateral foi o modelo escrever
~16 vereditos falsos por caderno — imitar o formato da recompensa em vez de
ganhá-la. O prior imita o mundo; não se move por ele. Consolidação continua
sendo o órgão que falta.*

*P.P.S. (2026-08-21, 22:30) — a Bateria C deu ao ensaio seu primeiro
positivo, calibrado: consolidar por LoRA os achados verificados move a
massa dos candidatos em variantes nunca vistas na direção do valor (−1,3 a
−1,5 pp; p = 0,016 no ciclo 2; vs controle aleatório p = 0,035), sem
colapso — e não move o teto (nenhum achado estrito; melhor ≈ best fit). O
prior anda quando se treina no que o mundo aprovou; anda para o
conhecido-bom, não além. Os bits encurtam; a fronteira ainda não.*

*P.P.P.S. (2026-08-22, 06:30) — repulsão ancorada: empurrar para longe dos
poços, com âncora, levou a massa inteira do prior ao melhor atrator
conhecido (100% dos candidatos ≡ best fit) e apagou as caudas onde vivem os
raros "melhores que os clássicos". Mover o mapa é fácil; o que é difícil é
movê-lo sem apagar a fronteira. A próxima pergunta da distância em bits não
é "como puxar", é "como puxar preservando as caudas".*
