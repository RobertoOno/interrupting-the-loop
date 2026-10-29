# Programa 3 — fontes e gerador conceitual v3

Estado: implementação e revisão **locais**, após os protótipos. Não é uma terceira
calibração comportamental. Não houve chamadas experimentais a modelos, AWS ou pods,
e não há novo resultado de utilidade causal. Os executores e registros v1/v2 e os dois
protótipos anteriores foram preservados.

## Decisão de escopo

As duas famílias continuam sendo candidatas para testar o **instrumento de transferência**,
não evidência de invenção ou de ausência de conhecimento prévio. O gerador agora produz
novas instâncias por semente, mas não novas estruturas matemáticas. Ele só emite pacotes
`DEVELOPMENT_ONLY`, inelegíveis tanto para calibração quanto para a amostra principal.

Não se alterou silenciosamente a exigência de novidade do pré-registro principal. Antes
de uma nova bateria, é necessário explicitar que o gate testa se fornecer a ponte muda
a solução, mesmo podendo haver reconhecimento de uma família conhecida. Uma eventual
aprovação desse gate não validará a alegação mais forte de rota fora do prior.

## 1. Revisão de reconhecimento e atalhos

No invariante, `xz − y²` é um determinante de matriz simétrica. A própria escolha da classe
de formas quadráticas abre uma rota de síntese algébrica: encontrar coeficientes cujas
equações de preservação se anulem. A literatura contém métodos de geração de invariantes
polinomiais via álgebra linear, sob hipóteses e limites de grau específicos. Isso sustenta
o risco de síntese conhecida; não é uma medição de que um modelo empregou esse método nem
uma aplicação automática do teorema do artigo a este programa. Referência:
[de Oliveira, Bensalem e Prevosto, Polynomial invariants by linear algebra](https://arxiv.org/abs/1611.07726).

Na representação, `aba = bab` é a relação clássica de tranças em dois geradores;
representações e métodos de normalização dessa família são conhecidos. Nossa relação em
palavras positivas e nossa prova de preservação não estabelecem fidelidade de representação
nem uma solução geral do problema de palavras. O vínculo com essa literatura é um motivo
para cautela quanto ao prior, não evidência de invenção. Referência:
[Birman e Brendle, Braids: A Survey, §§1.2 e 4](https://www.math.columbia.edu/~jb/Handbook-21.pdf).

Mudanças de nomes ou coordenadas não resolvem esses riscos. Também não aumentamos
arbitrariamente o coeficiente dos movimentos: substituir o cisalhamento unitário por
um passo `k` faria `x' − x` múltiplo de `k`, introduzindo conservação de `x mod k`.
Por exemplo, para `k = 3`, o início decodificado `x = n² + 1` nunca é zero módulo 3,
oferecendo uma rota modular direta contra `x = 0`. Esse candidato não foi implementado
nem submetido a modelos; foi descartado por inspeção algébrica.

## 2. O que varia no gerador

Código separado: `conceptual_generator.py`, versão 0.1.0; interface repo-local
`scripts/p3_conceptual.py`. Lean 4.33.1 e somente os três axiomas padrão já permitidos
em v2. Não há cliente de inferência nesse caminho.

**Invariante.** Sorteia `n` entre 3 e 9 e três deslocamentos inteiros não nulos entre
−5 e 5. As coordenadas decodificadas são `X=x−ox`, `Y=y−oy`, `Z=z−oz`. O início é
`(n²+1,n,1)` nessas coordenadas; os quatro movimentos unitários e os três alvos são
transportados pela mesma mudança afim. A quantidade preservada permanece `XZ−Y²=1`.
Essa variação não elimina equivalência de problemas por mudança de coordenadas.

**Representação.** Mantém a relação conhecida e sorteia novos pares de palavras com
comprimentos 6, 6 e 8. Em cada par, comprimento e contagens coincidem, não há prefixo
ou sufixo comum não vazio, e a ação inteira distingue os núcleos em `(1,0)`. O primeiro
par é distinguido pela ação de bits em `(true,false)`; o segundo tem a mesma ação em
todos os quatro pares de bits. O terceiro só exige distinção inteira.

O filtro exclui os pares dos protótipos e das fontes e evita repetições entre os três
alvos sob troca de símbolos, reversão de palavras, ordem do par e remoção de contexto
comum. É um filtro de equivalência **literal**, não um decisor de equivalência algébrica.
As restrições são verificações estruturais anteriores a qualquer resultado de modelo.
O tamanho do conjunto de candidatos de cada estrato fica nos metadados; não é uma
estimativa de quantidade de rotas independentes.

Os fixtures persistidos são `DEV3_I_43BE3D3CA20476F1` e
`DEV3_R_CD4DC332561F4980`, em `worlds/development/`. Seu manifesto cobre todos os
arquivos e metadados. A leitura exige correspondência exata com o gerador e assets
registrados, além dos hashes; não é possível simplesmente apagar auditorias dos
metadados e recalcular um manifesto para fazê-los passar.

## 3. Fontes e controle sham

Cada fonte é um problema independente completo em Lean, com definições, uma ponte e
uma solução. O arquivo Markdown entregue ao propositor contém exatamente o código
verificado, sem os comandos de auditoria. Ambos os braços usam o mesmo cabeçalho
neutro; o payload não traz o rótulo relevante/sham, o namespace do alvo nem os irmãos.

No invariante, a fonte relevante usa coordenadas permutadas e preserva uma forma
quadrática. O sham usa quatro movimentos reversíveis que preservam uma soma linear.
Ambos ensinam conservação, indução sobre percursos e uma impossibilidade aritmética;
só a relevante fornece a forma quadrática compatível com os movimentos do alvo.
As fontes têm três teoremas cada, com 307 e 311 palavras no payload (diferença 1,29%).

Na representação, a relevante resolve outro par de palavras usando uma ação inteira
com coordenadas trocadas. O sham resolve um problema de **comutação** por translações
de pares inteiros. Ambos mostram inversas, composição de ações e cancelamento de
contextos; diferem na lei que a representação respeita e no que ela distingue.
As fontes têm nove teoremas cada, com 628 e 624 palavras (diferença 0,64%).

Este pareamento é em palavras, número de teoremas e formato. Não medimos igualdade de
tokens no tokenizer do modelo, dificuldade cognitiva ou toda a quantidade de informação.
A contagem efetiva de tokens e sua tolerância devem ser resolvidas antes de qualquer
experimento D/C2. A próxima calibração de oráculo não inclui propositores D/C2.

### Adaptação verificável, não oráculo rebatizado

O adaptador extrai os corpos das definições e provas da fonte; remove o problema-fonte
e sua solução; aplica apenas o mapa registrado:

- Invariante: `(source.u, source.v, source.w) = (Z, X, Y)`, com a decodificação afim.
- Representação: `l → a`, `r → b`, preservando a ação de coordenadas trocadas da fonte.

As duas adaptações relevantes compilam contra a base do alvo e fecham os três alvos.
Também são recompiladas em seis workspaces limpos, sem qualquer arquivo-fonte ou
outro alvo. A ponte-oráculo original é verificada separadamente nos mesmos seis
contratos de saída. A solução local adaptada pode ser escrita pelo desenvolvedor:
isso demonstra aplicabilidade do mapa, **não** que um propositor o descobrirá.

As duas adaptações sham falham por obrigações de prova, não por sintaxe ou timeout.
Além dessa rejeição, o Lean prova incompatibilidade concreta: a soma transplantada
muda em um passo do alvo de invariante; as translações dão ações diferentes a `aba`
e `bab` no alvo de representação. Neste último, também prova que essas translações
identificam cada par de núcleos para qualquer ponto inteiro.

O sham não é “ausência de toda ideia útil”: ele ainda fornece prática genérica de
invariantes ou representações. O contraste proposto é a **estrutura adicional que se
alinha ao alvo**, além desse ensino compartilhado. A possibilidade de um agente
extrair outra rota do sham permanece aberta. A representação de bits continua sendo
diagnóstico auxiliar e não foi reclassificada como fonte sham.

## 4. Verificação local

A evidência integral está em `conceptual_sources_review_v3.json`, cópia exata de
`runs/p3/conceptual/local_review_v3.json`. Ela contém versões e hashes do código,
assets, manifests dos mundos, saídas de compilação e auditorias:

- Quatro fontes corretas em seus próprios mundos, com auditoria de todos os teoremas.
- Seis fechamentos pelo oráculo e seis pela adaptação relevante, em workspaces limpos.
- Duas adaptações sham rejeitadas e contraexemplos de compatibilidade provados.
- Dezoito sondas fixas sem ponte (`simp`, `grind`, `omega`): nenhuma resolveu;
  todas terminaram por obrigações de prova, sem timeout ou erro de sintaxe.
- Duas mutações tornam o alvo visível falso: o Lean verifica a negação e rejeita o
  oráculo original. Há dinâmica não vazia e não trivial nos dois pacotes.
- Testes de geração determinística, fontes/payloads, isolamento, hashes, recusa de
  sobrescrita e de revalidação por metadados manipulados. Outra semente por família
  também passa a compilação das fontes, pontes e fechamentos.

As sondas continuam com 200.000 heartbeats, 30 segundos por compilação e `grind`
limitado a quatro divisões em casos. Falhar nessas sondas não demonstra dificuldade
para modelos. O compilador roda em sandbox local sem rede; isso não abre sessões de
agentes Codex. O pré-registro antigo ainda passa `scripts/p3_bedrock.py validate`.

Suíte completa após esta etapa: **219 passed, 6 skipped**, incluindo 34 testes novos;
102,47 segundos nesta execução. A materialização D0/D/C2 foi testada quanto ao
isolamento, não executada com propositores. O verificador histórico de propositores
tem política zero-axiomas por padrão: a integração futura precisará explicitar a
allowlist padrão atual em uma versão própria, sem modificar os registros congelados.

## 5. Antes da próxima chamada paga

1. Confirmar o recorte: uma última calibração pequena do instrumento em famílias
   conhecidas, sem atribuir novidade de rota a um eventual contraste.
2. Preparar fixtures próprios de calibração, registrando a exclusão dos protótipos,
   destes pacotes e das instâncias geradas nos testes. O inventário de sementes está
   em `development_exclusions_v3.json`; excluir só o nome do diretório ou trocar a
   semente não basta quando os problemas coincidem. A versão atual não habilita
   calibração; será necessária uma preparação prospectiva separada. Não há garantia
   de que os pequenos estratos atuais sejam suficientes após todas as exclusões.
3. Fixar os novos fixtures, hashes, prompts, modelo, limites e ordem em um commit
   **anterior** à inferência; comunicar a estimativa e o teto de custo antes de usar.
4. Rodar somente o gate de quatro pares válidos: oráculo ≥3/4, baseline ≤2/4 e ganho
   líquido ≥2/4. Sem propositores ou amostra principal antes de passar.
5. Se não houver contraste nessa próxima pequena bateria, reavaliar o domínio ou a
   operacionalização. Não enfraquecer o modelo nem continuar ajustando até dar efeito.

P3B e o módulo de mecanismos internos permanecem separados e não começaram. Uma
calibração que passe só valida a manipulação nesse recorte; não satisfaz automaticamente
a exigência mais forte de novidade do programa principal.

## Reprodução

```bash
PYTHONPATH=src .venv/bin/python scripts/p3_conceptual.py review
.venv/bin/python -m pytest -q tests/test_p3_conceptual.py
.venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/python scripts/p3_bedrock.py validate
```

`generate --family ... --seed ... --destination ...` cria somente um diretório novo;
não reescreve fixtures. A reprodução byte a byte exige esta revisão do código e dos
assets. Revisões futuras precisam manter essa proveniência e seus próprios resultados.
