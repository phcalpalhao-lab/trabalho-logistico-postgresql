\set ON_ERROR_STOP on
\encoding UTF8

-- Executar em uma nova sessao psql, somente no banco de demonstracao vazio.
BEGIN;
SET LOCAL search_path = public, pg_catalog;
SET LOCAL standard_conforming_strings = on;

DO $preflight$
BEGIN
    IF current_database() <> 'projeto_logistico_demo_v1' THEN
        RAISE EXCEPTION 'Banco incorreto: esperado projeto_logistico_demo_v1';
    END IF;
    IF current_setting('server_version_num')::integer < 180000
       OR current_setting('server_version_num')::integer >= 190000 THEN
        RAISE EXCEPTION 'A rota preparada requer PostgreSQL 18';
    END IF;
    IF current_setting('server_encoding') <> 'UTF8' THEN
        RAISE EXCEPTION 'A rota preparada requer banco UTF8';
    END IF;
    IF current_setting('session_replication_role') <> 'origin' THEN
        RAISE EXCEPTION 'A verificacao normal de triggers e constraints e obrigatoria';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_namespace
        WHERE nspname NOT IN ('public', 'information_schema')
          AND nspname NOT LIKE 'pg\_%' ESCAPE '\'
    ) OR EXISTS (
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
    ) OR EXISTS (
        SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
    ) OR EXISTS (
        SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'public'
    ) OR EXISTS (
        SELECT 1 FROM pg_extension WHERE extname <> 'plpgsql'
    ) OR EXISTS (
        SELECT 1 FROM pg_event_trigger
    ) OR EXISTS (
        SELECT 1 FROM pg_publication
    ) THEN
        RAISE EXCEPTION 'Banco inesperadamente preenchido; interrompa sem limpar';
    END IF;
END
$preflight$;

CREATE TEMP TABLE demo_v1_stage (
    stage text NOT NULL,
    transaction_id xid8 NOT NULL DEFAULT pg_current_xact_id()
);
INSERT INTO pg_temp.demo_v1_stage (stage) VALUES ('schema');

-- Fonte revisada, mantida separada e inalterada; caminho relativo a este arquivo.
\ir '..\\..\\docs\\ddl_historico\\propostas\\trabalho_logistico_postgresql_REVISAO_OFFLINE_NAO_EXECUTAR.sql'
