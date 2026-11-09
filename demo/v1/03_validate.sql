\set ON_ERROR_STOP on
\encoding UTF8

DO $validate$
DECLARE
    expected record;
    fk record;
    actual_count bigint;
    total_count bigint := 0;
    actual_min bigint;
    actual_max bigint;
    join_predicate text;
    non_null_predicate text;
    has_orphans boolean;
    primary_keys bigint;
    foreign_keys bigint;
    checks bigint;
BEGIN
    IF current_database() <> 'projeto_logistico_demo_v1'
       OR NOT EXISTS (
           SELECT 1 FROM pg_temp.demo_v1_stage
           WHERE stage = 'loaded' AND transaction_id = pg_current_xact_id()
       )
       OR current_setting('session_replication_role') <> 'origin' THEN
        RAISE EXCEPTION 'Etapa ou banco incorreto para validacao';
    END IF;

    FOR expected IN
        SELECT * FROM (VALUES
            ('t_armazem', 'id_armazem', 5), ('t_avaria', 'id_avaria', 40),
            ('t_categoria', 'id_categoria', 20), ('t_clientes', 'id_clientes', 1000),
            ('t_compra', 'id_compra', 200), ('t_devolucao', 'id_devoluÇÃo', 60),
            ('t_entrega', 'id_entrega', 800), ('t_estoque', 'id_estoque', 400),
            ('t_fornecedor', 'id_fornecedor', 30),
            ('t_historico_entrega', 'id_historico', 1700),
            ('t_inventario', 'id_inventario', 60),
            ('t_item_compra', 'id_item_compra', 400),
            ('t_item_devolucao', 'id_item_devoluÇÃo', 90),
            ('t_item_inventario', 'id_item_inventario', 400),
            ('t_item_pedido', 'id_item_pedido', 1750),
            ('t_movimentaÇÃo_estoque', 'id_movimentaÇÃo', 1000),
            ('t_pagamento', 'id_pagamento', 840), ('t_pedidos', 'id_pedidos', 900),
            ('t_produto', 'id_produto', 300),
            ('t_transportadora', 'id_transpotadora', 9)
        ) AS counts(table_name, pk_column, expected_count)
    LOOP
        EXECUTE format('SELECT count(*), min(%I), max(%I) FROM public.%I',
                       expected.pk_column, expected.pk_column, expected.table_name)
            INTO actual_count, actual_min, actual_max;
        IF actual_count <> expected.expected_count OR actual_min IS DISTINCT FROM 1
           OR actual_max IS DISTINCT FROM expected.expected_count THEN
            RAISE EXCEPTION 'Contagem ou faixa de IDs incorreta em %', expected.table_name;
        END IF;
        total_count := total_count + actual_count;
        RAISE NOTICE 'public.%: % linhas, IDs % a %',
            expected.table_name, actual_count, actual_min, actual_max;
    END LOOP;
    IF total_count <> 10004 THEN
        RAISE EXCEPTION 'Total esperado: 10004; encontrado %', total_count;
    END IF;

    SELECT count(*) FILTER (WHERE c.contype = 'p'),
           count(*) FILTER (WHERE c.contype = 'f'),
           count(*) FILTER (WHERE c.contype = 'c')
    INTO primary_keys, foreign_keys, checks
    FROM pg_constraint c
    JOIN pg_class r ON r.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = r.relnamespace
    WHERE n.nspname = 'public';
    IF primary_keys <> 20 OR foreign_keys <> 21 OR checks <> 1
       OR (SELECT count(*) FROM information_schema.columns
           WHERE table_schema = 'public') <> 140 THEN
        RAISE EXCEPTION 'Estrutura inesperada: PK %, FK %, CHECK %',
            primary_keys, foreign_keys, checks;
    END IF;

    FOR fk IN
        SELECT c.* FROM pg_constraint c
        JOIN pg_class r ON r.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = r.relnamespace
        WHERE n.nspname = 'public' AND c.contype = 'f'
    LOOP
        IF NOT fk.convalidated THEN
            RAISE EXCEPTION 'FK nao validada: %', fk.conname;
        END IF;
        SELECT string_agg(format('child_row.%I = parent_row.%I', ca.attname, pa.attname),
                          ' AND ' ORDER BY keys.ordinality),
               string_agg(format('child_row.%I IS NOT NULL', ca.attname),
                          ' AND ' ORDER BY keys.ordinality)
        INTO join_predicate, non_null_predicate
        FROM unnest(fk.conkey, fk.confkey) WITH ORDINALITY
            AS keys(child_attnum, parent_attnum, ordinality)
        JOIN pg_attribute ca ON ca.attrelid = fk.conrelid AND ca.attnum = keys.child_attnum
        JOIN pg_attribute pa ON pa.attrelid = fk.confrelid AND pa.attnum = keys.parent_attnum;
        EXECUTE format(
            'SELECT EXISTS (SELECT 1 FROM %s child_row WHERE %s AND NOT EXISTS
             (SELECT 1 FROM %s parent_row WHERE %s))',
            fk.conrelid::regclass, non_null_predicate, fk.confrelid::regclass, join_predicate
        ) INTO has_orphans;
        IF has_orphans THEN
            RAISE EXCEPTION 'FK com registros orfaos: %', fk.conname;
        END IF;
    END LOOP;

    IF EXISTS (
        SELECT 1 FROM public."t_item_pedido" i
        WHERE i."quantidade" <= 0 OR i."preco_unitario" IS NULL
           OR i."preco_unitario" <= 0 OR i."desconto" IS NULL OR i."desconto" < 0
           OR i."desconto" > i."quantidade" * i."preco_unitario"
           OR i."subtotal" IS DISTINCT FROM i."quantidade" * i."preco_unitario" - i."desconto"
    ) OR EXISTS (
        SELECT 1 FROM public."t_pedidos" p
        WHERE p."valor_total" IS NULL OR p."data_pedido" IS NULL OR NOT EXISTS (
            SELECT 1 FROM public."t_item_pedido" i WHERE i."t_pedidos_id_pedidos" = p."id_pedidos"
        ) OR p."valor_total" IS DISTINCT FROM (
            SELECT sum(i."subtotal") FROM public."t_item_pedido" i
            WHERE i."t_pedidos_id_pedidos" = p."id_pedidos"
        )
    ) THEN
        RAISE EXCEPTION 'Itens e totais de pedidos inconsistentes';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public."t_item_compra" i
        WHERE i."quantidade" IS NULL OR i."quantidade" <= 0
           OR i."preÇo_unitario" IS NULL OR i."preÇo_unitario" <= 0
           OR i."subtotal" IS DISTINCT FROM i."quantidade" * i."preÇo_unitario"
    ) OR EXISTS (
        SELECT 1 FROM public."t_compra" c
        WHERE c."valor_total" IS NULL OR NOT EXISTS (
            SELECT 1 FROM public."t_item_compra" i WHERE i."t_compra_id_compra" = c."id_compra"
        ) OR c."valor_total" IS DISTINCT FROM (
            SELECT sum(i."subtotal") FROM public."t_item_compra" i
            WHERE i."t_compra_id_compra" = c."id_compra"
        )
    ) THEN
        RAISE EXCEPTION 'Itens e totais de compras inconsistentes';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public."t_pagamento" pay
        JOIN public."t_pedidos" p ON p."id_pedidos" = pay."t_pedidos_id_pedidos"
        WHERE pay."status_pagamento" IS NULL
           OR pay."status_pagamento" NOT IN ('APROVADO', 'PENDENTE', 'RECUSADO')
           OR pay."valor_pago" IS NULL OR pay."valor_pago" <= 0
           OR pay."data_pagamento" IS NULL OR p."data_pedido" IS NULL
           OR pay."data_pagamento" < p."data_pedido"
    ) OR EXISTS (
        SELECT 1 FROM public."t_pedidos" p
        WHERE (SELECT coalesce(sum(pay."valor_pago"), 0) FROM public."t_pagamento" pay
               WHERE pay."t_pedidos_id_pedidos" = p."id_pedidos"
                 AND pay."status_pagamento" = 'APROVADO') > p."valor_total"
    ) THEN
        RAISE EXCEPTION 'Pagamento invalido ou aprovado acima do total';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public."t_entrega" e
        JOIN public."t_pedidos" p ON p."id_pedidos" = e."t_pedidos_id_pedidos"
        WHERE e."data_envio" IS NULL OR e."data_prevista" IS NULL
           OR e."data_envio" < p."data_pedido" OR e."data_envio" > e."data_prevista"
           OR e."status_entrega" IS NULL
           OR e."status_entrega" NOT IN ('ENTREGUE', 'EM_TRANSITO', 'ATRASADA',
                                         'EXTRAVIADA', 'DEVOLVIDA_A_ORIGEM')
           OR (e."status_entrega" = 'ENTREGUE' AND
               (e."data_entrega" IS NULL OR e."data_entrega" < e."data_envio"))
           OR (e."status_entrega" <> 'ENTREGUE' AND e."data_entrega" IS NOT NULL)
           OR (SELECT coalesce(sum(pay."valor_pago"), 0) FROM public."t_pagamento" pay
               WHERE pay."t_pedidos_id_pedidos" = p."id_pedidos"
                 AND pay."status_pagamento" = 'APROVADO'
                 AND pay."data_pagamento" <= e."data_envio") < p."valor_total"
    ) THEN
        RAISE EXCEPTION 'RN-012 ou datas/estado de entrega inconsistentes';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public."t_pedidos" p
        WHERE p."status_pedidos" = 'CONCLUIDO' AND (
            (SELECT coalesce(sum(pay."valor_pago"), 0) FROM public."t_pagamento" pay
             WHERE pay."t_pedidos_id_pedidos" = p."id_pedidos"
               AND pay."status_pagamento" = 'APROVADO') < p."valor_total"
            OR NOT EXISTS (SELECT 1 FROM public."t_entrega" e
                           WHERE e."t_pedidos_id_pedidos" = p."id_pedidos")
            OR EXISTS (SELECT 1 FROM public."t_entrega" e
                       WHERE e."t_pedidos_id_pedidos" = p."id_pedidos"
                         AND e."status_entrega" IS DISTINCT FROM 'ENTREGUE')
        )
    ) THEN
        RAISE EXCEPTION 'RN-014: pedido concluido sem quitacao ou entregas concluidas';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public."t_entrega" e
        WHERE NOT EXISTS (
            SELECT 1 FROM public."t_historico_entrega" h
            WHERE h."t_entrega_id_entrega" = e."id_entrega"
        ) OR (
            SELECT h."status_evento" FROM public."t_historico_entrega" h
            WHERE h."t_entrega_id_entrega" = e."id_entrega"
            ORDER BY h."data_evento" DESC, h."id_historico" DESC LIMIT 1
        ) IS DISTINCT FROM CASE e."status_entrega"
            WHEN 'ENTREGUE' THEN 'ENTREGUE'
            WHEN 'EM_TRANSITO' THEN 'EM_TRANSITO'
            WHEN 'ATRASADA' THEN 'ATRASO_IDENTIFICADO'
            WHEN 'EXTRAVIADA' THEN 'EXTRAVIO_CONFIRMADO'
            WHEN 'DEVOLVIDA_A_ORIGEM' THEN 'RETORNO_A_ORIGEM'
        END
    ) OR EXISTS (
        SELECT 1 FROM public."t_historico_entrega" h
        JOIN public."t_entrega" e ON e."id_entrega" = h."t_entrega_id_entrega"
        WHERE h."data_evento" IS NULL OR h."data_evento" < e."data_envio"
           OR (e."data_entrega" IS NOT NULL AND h."data_evento" > e."data_entrega")
    ) THEN
        RAISE EXCEPTION 'Historico de entrega inconsistente';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public."t_item_devolucao" r
        JOIN public."t_devolucao" d ON d."id_devoluÇÃo" = r."t_devoluÇÃo_id_devoluÇÃo"
        JOIN public."t_item_pedido" i ON i."id_item_pedido" = r."t_item_pedido_id_item_pedido"
        WHERE r."quantidade" IS NULL OR r."quantidade" <= 0
           OR d."t_pedidos_id_pedidos" <> i."t_pedidos_id_pedidos"
    ) OR EXISTS (
        SELECT 1 FROM public."t_item_devolucao" r
        JOIN public."t_item_pedido" i ON i."id_item_pedido" = r."t_item_pedido_id_item_pedido"
        GROUP BY i."id_item_pedido", i."quantidade"
        HAVING sum(r."quantidade") > i."quantidade"
    ) OR EXISTS (
        SELECT 1 FROM public."t_devolucao" d
        WHERE d."valor_reembolso" IS NULL OR d."valor_reembolso" < 0
           OR d."data_solicitaÇÃo" IS NULL
           OR (d."data_conclusÃo" IS NOT NULL AND d."data_conclusÃo" < d."data_solicitaÇÃo")
           OR NOT EXISTS (
               SELECT 1 FROM public."t_pedidos" p
               WHERE p."id_pedidos" = d."t_pedidos_id_pedidos"
                 AND p."status_pedidos" = 'CONCLUIDO'
           )
           OR NOT EXISTS (
               SELECT 1 FROM public."t_entrega" e
               WHERE e."t_pedidos_id_pedidos" = d."t_pedidos_id_pedidos"
                 AND e."status_entrega" = 'ENTREGUE' AND e."data_entrega" IS NOT NULL
           )
           OR d."data_solicitaÇÃo" <= (
               SELECT max(e."data_entrega") FROM public."t_entrega" e
               WHERE e."t_pedidos_id_pedidos" = d."t_pedidos_id_pedidos"
                 AND e."status_entrega" = 'ENTREGUE'
           )
           OR NOT EXISTS (SELECT 1 FROM public."t_item_devolucao" r
                          WHERE r."t_devoluÇÃo_id_devoluÇÃo" = d."id_devoluÇÃo")
           OR d."valor_reembolso" > (
               SELECT sum(least(round(i."subtotal" / i."quantidade", 2) * r."quantidade", i."subtotal"))
               FROM public."t_item_devolucao" r
               JOIN public."t_item_pedido" i ON i."id_item_pedido" = r."t_item_pedido_id_item_pedido"
               WHERE r."t_devoluÇÃo_id_devoluÇÃo" = d."id_devoluÇÃo"
           )
    ) THEN
        RAISE EXCEPTION 'RN-028/RN-029 ou valor de reembolso inconsistente';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public."t_movimentaÇÃo_estoque" m
        WHERE m."quantidade" IS NULL OR m."quantidade" <= 0
           OR m."tipo_movimentação" IS NULL
           OR m."tipo_movimentação" NOT IN ('ENTRADA', 'SAIDA')
    ) OR EXISTS (
        SELECT 1 FROM public."t_estoque" s
        LEFT JOIN public."t_movimentaÇÃo_estoque" m ON m."t_estoque_id_estoque" = s."id_estoque"
        GROUP BY s."id_estoque", s."quantidade_atual", s."quantidade_reservada"
        HAVING s."quantidade_atual" IS NULL OR s."quantidade_reservada" IS NULL
            OR s."quantidade_atual" < 0 OR s."quantidade_reservada" < 0
            OR s."quantidade_reservada" > s."quantidade_atual"
            OR s."quantidade_atual" IS DISTINCT FROM coalesce(sum(
                CASE m."tipo_movimentação" WHEN 'ENTRADA' THEN m."quantidade"
                     WHEN 'SAIDA' THEN -m."quantidade" END), 0)
    ) THEN
        RAISE EXCEPTION 'Estoque, reserva ou conciliacao de movimentos inconsistente';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public."t_item_inventario" i
        JOIN public."t_inventario" inv ON inv."id_inventario" = i."t_inventario_id_inventario"
        JOIN public."t_estoque" s ON s."id_estoque" = i."t_estoque_id_estoque"
        WHERE i."quantidade_sistema" IS NULL OR i."quantidade_sistema" < 0
           OR i."quantidade_contada" IS NULL OR i."quantidade_contada" < 0
           OR i."diferenÇa" IS DISTINCT FROM i."quantidade_contada" - i."quantidade_sistema"
           OR i."quantidade_sistema" IS DISTINCT FROM s."quantidade_atual"
           OR inv."t_armazem_id_armazem" <> s."t_armazem_id_armazem"
    ) OR EXISTS (
        SELECT 1 FROM public."t_avaria" a
        LEFT JOIN public."t_movimentaÇÃo_estoque" m
          ON m."documento_referencia" = 'AVARIA:' || a."id_avaria"::text
        GROUP BY a."id_avaria", a."quantidade", a."t_estoque_id_estoque", a."data_avaria"
        HAVING count(m."id_movimentaÇÃo") <> 1
           OR min(m."tipo_movimentação") IS DISTINCT FROM 'SAIDA'
           OR min(m."quantidade") IS DISTINCT FROM a."quantidade"
           OR min(m."t_estoque_id_estoque") IS DISTINCT FROM a."t_estoque_id_estoque"
           OR min(m."data_movimentação") IS DISTINCT FROM a."data_avaria"
    ) THEN
        RAISE EXCEPTION 'Inventario ou movimento de avaria inconsistente';
    END IF;

    UPDATE pg_temp.demo_v1_stage SET stage = 'validated';
    RAISE NOTICE 'Validacao da demonstracao concluida; transacao permanece aberta';
END
$validate$;
