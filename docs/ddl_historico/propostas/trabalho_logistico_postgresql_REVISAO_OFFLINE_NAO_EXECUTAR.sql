-- PROPOSTA DE REVISAO OFFLINE - NAO EXECUTAR SEM PLANO E AUTORIZACAO ESPECIFICOS.
-- Derivada de trabalho_logistico_postgresql_sql.sql recebido em 04/11/2026.
-- SHA-256 da fonte: 0f5bbeee0c0e021f1878b44ab18f653a7ebed8ee70fb3a2af2331848e3f370cf
-- Ajuste de corpo: remocao de cinco modificadores BYTE em VARCHAR(n BYTE).
-- Os comentarios Oracle abaixo pertencem ao historico da fonte original.
-- Esta proposta nao e extracao do backup, migracao nem prova do banco atual.
-- Nao inclui gates de destino, controle transacional ou autorizacao de execucao.

-- Gerado por Oracle SQL Developer Data Modeler 24.3.1.351.0831
--   em:        2026-10-06 17:24:07 BRT
--   site:      Oracle Database 11g
--   tipo:      Oracle Database 11g



-- predefined type, no DDL - MDSYS.SDO_GEOMETRY

-- predefined type, no DDL - XMLTYPE

CREATE TABLE T_ARMAZEM 
    ( 
     ID_ARMAZEM   INTEGER  NOT NULL , 
     NOME_ARMAZEM VARCHAR (100 ) , 
     ENDEREÇO     VARCHAR (200 ) , 
     CIDADE       VARCHAR (100 ) , 
     ESTADO       CHAR (2 ) , 
     CAPACIDADE   INTEGER , 
     ATIVO        CHAR (1 ) 
    ) 
;

ALTER TABLE T_ARMAZEM 
    ADD CONSTRAINT T_ARMAZEM_PK PRIMARY KEY ( ID_ARMAZEM ) ;

CREATE TABLE T_AVARIA 
    ( 
     ID_AVARIA            INTEGER  NOT NULL , 
     DATA_AVARIA          DATE , 
     QUANTIDADE           INTEGER , 
     TIPO_AVARIA          VARCHAR (30 ) , 
     DESCRIÇÃO            VARCHAR (200) , 
     CUSTO_ESTIMADO       NUMERIC (12,2) , 
     STATUS_AVARIA        VARCHAR (20 ) , 
     T_ESTOQUE_ID_ESTOQUE INTEGER  NOT NULL 
    ) 
;

ALTER TABLE T_AVARIA 
    ADD CONSTRAINT T_AVARIA_PK PRIMARY KEY ( ID_AVARIA ) ;

CREATE TABLE T_CATEGORIA 
    ( 
     ID_CATEGORIA   INTEGER  NOT NULL , 
     NOME_CATEGORIA VARCHAR (100 ) , 
     DESCRIÇÃO      VARCHAR (200 ) , 
     ATIVO          CHAR (1 ) 
    ) 
;

ALTER TABLE T_CATEGORIA 
    ADD CONSTRAINT T_CATEGORIA_PK PRIMARY KEY ( ID_CATEGORIA ) ;

CREATE TABLE T_CLIENTES 
    ( 
     ID_CLIENTES   INTEGER  NOT NULL , 
     NOME          VARCHAR (200)  NOT NULL , 
     CPF_CNPJ      VARCHAR (20 )  NOT NULL , 
     EMAIL         VARCHAR (100)  NOT NULL , 
     ENDEREÇO      VARCHAR (20)  NOT NULL , 
     DATA_CADASTRO DATE , 
     STATUS        VARCHAR (20) 
    ) 
;

ALTER TABLE T_CLIENTES 
    ADD CONSTRAINT T_CLIENTES_PK PRIMARY KEY ( ID_CLIENTES ) ;

CREATE TABLE T_COMPRA 
    ( 
     ID_COMPRA                  INTEGER  NOT NULL , 
     DATA_COMPRA                DATE , 
     DATA_PREVISÃO              DATE , 
     STATUS_COMPRA              VARCHAR (20 ) , 
     VALOR_TOTAL                NUMERIC (12,2) , 
     NUMERO_TOTAL               VARCHAR (30 ) , 
     T_FORNECEDOR_ID_FORNECEDOR INTEGER  NOT NULL 
    ) 
