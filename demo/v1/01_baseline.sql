\set ON_ERROR_STOP on

DO $baseline$
DECLARE
    relation record;
    row_exists boolean;
BEGIN
    IF current_database() <> 'projeto_logistico_demo_v1'
       OR NOT EXISTS (
           SELECT 1 FROM pg_temp.demo_v1_stage
           WHERE stage = 'schema' AND transaction_id = pg_current_xact_id()
       ) THEN
        RAISE EXCEPTION 'Etapa ou banco incorreto para o baseline';
    END IF;
    IF (SELECT count(*) FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')) <> 20 THEN
        RAISE EXCEPTION 'Esperadas exatamente 20 tabelas no schema public';
    END IF;
    FOR relation IN
        SELECT c.relname FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
        ORDER BY c.relname
    LOOP
        EXECUTE format('LOCK TABLE public.%I IN ACCESS EXCLUSIVE MODE', relation.relname);
        EXECUTE format('SELECT EXISTS (SELECT 1 FROM public.%I)', relation.relname)
            INTO row_exists;
        IF row_exists THEN
            RAISE EXCEPTION 'Tabela public.% nao esta vazia', relation.relname;
        END IF;
    END LOOP;
END
$baseline$;

-- Registros novos e ficticios: nao sao os quatro registros historicos.
INSERT INTO public."t_armazem" ("id_armazem", "nome_armazem")
VALUES (1, 'Armazem base demonstracao');
INSERT INTO public."t_categoria" ("id_categoria", "nome_categoria")
VALUES (1, 'Categoria base demonstracao');
INSERT INTO public."t_clientes"
    ("id_clientes", "nome", "cpf_cnpj", "email", "endereÇo")
VALUES (1, 'Cliente base ficticio', 'DEMO-CLIENTE-1',
        'cliente-base@exemplo.invalid', 'Endereco ficticio');
INSERT INTO public."t_fornecedor" ("id_fornecedor", "razao_social", "telefone")
VALUES (1, 'Fornecedor base ficticio', 'DEMO-1');

UPDATE pg_temp.demo_v1_stage SET stage = 'baseline';
