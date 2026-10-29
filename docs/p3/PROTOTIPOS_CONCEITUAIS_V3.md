# Programa 3 — dois protótipos conceituais, revisão local v3

Estado: implementados e verificados localmente. **Não é calibração comportamental**,
não há novo resultado de transferência e nenhum piloto principal foi iniciado.
Nenhuma chamada experimental adicional a modelos, AWS ou pods foi feita nesta etapa.

O fechamento v2 mostrou 4/4 sem ponte e 4/4 com oráculo. A resposta nesta etapa foi
alterar a escolha de intermediário exigida pelo problema, preservando o executor e os
resultados antigos. Não aumentamos apenas a quantidade de construtores.

Os dois diretórios em `worlds/prototypes/` são escritos durante o desenvolvimento,
não sorteados. Seus alvos já foram vistos nesta tarefa: **ficam excluídos da amostra
principal e não são os fixtures de uma eventual próxima calibração**.

## 1. Invariante que não vem fornecido

Diretório: `worlds/prototypes/DEV_INVARIANT_V3/`.

A entrada contém estados inteiros `(x, y, z)`, o estado inicial `(2, 1, 1)` e quatro
movimentos. Dois deles são:

```text
(x, y, z) → (x + 2y + z, y + z, z)
(x, y, z) → (x, x + y, x + 2y + z)
```

Os outros dois são os movimentos inversos correspondentes. A base define o que é um
passo e uma sequência finita de passos, mas não fornece uma propriedade preservada.

O alvo visível pergunta se é impossível chegar a qualquer estado `(0, b, c)`. Os dois
irmãos perguntam pela impossibilidade de chegar a `(a, b, -a)` e a `(a, a, a)`.
São famílias infinitas de destinos, não três percursos finitos a expandir.

A ponte-oráculo introduz a quantidade

```text
I(x, y, z) = xz − y²
```

e prova sua conservação em qualquer percurso. No início, `I = 1`. Nos destinos do
alvo visível, `I = −b²`; no primeiro irmão, `I = −a² − b²`; no segundo, `I = 0`.
As três aplicações da ponte fecham por argumentos aritméticos locais.

A escolha intelectual proposta é formular a combinação quadrática antes de fazer
a indução. No gerador anterior, a propriedade a transportar já vinha na entrada;
aqui, indução continua sendo parte da prova, mas não fornece sozinha o enunciado útil.

### O que os diagnósticos realmente estabelecem

- Existem trajetos não vazios, incluindo um movimento seguido do inverso. A base não
  foi construída com hipóteses incompatíveis nem com uma relação sem exemplos.
- Cada propriedade pontual usada nos três alvos tem um contraexemplo à preservação
  por um passo em estados arbitrários. Portanto, a indução que tenta preservar apenas
  essa propriedade, sem informações adicionais sobre alcançabilidade, não fecha.
- Nenhuma combinação linear homogênea não nula `ax + by + cz` é preservada pelos dois
  movimentos apresentados **em todos os estados inteiros**. Isso não exclui invariantes
  de outra forma, restritos aos estados alcançáveis, nem procedimentos de síntese.
- Há um estado alcançável com coordenada `y` negativa: assumir positividade das três
  coordenadas não é uma solução legítima.
- Se o início for alterado para `(1, 1, 1)`, um movimento chega a `(0, 0, 1)`.
  O Lean prova que o alvo visível fica falso nessa mutação e rejeita a prova original.

### Limitação central

O invariante tem a forma de um determinante de uma matriz simétrica. Um modelo pode
reconhecê-lo imediatamente ou sintetizar uma forma quadrática a partir dos movimentos.
Não provamos que esta seja uma escolha difícil, inédita ou a única rota possível.
Uma prova por outra propriedade válida deve ser aceita normalmente.

## 2. Representação que não vem fornecida

Diretório: `worlds/prototypes/DEV_REPRESENTATION_V3/`.

A entrada contém palavras nos símbolos `a` e `b`. A regra permite trocar `aba` por
`bab` dentro de qualquer prefixo e sufixo; também permite reflexividade, simetria e
composição de trocas. Nenhuma interpretação numérica dos símbolos vem na base.

O alvo visível afirma que não se pode transformar

```text
p ++ aabb ++ s    em    p ++ abab ++ s
```

para quaisquer prefixo `p` e sufixo `s`. Os irmãos usam os pares `abba`/`baab` e
`aaabbb`/`ababab`. Em cada par, comprimento e quantidades de cada símbolo coincidem.
Os contextos arbitrários impedem tratar o objetivo geral como uma busca em apenas
duas palavras curtas isoladas.

A ponte interpreta os símbolos como transformações de pares de inteiros:

```text
a(x, y) = (x + y, y)
b(x, y) = (x, y − x)
```

Ela prova que a regra de troca preserva a transformação composta. Também constrói
as inversas para eliminar o prefixo e o sufixo comuns na representação. Os núcleos
de cada par produzem resultados diferentes no ponto `(1, 0)`; isso contradiz uma
suposta sequência de trocas. As três provas finais são aplicações curtas da mesma ponte.

A prova usa apenas uma direção: palavras relacionadas têm a mesma ação. Não afirma
que qualquer igualdade de ações corresponda a uma sequência de trocas, nem que a
representação distinga todas as palavras.

### Diagnóstico de uma representação insuficiente