;

ALTER TABLE T_COMPRA 
    ADD CONSTRAINT T_COMPRA_PK PRIMARY KEY ( ID_COMPRA ) ;

CREATE TABLE T_DEVOLUCAO 
    ( 
     ID_DEVOLUÇÃO         INTEGER  NOT NULL , 
     DATA_SOLICITAÇÃO     DATE , 
     MOTIVO               VARCHAR (200 ) , 
     STATUS_DEVOLUÇÃO     VARCHAR (30 ) , 
     DATA_CONCLUSÃO       DATE , 
     VALOR_REEMBOLSO      NUMERIC (12,2) , 
     T_PEDIDOS_ID_PEDIDOS INTEGER  NOT NULL 
    ) 
;

ALTER TABLE T_DEVOLUCAO 
    ADD CONSTRAINT T_DEVOLUÇÃO_PK PRIMARY KEY ( ID_DEVOLUÇÃO ) ;

CREATE TABLE T_ENTREGA 
    ( 
     ID_ENTREGA           INTEGER  NOT NULL , 
     CODIGO_RASTREIO      VARCHAR (50 ) , 
     DATA_ENVIO           DATE , 
     DATA_PREVISTA        DATE , 
     DATA_ENTREGA         DATE , 
     STATUS_ENTREGA       VARCHAR (30 ) , 
     VALOR_FRETE          NUMERIC (10,2) , 
     T_PEDIDOS_ID_PEDIDOS INTEGER  NOT NULL , 
     ID_TRANSPORTADORA    INTEGER  NOT NULL 
    ) 
;

ALTER TABLE T_ENTREGA 
    ADD CONSTRAINT T_ENTREGA_PK PRIMARY KEY ( ID_ENTREGA ) ;

CREATE TABLE T_ESTOQUE 
    ( 
     ID_ESTOQUE           INTEGER  NOT NULL , 
     QUANTIDADE_ATUAL     INTEGER , 
     QUANTIDADE_RESERVADA INTEGER , 
     LOCALIZAÇÃO          VARCHAR (30 ) , 
     ULTIMA_ATUALIZAÇÃO   DATE , 
     T_PRODUTO_ID_PRODUTO INTEGER  NOT NULL , 
     T_ARMAZEM_ID_ARMAZEM INTEGER  NOT NULL 
    ) 
;

ALTER TABLE T_ESTOQUE 
    ADD CONSTRAINT T_ESTOQUE_PK PRIMARY KEY ( ID_ESTOQUE ) ;

CREATE TABLE T_FORNECEDOR 
    ( 
     ID_FORNECEDOR      INTEGER  NOT NULL , 
     RAZAO_SOCIAL       VARCHAR (120 ) , 
     NOME_FANTASIA      VARCHAR (100) , 
     CNPJ               VARCHAR (20 ) , 
     EMAIL              VARCHAR (100 ) , 
     TELEFONE           VARCHAR (20 )  NOT NULL , 
     PRAZO_ENTREGA_DIAS INTEGER , 
     ATIVO              CHAR (1 ) 
    ) 
;

ALTER TABLE T_FORNECEDOR 
    ADD CONSTRAINT T_FORNECEDOR_PK PRIMARY KEY ( ID_FORNECEDOR ) ;

CREATE TABLE T_HISTORICO_ENTREGA 
    ( 
     ID_HISTORICO         INTEGER  NOT NULL , 
     DATA_EVENTO          DATE , 
     STATUS_EVENTO        VARCHAR (30 ) , 
     LOCAL_EVENTO         VARCHAR (100 ) , 
     OBSERVAÇÃO           VARCHAR (200 ) , 
     T_ENTREGA_ID_ENTREGA INTEGER  NOT NULL 
    ) 
;

ALTER TABLE T_HISTORICO_ENTREGA 
    ADD CONSTRAINT T_HISTORICO_ENTREGA_PK PRIMARY KEY ( ID_HISTORICO ) ;

