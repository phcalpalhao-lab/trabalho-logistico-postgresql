\set ON_ERROR_STOP on
\encoding UTF8

DO $load_guard$
BEGIN
    IF current_database() <> 'projeto_logistico_demo_v1'
       OR NOT EXISTS (
           SELECT 1 FROM pg_temp.demo_v1_stage
           WHERE stage = 'baseline' AND transaction_id = pg_current_xact_id()
       )
       OR current_setting('session_replication_role') <> 'origin' THEN
        RAISE EXCEPTION 'Etapa ou banco incorreto para a carga';
    END IF;
END
$load_guard$;

-- Caminhos relativos ao diretorio corrente do psql: raiz do repositorio.
-- Usar o conjunto ASCII verificado contra os originais e seu manifesto.
\copy public."t_armazem" ("id_armazem", "nome_armazem", "endereÇo", "cidade", "estado", "capacidade", "ativo") FROM 'generated_data\full_20261008_1724_ascii\t_armazem.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy public."t_categoria" ("id_categoria", "nome_categoria", "descriÇÃo", "ativo") FROM 'generated_data\full_20261008_1724_ascii\t_categoria.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy public."t_clientes" ("id_clientes", "nome", "cpf_cnpj", "email", "endereÇo", "data_cadastro", "status") FROM 'generated_data\full_20261008_1724_ascii\t_clientes.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy public."t_fornecedor" ("id_fornecedor", "razao_social", "nome_fantasia", "cnpj", "email", "telefone", "prazo_entrega_dias", "ativo") FROM 'generated_data\full_20261008_1724_ascii\t_fornecedor.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy public."t_transportadora" ("id_transpotadora", "razao_social", "cnpj", "telefone", "email", "tipo_trasnporte", "prazo_medio_dias", "ativo") FROM 'generated_data\full_20261008_1724_ascii\t_transportadora.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy public."t_produto" ("id_produto", "sku", "nome", "descriÇao", "peso_kg", "dimensoes", "preÇo_custo", "peÇo_venda", "estoque_minimo", "ativo", "t_categoria_id_categoria") FROM 'generated_data\full_20261008_1724_ascii\t_produto.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy public."t_compra" ("id_compra", "data_compra", "data_previsÃo", "status_compra", "valor_total", "numero_total", "t_fornecedor_id_fornecedor") FROM 'generated_data\full_20261008_1724_ascii\t_compra.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy public."t_pedidos" ("id_pedidos", "t_clientes_id_clientes", "data_pedido", "status_pedidos", "valor_total") FROM 'generated_data\full_20261008_1724_ascii\t_pedidos.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy public."t_estoque" ("id_estoque", "quantidade_atual", "quantidade_reservada", "localizaÇÃo", "ultima_atualizaÇÃo", "t_produto_id_produto", "t_armazem_id_armazem") FROM 'generated_data\full_20261008_1724_ascii\t_estoque.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy public."t_inventario" ("id_inventario", "data_abertura", "data_fechamento", "status_inventario", "observaÇÃo", "t_armazem_id_armazem") FROM 'generated_data\full_20261008_1724_ascii\t_inventario.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy public."t_item_compra" ("id_item_compra", "quantidade", "preÇo_unitario", "subtotal", "t_compra_id_compra", "t_produto_id_produto") FROM 'generated_data\full_20261008_1724_ascii\t_item_compra.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy public."t_item_pedido" ("id_item_pedido", "quantidade", "preco_unitario", "desconto", "subtotal", "t_pedidos_id_pedidos", "t_produto_id_produto") FROM 'generated_data\full_20261008_1724_ascii\t_item_pedido.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy public."t_pagamento" ("id_pagamento", "data_pagamento", "valor_pago", "forma_pagamento", "status_pagamento", "codigo_transaÇÃo", "t_pedidos_id_pedidos") FROM 'generated_data\full_20261008_1724_ascii\t_pagamento.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy public."t_entrega" ("id_entrega", "codigo_rastreio", "data_envio", "data_prevista", "data_entrega", "status_entrega", "valor_frete", "t_pedidos_id_pedidos", "id_transportadora") FROM 'generated_data\full_20261008_1724_ascii\t_entrega.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8', FORCE_NULL ("data_entrega"))
\copy public."t_devolucao" ("id_devoluÇÃo", "data_solicitaÇÃo", "motivo", "status_devoluÇÃo", "data_conclusÃo", "valor_reembolso", "t_pedidos_id_pedidos") FROM 'generated_data\full_20261008_1724_ascii\t_devolucao.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy public."t_item_inventario" ("id_item_inventario", "quantidade_sistema", "quantidade_contada", "diferenÇa", "observaÇÃo", "t_inventario_id_inventario", "t_estoque_id_estoque") FROM 'generated_data\full_20261008_1724_ascii\t_item_inventario.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy public."t_movimentaÇÃo_estoque" ("id_movimentaÇÃo", "tipo_movimentação", "quantidade", "data_movimentação", "motivo", "documento_referencia", "t_estoque_id_estoque") FROM 'generated_data\full_20261008_1724_ascii\t_movimentacao_estoque.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy public."t_avaria" ("id_avaria", "data_avaria", "quantidade", "tipo_avaria", "descriÇÃo", "custo_estimado", "status_avaria", "t_estoque_id_estoque") FROM 'generated_data\full_20261008_1724_ascii\t_avaria.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy public."t_historico_entrega" ("id_historico", "data_evento", "status_evento", "local_evento", "observaÇÃo", "t_entrega_id_entrega") FROM 'generated_data\full_20261008_1724_ascii\t_historico_entrega.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy public."t_item_devolucao" ("id_item_devoluÇÃo", "quantidade", "condiÇÃo_produto", "motivo_item", "t_devoluÇÃo_id_devoluÇÃo", "t_item_pedido_id_item_pedido") FROM 'generated_data\full_20261008_1724_ascii\t_item_devolucao.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')

UPDATE pg_temp.demo_v1_stage SET stage = 'loaded';
