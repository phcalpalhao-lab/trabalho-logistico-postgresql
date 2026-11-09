# Demonstracao reproduzivel V1 — execucao manual concluida no cenario relatado

Esta rota cria um banco novo e separado, `projeto_logistico_demo_v1`, sem
backup privado. Todos os dados sao **sinteticos**: nenhum cliente, pedido,
pagamento ou entrega representa pessoa, operacao ou resultado real.

**Situacao.** Em 09/11/2026 o autor executou a rota manualmente no cenario
descrito em [Evidencia da execucao manual](#evidencia-da-execucao-manual-relatada).
Essa evidencia e o relato das saidas fornecidas pelo autor; **nao ha logs
preservados**. As instrucoes abaixo sao o roteiro reproduzivel; ainda nao houve
reexecucao independente por outra pessoa.

**Delimitacao.** Esta V1 se refere somente a demonstracao no banco
`projeto_logistico_demo_v1`. O historico anterior do projeto, com outros bancos
e uma etapa classificada como `ANOMALY`, permanece no projeto original, nao faz
parte desta distribuicao e nao foi alterado. Esta execucao nao o comprova nem o
substitui.

## Origem e escolhas

- Alvo: PostgreSQL e `psql` **18**, banco UTF-8 (a execucao relatada usou
  PostgreSQL 18.6). Nao ha garantia de compatibilidade com outras versoes. O
  servidor e conferido pelo primeiro arquivo; confirme tambem a versao do
  cliente.
- O esquema e a [proposta PostgreSQL revisada](../../docs/ddl_historico/propostas/trabalho_logistico_postgresql_REVISAO_OFFLINE_NAO_EXECUTAR.sql),
  que o roteiro `00_schema.sql` inclui por `\ir`. O DDL traz no cabecalho o
  aviso «nao executar sem plano e autorizacao especificos»; nesta V1 ele e
  executado somente por `00_schema.sql`, em banco novo e separado, depois das
  verificacoes de preflight do proprio roteiro. Foi derivado de um DDL PostgreSQL
  adaptado do Oracle por remocao de cinco modificadores `BYTE` em
  `VARCHAR(n BYTE)`, preservando tipos, tamanhos, nomes e o espaco final em
  `'RODOVIARIO '`. Descreve 20 tabelas, 140 colunas, 20 PKs, 21 FKs e um CHECK.
  Nao demonstra o esquema de nenhum outro banco.
- O [manifesto](../../generated_data/full_20261008_1724/manifest.json) registra
  10.000 linhas novas e quatro IDs 1 no snapshot-base. Os CSVs tem, por exemplo,
  estoque e inventario que referenciam o armazem 1, produtos que referenciam a
  categoria 1 e compras que referenciam o fornecedor 1; essas linhas nao estao
  nos respectivos CSVs. A pesquisa por pedidos que referenciam cliente 1 nao
  encontrou ocorrencia; mesmo assim a rota inclui o cliente 1 para preservar o
  baseline e as contagens do perfil completo.
- `01_baseline.sql` cria quatro registros **novos e ficticios**, IDs 1 de
  armazem, categoria, cliente e fornecedor. Seus campos sao apenas os
  necessarios para satisfazer a estrutura e identificar a demonstracao. Nao
  reproduzem registros de execucoes anteriores do projeto, e resultados que
  dependam desses pais nao devem ser comparados com os de outras bases.
- `02_load.sql` usa os 20 CSVs de
  [full_20261008_1724_ascii](../../generated_data/full_20261008_1724_ascii).
  Os nomes fisicos ASCII evitam a ocorrencia acentuada no nome do arquivo de
  movimentos; identificadores e dados continuam UTF-8. A carga usa colunas
  explicitas em ordem de dependencia, PK/FK/CHECK ativos e `FORCE_NULL` em
  `data_entrega`. `HEADER true` descarta o cabecalho, mas nao o valida: a
  conferencia dos cabecalhos e hashes abaixo e obrigatoria antes da carga.

## Pre-requisitos e seguranca

1. Revisar todos os arquivos desta rota. Usar uma copia deste repositorio com os
   dois diretorios de CSVs e o manifesto.
2. Ter PostgreSQL 18 e Python 3.13 no Windows; a verificacao offline usa
   biblioteca padrao e modulos deste repositorio. No computador do autor, os
   clientes ficam fora do `PATH` e foram consultados com `--version`:
   - `C:\Program Files\PostgreSQL\18\bin\psql.exe` — `psql (PostgreSQL) 18.6`;
   - `C:\Program Files\PostgreSQL\18\bin\createdb.exe` — `createdb (PostgreSQL) 18.6`.
   Ajuste os caminhos a sua instalacao.
3. Ter um servidor de demonstracao separado e uma conta com permissao para
   criar um banco e objetos em seu schema `public`. A execucao relatada usou a
   conta `postgres` e o servidor `::1`, porta 5432; os comandos abaixo usam
   esses valores. Confirme que o endpoint e a conta sao os escolhidos antes de
   qualquer escrita; ajustes exigem revisao dos comandos. Nao registre senhas
   em arquivos ou comandos: use `-W` e digite a senha apenas no prompt.
4. Confirmar previamente que o nome `projeto_logistico_demo_v1` nao existe nesse
   servidor. A criacao falha se ele ja existir; **nao apague, restaure nem
   reutilize um banco preexistente** para contornar isso. A retomada apos
   rollback do banco criado nesta propria tentativa e tratada separadamente
   abaixo.
5. Trabalhar sem acesso concorrente ao banco de demonstracao e usar uma sessao
   psql nova. A checagem de nome, versao, objetos e transacao nao autentica
   identidade do servidor nem constitui controle de autorizacao.

O nome exato do banco e obrigatorio em cada etapa. O preflight recusa schemas,
relacoes, rotinas, tipos e outros objetos previstos no arquivo; a etapa de
baseline tambem exige 20 tabelas vazias e bloqueia concorrencia sobre elas
durante a transacao. Qualquer divergencia significa parar, nao limpar o banco.
Essas verificacoes nao substituem a confirmacao humana do endpoint e do ambiente.

## Sequencia reproduzivel no Windows

Abra PowerShell na **raiz do repositorio**, em um caminho conferido pelo
operador, e mantenha essa pasta como diretorio corrente do `psql`. Os
`\copy` usam caminhos relativos a essa raiz; `\ir` no arquivo de esquema
localiza o DDL relativo ao proprio arquivo. Os comandos abaixo sao o roteiro
reproduzivel; o que o autor relatou fica na secao de evidencia.

Primeiro, somente leitura offline, com os CSVs e o manifesto desta copia:

```powershell
python --version
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' --version
& 'C:\Program Files\PostgreSQL\18\bin\createdb.exe' --version
python -I -S -B scripts\verify_pilot_artifacts.py --profile full --output generated_data\full_20261008_1724 --ascii-output generated_data\full_20261008_1724_ascii
```

Prosseguir apenas se o verificador terminar com codigo de saida 0 e imprimir
`FULL_ARTIFACTS_OK: 20 CSVs, 10000 rows, 20 SHA-256 hashes.` Essa verificacao
cobre manifesto, hashes, cabecalhos, tipos e as copias ASCII; nao envolve o
banco.

Consultar o servidor administrativo escolhido, com permissao de conexao ao
banco `postgres` (a senha e pedida no prompt por `-W`):

```powershell
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -X -W -v ON_ERROR_STOP=1 -h ::1 -p 5432 -U postgres -d postgres -c "SELECT current_user, inet_server_addr(), inet_server_port(), current_setting('server_version'), current_setting('server_encoding');"
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -X -W -v ON_ERROR_STOP=1 -h ::1 -p 5432 -U postgres -d postgres -c "SELECT datname FROM pg_database WHERE datname = 'projeto_logistico_demo_v1';"
```

Confirmar os dois codigos de saida, identidade/endpoint e versao do servidor;
a segunda consulta deve retornar zero linhas. Essas consultas nao garantem que
outro processo nao crie o nome em seguida; o resultado da criacao tambem deve
ser conferido. Depois de confirmar permissoes e obter autorizacao para criar o
banco, a execucao relatada usou este comando SQL (no banco `postgres`):

```sql
CREATE DATABASE projeto_logistico_demo_v1
    WITH OWNER = postgres
         TEMPLATE = template0
         ENCODING = 'UTF8';
```

O `createdb.exe` com `-T template0 -E UTF8` seria uma alternativa equivalente
por linha de comando, mas **nao foi o meio relatado nem foi executado**.
Prosseguir apenas se a criacao terminar sem erro. Na mesma pasta, em uma
**nova sessao** psql:

```powershell
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -X -W -v ON_ERROR_STOP=1 -h ::1 -p 5432 -U postgres -d projeto_logistico_demo_v1
```

No prompt dessa sessao, verificar a conexao e o servidor antes dos arquivos:

```text
SELECT current_database(), current_user, inet_server_addr(), inet_server_port(), current_setting('server_version'), current_setting('server_encoding');
\i 'demo\\v1\\00_schema.sql'
\i 'demo\\v1\\01_baseline.sql'
\i 'demo\\v1\\02_load.sql'
\i 'demo\\v1\\03_validate.sql'
```

O relato do autor nao detalha a forma exata de cada linha digitada; se o
`psql` rejeitar a sintaxe de caminho acima, interrompa e corrija o roteiro, sem
alterar os SQL.

Executar cada linha somente se a anterior terminou sem erro. `00_schema.sql`
inicia uma transacao; as demais etapas devem ocorrer na **mesma sessao**, sem
`COMMIT` intermediario. A validacao termina com uma mensagem e deixa a transacao
aberta. Depois de conferir os criterios abaixo, a decisao explicita de aceitar
a demonstracao e:

```sql
COMMIT;
```

Se qualquer passo falhar, for interrompido ou produzir resultado inesperado,
na mesma sessao execute `ROLLBACK;` e pare. Se a sessao tiver sido encerrada,
o PostgreSQL desfaz a transacao nao confirmada. Nao execute `COMMIT` para
contornar erro. Uma tentativa posterior deve comecar numa sessao nova, apos
verificar que o banco separado continua vazio; nao use limpeza destrutiva.

## Criterios de aceite (roteiro)

`03_validate.sql` deve terminar sem excecao e informar 10.004 linhas: os
10.000 CSVs mais os quatro registros sinteticos acima. A tabela abaixo mostra
contagens finais; as faixas de IDs esperadas sao de 1 ate a respectiva contagem.

| Tabela | Linhas | Tabela | Linhas |
|---|---:|---|---:|
| armazem | 5 | avaria | 40 |
| categoria | 20 | clientes | 1.000 |
| compra | 200 | devolucao | 60 |
| entrega | 800 | estoque | 400 |
| fornecedor | 30 | historico_entrega | 1.700 |
| inventario | 60 | item_compra | 400 |
| item_devolucao | 90 | item_inventario | 400 |
| item_pedido | 1.750 | movimentação_estoque | 1.000 |
| pagamento | 840 | pedidos | 900 |
| produto | 300 | transportadora | 9 |

O arquivo `03_validate.sql` verifica contagens/faixas, 140 colunas, 20 PKs, 21 FKs
validadas e sem orfaos e um CHECK; totais de pedidos e compras; pagamentos e as
regras de entrega apos pagamento integral e de pedido concluido (identificadas
como RN-012 e RN-014 nas mensagens do script); datas, estado e historico de
entregas; regras de devolucao e teto de reembolso (RN-028 e RN-029);
saldo/reserva, movimentos, itens de inventario e pareamento de avarias.
Essas verificacoes se aplicam ao **conjunto carregado**; o arquivo nao e uma
auditoria exaustiva e nao reproduz os criterios de outras execucoes.
Uma excecao e falha, nao sucesso parcial. As constraints permanecem ativas;
erros de `\copy`, PK, FK, CHECK, tipo ou nulabilidade tambem interrompem a carga.

## Evidencia da execucao manual relatada

Em 09/11/2026 o autor executou manualmente a rota e forneceu as saidas das
quais estes dados foram transcritos. Nao ha log, captura ou arquivo de saida
preservado que permita conferencia independente.

| Item | Relato |
|---|---|
| Banco | `projeto_logistico_demo_v1`, criado pelo autor (comando SQL acima) |
| Conexao | usuario `postgres`, servidor `::1`, porta 5432 |
| Servidor | PostgreSQL 18.6; banco em UTF8 |
| `00_schema.sql` | executado, sem erro relatado |
| `01_baseline.sql` | quatro registros ficticios inseridos |
| `02_load.sql` | vinte operacoes `COPY`, somando 10.000 registros |
| `03_validate.sql` | contagens e verificacoes concluidas; mensagem final de validacao e retorno `DO` |
| Confirmacao | `COMMIT;` executado, resposta `COMMIT` |
| Resultado | 10.004 linhas no cenario executado (10.000 CSVs + 4 ficticias) |

Alcance: essa execucao comprova, segundo o relato, somente a rota desta V1 no
banco de demonstracao. Nao comprova nenhuma execucao anterior do projeto e nao
altera o historico original. As verificacoes de `03_validate.sql` examinam os
dados carregados; nao sao triggers e nao impedem alteracoes invalidas futuras.

## Consulta financeira/logistica

[04_pedidos_pagamentos_entregas.sql](04_pedidos_pagamentos_entregas.sql) e uma
consulta somente de leitura, em transacao `READ ONLY` encerrada por `ROLLBACK`.
Ela agrega pagamentos e entregas separadamente por pedido, antes de
juntar a `public.t_pedidos`, para nao multiplicar valores, e preserva pedidos
sem pagamentos ou entregas. Reproducao, em uma sessao nova, a partir da raiz:

```powershell
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -X -W -v ON_ERROR_STOP=1 -h ::1 -p 5432 -U postgres -d projeto_logistico_demo_v1 -f demo\v1\04_pedidos_pagamentos_entregas.sql
```

Definicoes (todos os valores sao sinteticos):

- `valor_aprovado_registrado`: soma de `valor_pago` dos pagamentos com
  `status_pagamento = 'APROVADO'`. E um valor **registrado** no conjunto
  sintetico, nao liquidacao bancaria nem resultado financeiro real.
- `tentativas_pendentes` e `tentativas_recusadas`: **quantidade de registros de
  pagamento** `PENDENTE` e `RECUSADO`, contados em separado e nunca somados ao
  valor aprovado. Nao sao quantidade de pedidos.
- `situacao_pagamento`, nesta ordem: aprovado maior que o total do pedido,
  `ACIMA_DO_TOTAL`; igual, `QUITADO`; maior que zero, `PARCIAL`; demais casos,
  `SEM_APROVACAO`.
- `pedidos_com_entrega`: **pedidos** com ao menos um registro de entrega, nao a
  quantidade de registros de entrega (a tabela tem 800 registros).
- `pedidos_com_todas_entregas_concluidas`: pedidos com ao menos uma entrega e
  todas com status `ENTREGUE`.
- `pedidos_concluidos`: pedidos com `status_pedidos = 'CONCLUIDO'`.

### Reproducao da consulta 04

Depois do `COMMIT` da carga, o autor executou manualmente o arquivo salvo
`04_pedidos_pagamentos_entregas.sql` e relatou que ele **reproduziu os tres
grupos e todos os valores** do CSV abaixo. Esse relato e a unica evidencia
dessa execucao: nao ha horario, duracao, hash ou log preservados.

O `ROLLBACK` final encerrou apenas a transacao `READ ONLY` da consulta. Ele
**nao desfez a carga**, ja confirmada antes pelo `COMMIT` da etapa de carga.

### Resultado observado

[resultado_pedidos_pagamentos_entregas.csv](resultado_pedidos_pagamentos_entregas.csv)
foi **transcrito da saida da consulta interativa executada pelo autor**, com
ponto decimal; nao foi gerado por este arquivo. A execucao posterior do arquivo
salvo reproduziu esses mesmos valores, conforme o relato acima.

| situacao_pagamento | pedidos | valor_total_pedidos | valor_aprovado_registrado | tentativas_pendentes | tentativas_recusadas | pedidos_com_entrega | pedidos_com_todas_entregas_concluidas | pedidos_concluidos |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| PARCIAL | 60 | 14206.77 | 7103.53 | 0 | 0 | 0 | 0 | 0 |
| QUITADO | 600 | 146461.32 | 146461.32 | 0 | 0 | 600 | 350 | 350 |
| SEM_APROVACAO | 240 | 52817.43 | 0 | 40 | 40 | 0 | 0 | 0 |

Leitura, restrita ao que a tabela mostra: os tres grupos somam 900 pedidos;
nenhum esta `ACIMA_DO_TOTAL`; so pedidos `QUITADO` possuem entrega, e nesses o
valor aprovado registrado coincide com o total. Dos 600 quitados, 350 tem todas
as entregas `ENTREGUE` e 350 estao `CONCLUIDO`; a coincidencia dos dois numeros
neste resultado e consistente com a regra verificada na carga, mas esta tabela
nao identifica pedido a pedido. As tentativas pendentes e recusadas aparecem
apenas em `SEM_APROVACAO` e nao compoem valor aprovado. Esses numeros descrevem
dados sinteticos e nao medem desempenho logistico real.

## Limites

- Esta validacao verifica o conjunto carregado; nao implementa triggers de
  negocio nem prova que futuras alteracoes respeitarao as regras.
- Datas tem granularidade diaria; pagamento aprovado no mesmo dia do envio nao
  prova ordem intradiaria nem liquidacao bancaria. Reembolso registrado nao
  prova estorno efetivo ou vinculo a pagamento; nao ha item associado diretamente
  a remessa nem historico completo de transicoes.
- A execucao manual relatada nao altera nem comprova o historico original do
  projeto, que permanece fora desta distribuicao, com a etapa classificada como
  `ANOMALY` inalterada.
- O relato de execucao nao esta acompanhado de log preservado; ainda nao houve
  reproducao independente por terceiros, e o arquivo `04_pedidos_pagamentos_entregas.sql`
  foi reproduzido apenas pelo autor que executou a carga.