CREATE TABLE T_INVENTARIO 
    ( 
     ID_INVENTARIO        INTEGER  NOT NULL , 
     DATA_ABERTURA        DATE , 
     DATA_FECHAMENTO      DATE , 
     STATUS_INVENTARIO    VARCHAR (20 ) , 
     OBSERVAÇÃO           VARCHAR (200 ) , 
     T_ARMAZEM_ID_ARMAZEM INTEGER  NOT NULL 
    ) 
;

ALTER TABLE T_INVENTARIO 
    ADD CONSTRAINT T_INVENTARIO_PK PRIMARY KEY ( ID_INVENTARIO ) ;

CREATE TABLE T_ITEM_COMPRA 
    ( 
     ID_ITEM_COMPRA       INTEGER  NOT NULL , 
     QUANTIDADE           INTEGER , 
     PREÇO_UNITARIO       NUMERIC (10,2) , 
     SUBTOTAL             NUMERIC (12,2) , 
     T_COMPRA_ID_COMPRA   INTEGER  NOT NULL , 
     T_PRODUTO_ID_PRODUTO INTEGER  NOT NULL 
    ) 
;

ALTER TABLE T_ITEM_COMPRA 
    ADD CONSTRAINT T_ITEM_COMPRA_PK PRIMARY KEY ( ID_ITEM_COMPRA ) ;

CREATE TABLE T_ITEM_DEVOLUCAO 
    ( 
     ID_ITEM_DEVOLUÇÃO            INTEGER  NOT NULL , 
     QUANTIDADE                   INTEGER , 
     CONDIÇÃO_PRODUTO             VARCHAR (30 ) , 
     MOTIVO_ITEM                  VARCHAR (200 ) , 
     T_DEVOLUÇÃO_ID_DEVOLUÇÃO     INTEGER  NOT NULL , 
     T_ITEM_PEDIDO_ID_ITEM_PEDIDO INTEGER  NOT NULL 
    ) 
;

ALTER TABLE T_ITEM_DEVOLUCAO 
    ADD CONSTRAINT T_ITEM_DEVOLUÇÃO_PK PRIMARY KEY ( ID_ITEM_DEVOLUÇÃO ) ;

CREATE TABLE T_ITEM_INVENTARIO 
    ( 
     ID_ITEM_INVENTARIO         INTEGER  NOT NULL , 
     QUANTIDADE_SISTEMA         INTEGER , 
     QUANTIDADE_CONTADA         INTEGER , 
     DIFERENÇA                  INTEGER , 
     OBSERVAÇÃO                 VARCHAR (200 ) , 
     T_INVENTARIO_ID_INVENTARIO INTEGER  NOT NULL , 
     T_ESTOQUE_ID_ESTOQUE       INTEGER  NOT NULL 
    ) 
;

ALTER TABLE T_ITEM_INVENTARIO 
    ADD CONSTRAINT T_ITEM_INVENTARIO_PK PRIMARY KEY ( ID_ITEM_INVENTARIO ) ;

CREATE TABLE T_ITEM_PEDIDO 
    ( 
     ID_ITEM_PEDIDO       INTEGER  NOT NULL , 
     QUANTIDADE           INTEGER  NOT NULL , 
     PRECO_UNITARIO       NUMERIC (10,2) , 
     DESCONTO             NUMERIC (10,2) , 
     SUBTOTAL             NUMERIC (10,2) , 
     T_PEDIDOS_ID_PEDIDOS INTEGER  NOT NULL , 
     T_PRODUTO_ID_PRODUTO INTEGER  NOT NULL 
    ) 
;

ALTER TABLE T_ITEM_PEDIDO 
    ADD CONSTRAINT T_ITEM_PEDIDO_PK PRIMARY KEY ( ID_ITEM_PEDIDO ) ;

CREATE TABLE T_MOVIMENTAÇÃO_ESTOQUE 
    ( 
     ID_MOVIMENTAÇÃO      INTEGER  NOT NULL , 
     tipo_movimentação    VARCHAR (20 ) , 
     quantidade           INTEGER , 
     data_movimentação    DATE , 
     motivo               VARCHAR (200 ) , 
     documento_referencia VARCHAR (50 ) , 
     T_ESTOQUE_ID_ESTOQUE INTEGER  NOT NULL 
    ) 
;

