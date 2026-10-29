# S16 — sensibilidade ao limite de resposta do P3/Claude

08/09/2026 UTC. Protocolo prospectivo da pendência proposta em 05/09;
retomada após Roberto confirmar seguir a sequência de robustez, produção,
transferência e replicação antes de priorizar mecanismos. Preserva o
rascunho e a calibração v3 encerrada. Não é nova amostra principal.

## Pergunta e comparação

A vantagem da ponte observada na v3 resiste a um limite maior por resposta?
Mesmos dois mundos expostos e seus dois irmãos; com/sem oráculo em cada um;
limites 8.192/16.384 tokens: 16 sessões novas. Nenhuma baseline histórica
substitui a nova condição de 8.192. Não há repetição seletiva das três falhas.

Mesmo `anthropic.claude-opus-5`, AWS `main-account`, região `us-east-1`,
effort high, prompt, ferramenta única e política Lean. Até 20 mil tokens
de saída, 200 mil de entrada, 12 requisições e 600 s por sessão em ambos
os limites. Timeout por requisição de 300 s em ambos, limitado pelo tempo
restante da sessão; contagem de tokens até 30 s. A comparação causal é
interna a S16, não uma comparação direta com o timeout de 120 s da v3.
Sem ferramenta, a sessão termina; sem continuação extra para fracassos.

Novas sessões podem revisar provas após rejeição pelo mesmo contrato
histórico. Primeira prova validada encerra, sem requisição adicional.
O limite restante cumulativo de saída pode reduzir o máximo em requisições
posteriores, igualmente nos dois regimes. Todos os limites são registrados.

## Congelamento e controles

Plano `response_limit_sensitivity_plan_v1.json`; ID exclusivo
`p3a_response_limit_sensitivity_v1`. As 16 células e hashes das entradas são
derivados da matriz v3 integral. Ordem embaralhada com semente 2026090801,
fixada antes de qualquer resposta S16. Concorrência máxima dois; não se
promete ordem de conclusão. Estado e cache locais não passam entre sessões.

Materialização de cada entrada precisa coincidir com seu hash histórico.
Preflight das 16 células exige Lean funcional, leitura externa negada e
rede negada. O modelo recebe somente os arquivos permitidos; compilação
ocorre na sandbox, sem cache de provas herdado. Código, testes, protocolo,
preços, mundo e plano precisam estar publicados antes da primeira chamada.

Executor do modelo/verificador históricos permanecem byte-idênticos. Arquivos
novos coordenam apenas a matriz, os dois configs, o agregado e o diário.
Validação recusa alterações de ambiente, fontes, preços, parâmetros, células
ou ordem. Diretório e ID são fixos: execução iniciada ou arquivo publicado
impede relançamento. Nenhum parâmetro de diretório habilita outra tentativa.
O lançador fixa intenção exclusiva antes de criar o processo separado da
conversa, preservando log/PID. Intenção sem confirmação é ambígua, nunca
permissão para repetir. Não invocar o modo interno do worker manualmente.

## Desfecho e decisões

Quatro pares completos em cada limite; O >=3/4, baseline <=2/4 e ganho >=2/4.
Robustez a esta alteração exige esses critérios nos DOIS limites. Dois
mundos e irmãos dependentes, uma sessão por célula: não oito mundos, teste
populacional, equivalência ou demonstração de ausência de prior.

Precedência: lote incompleto/falha técnica pede diagnóstico; critério baixo
não reproduzido pede revisão antes da principal; ambos passam permitem
preparar transferência, ainda sem admissão automática da principal; apenas
baixo passa significa contraste não robusto ao limite testado. Não escolher
terceiro limite ou novos casos para recuperar diferença. Se a baseline
melhorar com mais espaço, considerar compressão de trabalho sob restrição
como interpretação delimitada, não prova de incapacidade de achar a rota.

Todas as falhas matemáticas, de protocolo e de orçamento/tempo de sessão
permanecem nos denominadores. Falha de infraestrutura interrompe novas
admissões; sessões já em andamento encerram normalmente e são preservadas.
Sessões não iniciadas ficam explícitas; nenhuma reposição ou retry. Uso
incerto mantém a reserva integral até conciliação, nunca é tratado como zero.
Tokens/tempo são secundários descritivos, não substitutos pós-resultado.

## Orçamento e sequência

Reserva nominal integral US$26,40, teto operacional US$30 dentro do limite
Claude/AWS de US$150/dia, com diário cumulativo e reservas que não expiram à
meia-noite. Reconciliar o diário e consumo externo conhecido antes de admitir.
Consulta de faturamento atrasada não demonstra consumo externo zero.
Não é autorização para recarga/compra nem alteração do orçamento RunPod.

Tarifas conferidas em 08/09: Opus 5 US$5/25 por milhão de tokens de entrada/
saída, mais 10% regional; guardas conservam US$5,50/27,50. Fontes oficiais:
[preços](https://platform.claude.com/docs/en/about-claude/pricing) e
[Bedrock regional](https://platform.claude.com/docs/en/build-with-claude/claude-in-amazon-bedrock).
Estimativa de uso, sem impostos/acordos privados, não fatura final.

Após execução: recuperar todas as respostas/provas, verificar hashes,
reconstruir contabilidade e escores e revalidar provas em workspaces novos.
Só depois aplicar a decisão. Produção/transferência, replicação, P3B e
mecanismos mantêm critérios próprios; resultado Qwen não substitui S16,
e resultado Claude não valida mecanismos em outro checkpoint.