O arquivo de diagnósticos também constrói uma representação menor, em pares de bits,
substituindo a aritmética por XOR. O Lean verifica que ela respeita a regra de troca.
Ela distingue os **núcleos** do alvo visível, mas identifica os dois núcleos do
primeiro irmão para todos os pares de bits.

Isso documenta uma perda concreta de informação: reconhecer uma representação válida
e suficiente para distinguir um exemplo não garante distinguir os irmãos. O diagnóstico
não é uma sessão propositora nem uma medida causal; não executamos avaliadores com essa
ponte alternativa. O arquivo prova a distinção dos núcleos, não um fechamento completo
do alvo visível com prefixo/sufixo usando a representação de bits.

Outros controles provados: a dinâmica relaciona palavras distintas; comprimento é
preservado, mas não distingue os pares; contagem de `a` não é preservada pela regra.
Uma mutação que acrescenta diretamente a troca `aabb → abab` torna o alvo visível falso;
há prova desse fato e a ponte original deixa de passar.

### Limitação central

A relação `aba = bab` e representações matriciais associadas são estruturas conhecidas.
Este protótipo **não satisfaz uma alegação de problema matemático novo ou prior vazio**.
Nomes neutros, coeficientes trocados ou mudanças de coordenadas não bastariam, por si
sós, para estabelecer novidade estrutural. Também não excluímos rotas por normalização
de palavras ou por outras representações.

## 3. Resultado da revisão local

- Duas pontes e seus seis fechamentos aceitos pelo Lean 4.33.1, sem Mathlib.
- Auditorias transitivas limitadas a `propext`, `Quot.sound` e `Classical.choice`;
  nenhum axioma novo ou `sorryAx` aceito.
- Seis fechamentos recompilados em workspaces limpos com apenas base, um alvo e ponte.
- Dezoito tentativas automáticas sem ponte: `simp`, `grind` e `omega` em cada alvo.
  Nenhuma resolveu; todas falharam por obrigações de prova, não por sintaxe ou timeout.
  O `grind` foi limitado a quatro divisões em casos; as tentativas tinham 200.000
  heartbeats e timeout de compilação de 30 segundos. São sondas fixas, não busca exaustiva.
- Duas mutações com negações dos alvos verificadas e rejeição da prova original.
- Suíte completa: **185 passed, 6 skipped**, incluindo 24 testes novos. Sem inferência
  experimental nesses testes.

Esses resultados são verificações estruturais. V1 e v2 também passaram verificações
locais e tiveram teto comportamental: **falhar em `grind` não demonstra dificuldade
para um modelo**, e passar o oráculo não demonstra utilidade causal.

## 4. Parecer e portão seguinte

Eu priorizaria a revisão do protótipo de representação: ele contém uma distinção
formal explícita entre uma representação válida mas insuficiente e uma representação
que distingue todos os irmãos. O de invariante é um controle conceitualmente mais
simples, com diagnósticos fortes contra a indução pontual e combinações lineares.
Essa prioridade é um parecer de desenho, não um resultado comparativo de modelos.

Antes de qualquer nova bateria paga ainda faltam:

1. Revisão do quanto cada família mede escolha de rota e do quanto mede reconhecimento
   de uma estrutura conhecida. Se não conseguirmos defender essa distinção, revisar
   a família ou limitar explicitamente a pergunta científica.
2. Um gerador de novas instâncias descartáveis e uma revisão dos irmãos. Não usar os
   exemplos já vistos, nem apresentar renomeação como evidência de ausência de prior.
3. Fontes relevante e sham formalmente válidas, pareadas e com adaptação especificada.
   Não foram implementadas aqui; os diagnósticos não as substituem.
4. Novo plano prospectivo com os mundos, hashes, modelo, prompts, orçamento e portão
   congelados antes das chamadas. O gate mantém quatro pares válidos, oráculo ≥3/4,
   baseline ≤2/4 e ganho líquido ≥2/4; não se troca sucesso por economia de tokens.

Propomos no máximo uma próxima bateria pequena após essa revisão. Se novamente não
houver margem de ganho, reavaliar domínio/operacionalização antes de outra rodada,
sem uma sequência automática de ajustes até aparecer contraste. O piloto principal
continua com congelamento e amostra independentes; P3B e o módulo interno continuam
separados e não foram iniciados.

## 5. Reprodução e preservação

```bash
PYTHONPATH=src .venv/bin/python scripts/p3_prototypes.py review
.venv/bin/python -m pytest -q
```

O comando usa o sandbox local apenas como executor do compilador; não inicia um agente
Codex nem importa cliente AWS. São copiados somente fontes permitidas, sem caches
herdados. A revisão não altera os protótipos originais. O subcomando `seal` registra
proveniência uma vez e recusa sobrescrever hashes existentes; isso não equivale a
congelar um protocolo comportamental.

`prototype_review_v3.json` contém a evidência integral da revisão, os hashes dos dois
mundos, hashes do código de revisão e versão do ambiente. É cópia exata de
`runs/p3/prototypes/local_review_v3_final.json`; uma primeira revisão local anterior
ao acréscimo desses hashes de código permanece em `runs/p3/prototypes/`.
Os manifests de cada protótipo cobrem suas nove fontes/configurações e metadados.

O gerador, os executores, os quatro fixtures e os planos congelados v1/v2 não foram
alterados. A comprovação de assinaturas/axiomas reutiliza o verificador existente.
Referência técnica para o papel das táticas e dos verificadores:
[Lean — The grind tactic](https://lean-lang.org/doc/reference/latest/The--grind--tactic/).