ALTER TABLE T_MOVIMENTAÇÃO_ESTOQUE 
    ADD CONSTRAINT T_MOVIMENTAÇÃO_ESTOQUE_PK PRIMARY KEY ( ID_MOVIMENTAÇÃO ) ;

CREATE TABLE T_PAGAMENTO 
    ( 
     ID_PAGAMENTO         INTEGER  NOT NULL , 
     DATA_PAGAMENTO       DATE , 
     VALOR_PAGO           NUMERIC (12,2) , 
     FORMA_PAGAMENTO      VARCHAR (30 ) , 
     STATUS_PAGAMENTO     VARCHAR (20 ) , 
     CODIGO_TRANSAÇÃO     VARCHAR (80 ) , 
     T_PEDIDOS_ID_PEDIDOS INTEGER  NOT NULL 
    ) 
;

ALTER TABLE T_PAGAMENTO 
    ADD CONSTRAINT T_PAGAMENTO_PK PRIMARY KEY ( ID_PAGAMENTO ) ;

CREATE TABLE T_PEDIDOS 
    ( 
     ID_PEDIDOS             INTEGER  NOT NULL , 
     T_CLIENTES_ID_CLIENTES INTEGER  NOT NULL , 
     DATA_PEDIDO            DATE , 
     STATUS_PEDIDOS         VARCHAR (20) , 
     VALOR_TOTAL            NUMERIC (10,2) 
    ) 
;

ALTER TABLE T_PEDIDOS 
    ADD CONSTRAINT T_PEDIDOS_PK PRIMARY KEY ( ID_PEDIDOS ) ;

CREATE TABLE T_PRODUTO 
    ( 
     ID_PRODUTO               INTEGER  NOT NULL , 
     SKU                      VARCHAR (50 ) , 
     NOME                     VARCHAR (100 )  NOT NULL , 
     DESCRIÇAO                VARCHAR (200 ) , 
     PESO_KG                  NUMERIC (8,2) , 
     DIMENSOES                VARCHAR (50 ) , 
     PREÇO_CUSTO              NUMERIC (10,2) , 
     PEÇO_VENDA               NUMERIC (10,2) , 
     ESTOQUE_MINIMO           INTEGER , 
     ATIVO                    CHAR (1) , 
     T_CATEGORIA_ID_CATEGORIA INTEGER  NOT NULL 
    ) 
;

ALTER TABLE T_PRODUTO 
    ADD CONSTRAINT T_PRODUTO_PK PRIMARY KEY ( ID_PRODUTO ) ;

CREATE TABLE T_TRANSPORTADORA 
    ( 
     ID_TRANSPOTADORA INTEGER  NOT NULL , 
     RAZAO_SOCIAL     VARCHAR (120 ) , 
     CNPJ             VARCHAR (20 ) , 
     TELEFONE         VARCHAR (20 )  NOT NULL , 
     EMAIL            VARCHAR (100 ) , 
     TIPO_TRASNPORTE  VARCHAR (30 ) , 
     PRAZO_MEDIO_DIAS INTEGER , 
     ATIVO            CHAR (1 ) 
    ) 
;

ALTER TABLE T_TRANSPORTADORA 
    ADD 
    CHECK (TIPO_TRASNPORTE IN ('RODOVIARIO ', 'AEREO', 'MARITIMO')) 
;

ALTER TABLE T_TRANSPORTADORA 
    ADD CONSTRAINT T_TRANSPORTADORA_PK PRIMARY KEY ( ID_TRANSPOTADORA ) ;

ALTER TABLE T_ITEM_DEVOLUCAO 
    ADD CONSTRAINT FK_DEV_ITEM_PEDIDO FOREIGN KEY 
    ( 
     T_ITEM_PEDIDO_ID_ITEM_PEDIDO
    ) 
    REFERENCES T_ITEM_PEDIDO 
    ( 
     ID_ITEM_PEDIDO
    ) 
;

ALTER TABLE T_ENTREGA 
    ADD CONSTRAINT FK_ENTREGA_TRASNPOTADORA FOREIGN KEY 
    ( 
     ID_TRANSPORTADORA
    ) 
    REFERENCES T_TRANSPORTADORA 
    ( 
     ID_TRANSPOTADORA
    ) 
