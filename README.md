# Trabalho logístico — banco relacional de logística (versão 1)

Projeto de portfólio: um banco PostgreSQL de logística, dados **sintéticos** gerados por um programa em Python, uma carga reproduzível a partir de um banco vazio e consultas que cruzam pedidos, pagamentos e entregas.

> **Todos os dados são sintéticos.** Nenhum cliente, pedido, pagamento, entrega ou valor representa pessoas, empresas ou operações reais. Os resultados mostram o funcionamento do modelo e das consultas; não indicam faturamento, liquidação bancária, desempenho de transportadoras reais nem redução de custos.

## Problema abordado

Uma operação logística precisa ligar o que foi vendido ao que foi pago, enviado, devolvido e retirado do estoque. Sem um modelo explícito, perguntas simples ficam sem resposta: quais pedidos foram pagos integralmente antes do envio? Quais tentativas de pagamento não contam como pagamento? Quais pedidos têm todas as entregas concluídas? Esta versão 1 modela essa cadeia em 20 tabelas relacionadas e mostra, com um conjunto de dados sintético, como consultar e verificar essas relações.

## Escopo implementado

| Domínio | Tabelas principais |
|---|---|
| Pedidos e pagamentos | `t_clientes`, `t_pedidos`, `t_item_pedido`, `t_pagamento` |
| Entregas e devoluções | `t_transportadora`, `t_entrega`, `t_historico_entrega`, `t_devolucao`, `t_item_devolucao` |
| Catálogo e compras | `t_categoria`, `t_produto`, `t_fornecedor`, `t_compra`, `t_item_compra` |
| Estoque | `t_armazem`, `t_estoque`, `t_movimentaÇÃo_estoque`, `t_avaria`, `t_inventario`, `t_item_inventario` |

O esquema tem **20 tabelas, 140 colunas, 20 chaves primárias e 21 chaves estrangeiras**. O [diagrama do modelo relacional](docs/MODELO_RELACIONAL_V1.md) mostra as tabelas e relações por domínio, com a lista completa de nomes físicos.

## Tecnologias efetivamente usadas

- **PostgreSQL 18.6** (banco em UTF8) e o cliente `psql` 18.6, no Windows.
- **SQL** para o esquema, a carga (`\copy`), as validações e a consulta de demonstração.
- **Python 3.13** (biblioteca padrão) no gerador de dados sintéticos e no verificador offline dos CSVs.
- **Oracle SQL Developer Data Modeler**, origem do DDL que foi adaptado ao PostgreSQL.
- **Mermaid** (em Markdown) para os diagramas do modelo. Os cinco diagramas foram conferidos visualmente pelo autor no GitHub.

## Resultados observados

A demonstração foi **executada manualmente** pelo autor em 09/11/2026 e relatada nas saídas descritas em [`demo/v1/README.md`](demo/v1/README.md). Esta distribuição não preserva logs dessas execuções. O que foi confirmado:

- Banco novo e separado `projeto_logistico_demo_v1`, PostgreSQL 18.6, UTF8.
- Criação do esquema, quatro registros-base fictícios, carga de 20 arquivos CSV (10.000 registros) e validação executadas manualmente, com `COMMIT` ao final.
- **10.004 linhas** no cenário executado (10.000 dos CSVs mais 4 registros-base fictícios).
- A consulta [`04_pedidos_pagamentos_entregas.sql`](demo/v1/04_pedidos_pagamentos_entregas.sql) foi executada depois do `COMMIT` e reproduziu os três grupos e todos os valores do arquivo [`resultado_pedidos_pagamentos_entregas.csv`](demo/v1/resultado_pedidos_pagamentos_entregas.csv). O `ROLLBACK` dela encerra apenas a transação de leitura; não desfaz a carga.

### Pedidos, pagamentos e entregas (dados sintéticos)

| Situação do pagamento | Pedidos | Com entrega | Todas as entregas concluídas | Pedidos concluídos |
|---|---:|---:|---:|---:|
| `PARCIAL` | 60 | 0 | 0 | 0 |
| `QUITADO` | 600 | 600 | 350 | 350 |
| `SEM_APROVACAO` | 240 | 0 | 0 | 0 |

No grupo `SEM_APROVACAO` há 40 tentativas de pagamento `PENDENTE` e 40 `RECUSADO`. São **tentativas**, não necessariamente pedidos distintos, e não entram no valor aprovado. As colunas «Com entrega» contam **pedidos** com ao menos um registro de entrega, não registros de entrega (a tabela tem 800). Valores monetários agregados estão no arquivo [CSV](demo/v1/resultado_pedidos_pagamentos_entregas.csv); o projeto não define moeda — os valores são nominais — e o valor aprovado é um registro sintético, não uma liquidação bancária.

Leitura, restrita à tabela: nesta massa, só pedidos quitados têm entrega, e nenhum pedido está acima do total. As definições completas das colunas estão em [`demo/v1/README.md`](demo/v1/README.md).

## Regras: o que é verificado, o que é imposto e o que não é garantido

