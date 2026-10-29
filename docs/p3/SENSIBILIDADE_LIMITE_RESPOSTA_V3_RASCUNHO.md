# Sensibilidade ao limite por resposta — proposta posterior à calibração v3

**RASCUNHO REVISÁVEL — NÃO CONGELADO — NÃO EXECUTADO — 05/09/2026.**

Motivação explicitamente pós-resultado: a v3 passou seu portão (1/4 versus 4/4), mas
três baselines terminaram na primeira resposta de 8.192 tokens, sem submissão. A
pergunta seguinte é se a vantagem da ponte persiste quando o limite por resposta
deixa de encerrar tão cedo essas sessões. O objetivo não é obter um novo resultado
favorável nem alterar o desfecho já registrado.

## Contraste proposto

Usar os **mesmos dois fixtures de calibração**, já expostos e inelegíveis para principal,
sem seleção de casos por fracasso. Dois irmãos por mundo × ponte ausente/oráculo ×
teto por resposta de 8.192/16.384 tokens: **16 sessões novas**. A condição de 8.192
também é reexecutada como parte deste novo desenho, evitando comparar apenas uma
nova rodada favorável com uma baseline histórica. Uma sessão por combinação ainda
é diagnóstico pequeno; não sustenta inferência populacional.

Mesmo modelo, esforço, fonte dos arquivos e contrato de prova. Manter limites totais
por sessão: 200 mil tokens de entrada, 20 mil de saída, 12 requisições, 600 segundos.
Manter encerramento se não houver ferramenta; não adicionar um incentivo "continue"
somente aos fracassos. Alterar apenas o limite por resposta dentro da comparação.

Há uma adequação operacional a revisar **antes** de congelar: 8.192 tokens de saída
levaram cerca de 91–104 s nas três sessões truncadas; o timeout de 120 s por requisição
da v3 poderia interromper respostas de 16.384 tokens. A proposta é usar 300 s por
requisição **nos dois braços de limite**, mantendo 600 s por sessão. Isso significa
que a comparação causal relevante será interna ao novo desenho, não entre v3 e a
sensibilidade. A viabilidade desse ajuste precisa de validação local do invólucro;
nenhum teste pago de parâmetros foi iniciado.

## Regras a fixar antes da inferência

- Novo ID e diretório, código separado dos freezes anteriores, entradas, células,
  ordem sorteada, versões, preços e código integralmente commitados antes das chamadas.
- Mesma política de axiomas, isolamento, orçamento diário e limite de concorrência 2.
- Todos os 16 resultados preservados. Nenhum rerun seletivo, fallback, continuação
  ad hoc, relaxamento do verificador ou troca de mundo depois de observar saídas.
- Desfecho primário: quatro pares completos em **cada** limite; relatar baseline,
  oráculo e ganho separadamente. Não juntar os oito pares para fingir mais mundos.
- Para chamar o instrumento de robusto a essa alteração, exigir em ambos os limites
  O≥3/4, baseline≤2/4, ganho≥2/4, além dos quatro pares válidos em cada um.
- Falhas de infraestrutura deixam o diagnóstico incompleto; não viram provas fracassadas.
- Desfechos secundários descritivos: `max_tokens` sem ferramenta, submissões, tokens,
  tempo e custo. Não substituem solução como desfecho primário.

## Decisões possíveis

Se o contraste persistir em ambos os limites, o instrumento ganha suporte operacional
para um próximo desenho de transferência de fontes — ainda não para alegar invenção,
novidade estrutural ou ausência de prior. Novos mundos e a elegibilidade do principal
exigem decisão própria; estes fixtures continuam descartáveis.

Se aumentar o limite eliminar o contraste por elevar a baseline, preservar a leitura
de que a ponte comprime o trabalho sob restrição. Não continuar ajustando limites ou
selecionando alvos para recuperar uma diferença binária; reavaliar o desfecho e o
domínio antes de avançar a transferência como hipótese confirmatória.

Se o braço de 8.192 não reproduzir a margem, registrar instabilidade; se houver
falhas de infraestrutura, diagnosticar sem substituir dados. Esses casos não autorizam
um piloto principal por conveniência nem um terceiro valor de limite pós-hoc.

## Orçamento proposto e estado operacional

Com os mesmos tetos cumulativos e tarifas congeladas usadas na v3, 16 sessões têm
reserva nominal de tokens de US$26,40. Propõe-se teto operacional de **US$30**, dentro
do limite diário de US$150, descontando gastos/reservas anteriores e conciliando
consumo conhecido de outros agentes. Não foi feita reserva nem chamada dessa rodada.
Revalidar preços e saldo antes de executar; estimativa não inclui impostos ou acordos
comerciais. Aumento do teto por resposta não amplia o teto cumulativo de saída.

Esta proposta não modifica o pré-registro principal, não é uma nova calibração de
mundos e não autoriza execução por estar escrita. O próximo trabalho é revisão e
congelamento deste diagnóstico separado, não a repetição da v3.