;

ALTER TABLE T_HISTORICO_ENTREGA 
    ADD CONSTRAINT FK_HIST_ENRTEGA FOREIGN KEY 
    ( 
     T_ENTREGA_ID_ENTREGA
    ) 
    REFERENCES T_ENTREGA 
    ( 
     ID_ENTREGA
    ) 
;

ALTER TABLE T_ITEM_DEVOLUCAO 
    ADD CONSTRAINT FK_ITEM_DEVOLUCAO FOREIGN KEY 
    ( 
     T_DEVOLUÇÃO_ID_DEVOLUÇÃO
    ) 
    REFERENCES T_DEVOLUCAO 
    ( 
     ID_DEVOLUÇÃO
    ) 
;

ALTER TABLE T_ITEM_INVENTARIO 
    ADD CONSTRAINT FK_ITEM_INV_ESTOQUE FOREIGN KEY 
    ( 
     T_ESTOQUE_ID_ESTOQUE
    ) 
    REFERENCES T_ESTOQUE 
    ( 
     ID_ESTOQUE
    ) 
;

ALTER TABLE T_ITEM_INVENTARIO 
    ADD CONSTRAINT FK_ITEM_INV_INVENTARIO FOREIGN KEY 
    ( 
     T_INVENTARIO_ID_INVENTARIO
    ) 
    REFERENCES T_INVENTARIO 
    ( 
     ID_INVENTARIO
    ) 
;

ALTER TABLE T_MOVIMENTAÇÃO_ESTOQUE 
    ADD CONSTRAINT FK_MOV_ESTOQUE FOREIGN KEY 
    ( 
     T_ESTOQUE_ID_ESTOQUE
    ) 
    REFERENCES T_ESTOQUE 
    ( 
     ID_ESTOQUE
    ) 
;

ALTER TABLE T_AVARIA 
    ADD CONSTRAINT T_AVARIA_T_ESTOQUE_FK FOREIGN KEY 
    ( 
     T_ESTOQUE_ID_ESTOQUE
    ) 
    REFERENCES T_ESTOQUE 
    ( 
     ID_ESTOQUE
    ) 
;

ALTER TABLE T_COMPRA 
    ADD CONSTRAINT T_COMPRA_T_FORNECEDOR_FK FOREIGN KEY 
    ( 
     T_FORNECEDOR_ID_FORNECEDOR
    ) 
    REFERENCES T_FORNECEDOR 
    ( 
     ID_FORNECEDOR
    ) 
;

ALTER TABLE T_DEVOLUCAO 
    ADD CONSTRAINT T_DEVOLUÇÃO_T_PEDIDOS_FK FOREIGN KEY 
    ( 
     T_PEDIDOS_ID_PEDIDOS
    ) 
    REFERENCES T_PEDIDOS 
    ( 
     ID_PEDIDOS
    ) 
;

ALTER TABLE T_ENTREGA 
    ADD CONSTRAINT T_ENTREGA_T_PEDIDOS_FK FOREIGN KEY 
    ( 
     T_PEDIDOS_ID_PEDIDOS
    ) 
    REFERENCES T_PEDIDOS 
    ( 
     ID_PEDIDOS
    ) 
;

ALTER TABLE T_ESTOQUE 
    ADD CONSTRAINT T_ESTOQUE_T_ARMAZEM_FK FOREIGN KEY 
    ( 
     T_ARMAZEM_ID_ARMAZEM
    ) 
    REFERENCES T_ARMAZEM 
    ( 
     ID_ARMAZEM
    ) 
;

ALTER TABLE T_ESTOQUE 
    ADD CONSTRAINT T_ESTOQUE_T_PRODUTO_FK FOREIGN KEY 
    ( 
     T_PRODUTO_ID_PRODUTO
    ) 
    REFERENCES T_PRODUTO 
    ( 
     ID_PRODUTO
    ) 
;

ALTER TABLE T_INVENTARIO 
    ADD CONSTRAINT T_INVENTARIO_T_ARMAZEM_FK FOREIGN KEY 
    ( 
     T_ARMAZEM_ID_ARMAZEM
    ) 
    REFERENCES T_ARMAZEM 
    ( 
     ID_ARMAZEM
    ) 