| Camada | O que existe |
|---|---|
| **Constraints do banco** | Chaves primárias, 21 chaves estrangeiras, `NOT NULL` em chaves e em poucas colunas e **um** `CHECK` (modal de `t_transportadora`). Detalhes em [`docs/MODELO_RELACIONAL_V1.md`](docs/MODELO_RELACIONAL_V1.md). |
| **Validação feita por código** | [`demo/v1/03_validate.sql`](demo/v1/03_validate.sql) é um bloco `DO` que confere, sobre os dados **carregados**, contagens, integridade referencial e regras como pagamento integral antes do envio, pedido concluído apenas com pagamento integral e todas as entregas `ENTREGUE`, devoluções e limite de reembolso, saldo e reserva de estoque conciliados com movimentos e pareamento de avarias. Em Python, [`scripts/verify_pilot_artifacts.py`](scripts/verify_pilot_artifacts.py) valida os CSVs e o manifesto **antes** da carga. |
| **Regras verificadas neste conjunto** | Aprovadas pela validação relatada acima para a massa de 10.004 linhas. Valem para esse conjunto, não para outro. |
| **Sem garantia futura** | O esquema não tem triggers, views nem `CHECK` para status e valores. Uma inserção ou atualização futura pode violar essas regras sem ser barrada pelo banco. |

A validação **não é** um conjunto de triggers e não substitui testes de outras execuções.

## Como reproduzir

Pré-requisitos: PostgreSQL 18 (servidor e `psql`), Python 3.13, uma conta que possa criar o banco `projeto_logistico_demo_v1` e uma cópia deste repositório. Sem acesso a backup privado.

O roteiro completo, com ordem dos arquivos, comandos, contagens esperadas e critérios de aceite, está em [`demo/v1/README.md`](demo/v1/README.md). O banco deve ser novo; a rota recusa um banco preenchido e não inclui `DROP`, `TRUNCATE` nem limpeza. O DDL revisado em [`docs/ddl_historico/propostas/`](docs/ddl_historico/propostas/trabalho_logistico_postgresql_REVISAO_OFFLINE_NAO_EXECUTAR.sql) é incluído por `demo/v1/00_schema.sql`, apenas nas condições dessa demonstração (banco novo e separado, depois das verificações de preflight); o aviso «não executar» do cabeçalho do arquivo se refere a outro uso. Não registre senhas em arquivos.

## Organização dos arquivos

| Caminho | Finalidade |
|---|---|
| [`demo/v1/`](demo/v1/) | Rota reproduzível: esquema (`00`), dados-base (`01`), carga (`02`), validação (`03`), consulta de pedidos, pagamentos e entregas (`04`), resultado em CSV e README do roteiro |
| [`docs/MODELO_RELACIONAL_V1.md`](docs/MODELO_RELACIONAL_V1.md) | Diagramas e nomes físicos do modelo |
| [`docs/ddl_historico/propostas/`](docs/ddl_historico/propostas/) | DDL PostgreSQL revisado, incluído por `demo/v1/00_schema.sql` |
| [`tools/logistics_generator.py`](tools/logistics_generator.py) | Gerador e validações dos dados sintéticos (também importado pelo verificador) |
| [`scripts/verify_pilot_artifacts.py`](scripts/verify_pilot_artifacts.py) | Verificador offline dos CSVs, hashes e manifesto, executado antes da carga |
| [`generated_data/full_20261008_1724/`](generated_data/full_20261008_1724/) | 20 CSVs originais da carga e o `manifest.json` |
| [`generated_data/full_20261008_1724_ascii/`](generated_data/full_20261008_1724_ascii/) | Cópias dos 20 CSVs com nomes de arquivo ASCII, usadas pelo `\copy` |
| `.gitattributes`, `.gitignore` | Preservam os bytes dos CSVs (hashes verificados) e limitam o que entra no repositório |

## Limitações conhecidas

- A evidência da execução é o relato do autor; não há logs preservados, e outra pessoa ainda não reproduziu a rota.
- Os dados são sintéticos e a massa é pequena (10.004 linhas); não há análise de desempenho.
- O modelo não liga item de pedido a remessa, nem reembolso a pagamento, e não guarda o histórico completo de transições de pedido; só as entregas têm histórico de eventos.
- Datas têm granularidade diária; um pagamento aprovado no mesmo dia do envio não prova a ordem intradiária.
- As regras de negócio estão verificadas sobre os dados carregados, mas não são impostas por triggers, views ou `CHECK`.
- Há grafias herdadas do DDL de origem (por exemplo `id_transpotadora`, `peÇo_venda`), preservadas para manter a fidelidade ao esquema; use os identificadores exatos entre aspas duplas, conforme o carregador.
- A rota foi preparada para Windows e PostgreSQL 18; não foi testada em outros ambientes.

## Melhorias futuras

Triggers ou `CHECK` para as regras de pagamento, entrega e estoque; vínculo entre item e remessa e entre reembolso e pagamento; histórico completo de transições; consultas de estoque e de transportadoras sobre o banco da V1; registro de logs da execução. Nenhuma delas faz parte da versão 1.

## Delimitação histórica

Esta V1 se refere à demonstração no banco `projeto_logistico_demo_v1`. O histórico anterior do projeto, com outros bancos, análises e uma etapa classificada como `ANOMALY`, permanece no projeto original; não faz parte desta distribuição, não é comprovado por esta demonstração e não foi alterado.
