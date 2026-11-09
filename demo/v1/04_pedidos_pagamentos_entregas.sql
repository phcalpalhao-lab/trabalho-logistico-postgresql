\set ON_ERROR_STOP on
\encoding UTF8

-- Consulta somente de leitura sobre dados sinteticos de demonstracao.
-- Executar no banco projeto_logistico_demo_v1, em sessao nova.
-- Pagamentos e entregas sao agregados separadamente por pedido antes da
-- juncao, para nao multiplicar valores.
BEGIN READ ONLY;

WITH pagamentos AS (
    SELECT
        pay."t_pedidos_id_pedidos" AS id_pedidos,
        sum(pay."valor_pago") FILTER (WHERE pay."status_pagamento" = 'APROVADO')
            AS valor_aprovado,
        count(*) FILTER (WHERE pay."status_pagamento" = 'PENDENTE')
            AS tentativas_pendentes,
        count(*) FILTER (WHERE pay."status_pagamento" = 'RECUSADO')
            AS tentativas_recusadas
    FROM public."t_pagamento" pay
    GROUP BY pay."t_pedidos_id_pedidos"
),
entregas AS (
    SELECT
        e."t_pedidos_id_pedidos" AS id_pedidos,
        count(*) AS total_entregas,
        count(*) FILTER (WHERE e."status_entrega" = 'ENTREGUE') AS entregas_entregues
    FROM public."t_entrega" e
    GROUP BY e."t_pedidos_id_pedidos"
),
pedidos_base AS (
    SELECT
        p."id_pedidos",
        p."status_pedidos",
        p."valor_total",
        coalesce(pg.valor_aprovado, 0) AS valor_aprovado,
        coalesce(pg.tentativas_pendentes, 0) AS tentativas_pendentes,
        coalesce(pg.tentativas_recusadas, 0) AS tentativas_recusadas,
        coalesce(en.total_entregas, 0) AS total_entregas,
        coalesce(en.entregas_entregues, 0) AS entregas_entregues,
        CASE
            WHEN coalesce(pg.valor_aprovado, 0) > p."valor_total" THEN 'ACIMA_DO_TOTAL'
            WHEN coalesce(pg.valor_aprovado, 0) = p."valor_total" THEN 'QUITADO'
            WHEN coalesce(pg.valor_aprovado, 0) > 0 THEN 'PARCIAL'
            ELSE 'SEM_APROVACAO'
        END AS situacao_pagamento
    FROM public."t_pedidos" p
    LEFT JOIN pagamentos pg ON pg.id_pedidos = p."id_pedidos"
    LEFT JOIN entregas en ON en.id_pedidos = p."id_pedidos"
)
SELECT
    situacao_pagamento,
    count(*) AS pedidos,
    sum("valor_total") AS valor_total_pedidos,
    sum(valor_aprovado) AS valor_aprovado_registrado,
    sum(tentativas_pendentes) AS tentativas_pendentes,
    sum(tentativas_recusadas) AS tentativas_recusadas,
    count(*) FILTER (WHERE total_entregas > 0) AS pedidos_com_entrega,
    count(*) FILTER (
        WHERE total_entregas > 0 AND entregas_entregues = total_entregas
    ) AS pedidos_com_todas_entregas_concluidas,
    count(*) FILTER (WHERE "status_pedidos" = 'CONCLUIDO') AS pedidos_concluidos
FROM pedidos_base
GROUP BY situacao_pagamento
ORDER BY situacao_pagamento;

ROLLBACK;