;

ALTER TABLE T_ITEM_COMPRA 
    ADD CONSTRAINT T_ITEM_COMPRA_T_COMPRA_FK FOREIGN KEY 
    ( 
     T_COMPRA_ID_COMPRA
    ) 
    REFERENCES T_COMPRA 
    ( 
     ID_COMPRA
    ) 
;

ALTER TABLE T_ITEM_COMPRA 
    ADD CONSTRAINT T_ITEM_COMPRA_T_PRODUTO_FK FOREIGN KEY 
    ( 
     T_PRODUTO_ID_PRODUTO
    ) 
    REFERENCES T_PRODUTO 
    ( 
     ID_PRODUTO
    ) 
;

ALTER TABLE T_ITEM_PEDIDO 
    ADD CONSTRAINT T_ITEM_PEDIDO_T_PEDIDOS_FK FOREIGN KEY 
    ( 
     T_PEDIDOS_ID_PEDIDOS
    ) 
    REFERENCES T_PEDIDOS 
    ( 
     ID_PEDIDOS
    ) 
;

ALTER TABLE T_ITEM_PEDIDO 
    ADD CONSTRAINT T_ITEM_PEDIDO_T_PRODUTO_FK FOREIGN KEY 
    ( 
     T_PRODUTO_ID_PRODUTO
    ) 
    REFERENCES T_PRODUTO 
    ( 
     ID_PRODUTO
    ) 
;

ALTER TABLE T_PAGAMENTO 
    ADD CONSTRAINT T_PAGAMENTO_T_PEDIDOS_FK FOREIGN KEY 
    ( 
     T_PEDIDOS_ID_PEDIDOS
    ) 
    REFERENCES T_PEDIDOS 
    ( 
     ID_PEDIDOS
    ) 
;

ALTER TABLE T_PEDIDOS 
    ADD CONSTRAINT T_PEDIDOS_T_CLIENTES_FK FOREIGN KEY 
    ( 
     T_CLIENTES_ID_CLIENTES
    ) 
    REFERENCES T_CLIENTES 
    ( 
     ID_CLIENTES
    ) 
;

ALTER TABLE T_PRODUTO 
    ADD CONSTRAINT T_PRODUTO_T_CATEGORIA_FK FOREIGN KEY 
    ( 
     T_CATEGORIA_ID_CATEGORIA
    ) 
    REFERENCES T_CATEGORIA 
    ( 
     ID_CATEGORIA
    ) 
;



-- Relatório do Resumo do Oracle SQL Developer Data Modeler: 
-- 
-- CREATE TABLE                            20
-- CREATE INDEX                             0
-- ALTER TABLE                             42
-- CREATE VIEW                              0
-- ALTER VIEW                               0
-- CREATE PACKAGE                           0
-- CREATE PACKAGE BODY                      0
-- CREATE PROCEDURE                         0
-- CREATE FUNCTION                          0
-- CREATE TRIGGER                           0
-- ALTER TRIGGER                            0
-- CREATE COLLECTION TYPE                   0
-- CREATE STRUCTURED TYPE                   0
-- CREATE STRUCTURED TYPE BODY              0
-- CREATE CLUSTER                           0
-- CREATE CONTEXT                           0
-- CREATE DATABASE                          0
-- CREATE DIMENSION                         0
-- CREATE DIRECTORY                         0
-- CREATE DISK GROUP                        0
-- CREATE ROLE                              0
-- CREATE ROLLBACK SEGMENT                  0
-- CREATE SEQUENCE                          0
-- CREATE MATERIALIZED VIEW                 0
-- CREATE MATERIALIZED VIEW LOG             0
-- CREATE SYNONYM                           0
-- CREATE TABLESPACE                        0
-- CREATE USER                              0
-- 
-- DROP TABLESPACE                          0
-- DROP DATABASE                            0
-- 
-- REDACTION POLICY                         0
-- 
-- ORDS DROP SCHEMA                         0
-- ORDS ENABLE SCHEMA                       0
-- ORDS ENABLE OBJECT                       0
-- 
-- ERRORS                                   0
-- WARNINGS                                 0
