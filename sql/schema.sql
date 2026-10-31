-- =====================================================================
-- Sompo AgroPredict - Schema do Banco de Dados (Oracle)
-- =====================================================================

-- Remover objetos existentes (se houver)
BEGIN EXECUTE IMMEDIATE 'DROP TABLE alertas CASCADE CONSTRAINTS';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF; END;
/
BEGIN EXECUTE IMMEDIATE 'DROP TABLE predicoes CASCADE CONSTRAINTS';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF; END;
/
BEGIN EXECUTE IMMEDIATE 'DROP TABLE operadores CASCADE CONSTRAINTS';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF; END;
/
BEGIN EXECUTE IMMEDIATE 'DROP TABLE equipamentos CASCADE CONSTRAINTS';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF; END;
/
BEGIN EXECUTE IMMEDIATE 'DROP TABLE usuarios CASCADE CONSTRAINTS';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF; END;
/
BEGIN EXECUTE IMMEDIATE 'DROP TABLE logs_auditoria CASCADE CONSTRAINTS';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF; END;
/
BEGIN EXECUTE IMMEDIATE 'DROP SEQUENCE seq_predicao';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -2289 THEN RAISE; END IF; END;
/
BEGIN EXECUTE IMMEDIATE 'DROP SEQUENCE seq_alerta';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -2289 THEN RAISE; END IF; END;
/
BEGIN EXECUTE IMMEDIATE 'DROP SEQUENCE seq_log_auditoria';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -2289 THEN RAISE; END IF; END;
/
BEGIN EXECUTE IMMEDIATE 'DROP VIEW vw_metricas_diarias';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF; END;
/

-- Tabela EQUIPAMENTOS
CREATE TABLE equipamentos (
    id_equipamento  NUMBER(6)     PRIMARY KEY,
    modelo          VARCHAR2(100) NOT NULL,
    fabricante      VARCHAR2(50)  NOT NULL,
    ano_fabricacao  NUMBER(4)     NOT NULL,
    fazenda         VARCHAR2(100),
    ativo           CHAR(1)       DEFAULT 'S' CHECK (ativo IN ('S','N'))
);

-- Tabela OPERADORES
CREATE TABLE operadores (
    id_operador  NUMBER(6)     PRIMARY KEY,
    nome         VARCHAR2(100) NOT NULL,
    cpf          VARCHAR2(14)  UNIQUE,
    fazenda      VARCHAR2(100),
    ativo        CHAR(1)       DEFAULT 'S' CHECK (ativo IN ('S','N'))
);

-- Tabela PREDICOES
CREATE TABLE predicoes (
    id_predicao     NUMBER(10)   PRIMARY KEY,
    data_hora       TIMESTAMP    DEFAULT SYSTIMESTAMP NOT NULL,
    id_equipamento  NUMBER(6),
    id_operador     NUMBER(6),
    umidade_solo    NUMBER(5,2)  NOT NULL,
    declividade     NUMBER(5,2)  NOT NULL,
    chuva_24h       NUMBER(6,2)  NOT NULL,
    temperatura     NUMBER(5,2)  NOT NULL,
    velocidade      NUMBER(5,2)  NOT NULL,
    idade_maquina   NUMBER(5,2)  NOT NULL,
    horas_operacao  NUMBER(5,2)  NOT NULL,
    status_operacao VARCHAR2(20) NOT NULL CHECK (status_operacao IN ('Colheita','Deslocamento','Manobra')),
    score_risco     NUMBER(5,2)  NOT NULL,
    classe_risco    VARCHAR2(10) NOT NULL CHECK (classe_risco IN ('BAIXO','MEDIO','ALTO')),
    recomendacao    VARCHAR2(200),
    prob_baixo      NUMBER(5,4),
    prob_medio      NUMBER(5,4),
    prob_alto       NUMBER(5,4),
    versao_modelo   VARCHAR2(20) DEFAULT 'v1.0'
);

ALTER TABLE predicoes ADD CONSTRAINT fk_pred_equip
    FOREIGN KEY (id_equipamento) REFERENCES equipamentos(id_equipamento);
ALTER TABLE predicoes ADD CONSTRAINT fk_pred_oper
    FOREIGN KEY (id_operador) REFERENCES operadores(id_operador);

CREATE INDEX idx_pred_data   ON predicoes(data_hora);
CREATE INDEX idx_pred_classe ON predicoes(classe_risco);
CREATE INDEX idx_pred_equip  ON predicoes(id_equipamento);

CREATE SEQUENCE seq_predicao START WITH 1 INCREMENT BY 1 NOCACHE;

-- Tabela ALERTAS
CREATE TABLE alertas (
    id_alerta    NUMBER(10)   PRIMARY KEY,
    id_predicao  NUMBER(10)   NOT NULL,
    data_emissao TIMESTAMP    DEFAULT SYSTIMESTAMP NOT NULL,
    acao_tomada  VARCHAR2(30) DEFAULT 'PENDENTE' CHECK (acao_tomada IN ('RESPEITOU','IGNOROU','PENDENTE')),
    data_acao    TIMESTAMP,
    observacao   VARCHAR2(500)
);
ALTER TABLE alertas ADD CONSTRAINT fk_alerta_pred
    FOREIGN KEY (id_predicao) REFERENCES predicoes(id_predicao);
CREATE SEQUENCE seq_alerta START WITH 1 INCREMENT BY 1 NOCACHE;

-- Tabela USUARIOS (controle de acesso)
CREATE TABLE usuarios (
    id_usuario    NUMBER(6)     PRIMARY KEY,
    nome          VARCHAR2(100) NOT NULL,
    email         VARCHAR2(100) UNIQUE NOT NULL,
    senha_hash    VARCHAR2(255) NOT NULL,
    role          VARCHAR2(20)  NOT NULL CHECK (role IN ('OPERADOR','GESTOR','ANALISTA_SOMPO')),
    id_operador   NUMBER(6)     NULL,
    fazenda       VARCHAR2(100) NULL,
    ativo         CHAR(1)       DEFAULT 'S' CHECK (ativo IN ('S','N'))
);
ALTER TABLE usuarios ADD CONSTRAINT fk_usuarios_operador
    FOREIGN KEY (id_operador) REFERENCES operadores(id_operador);

-- Tabela LOGS_AUDITORIA
CREATE TABLE logs_auditoria (
    id_log        NUMBER(10) PRIMARY KEY,
    id_usuario    NUMBER(6) NOT NULL,
    acao          VARCHAR2(100) NOT NULL,
    endpoint      VARCHAR2(100),
    payload_resumo VARCHAR2(500),
    ip_origem     VARCHAR2(50),
    data_hora     TIMESTAMP DEFAULT SYSTIMESTAMP
);
CREATE SEQUENCE seq_log_auditoria START WITH 1 INCREMENT BY 1 NOCACHE;

-- View de métricas diárias
CREATE OR REPLACE VIEW vw_metricas_diarias AS
SELECT
    TRUNC(p.data_hora)                                           AS dia,
    COUNT(*)                                                     AS total_predicoes,
    SUM(CASE WHEN p.classe_risco = 'BAIXO' THEN 1 ELSE 0 END)   AS qtd_baixo,
    SUM(CASE WHEN p.classe_risco = 'MEDIO' THEN 1 ELSE 0 END)   AS qtd_medio,
    SUM(CASE WHEN p.classe_risco = 'ALTO'  THEN 1 ELSE 0 END)   AS qtd_alto,
    ROUND(AVG(p.score_risco), 2)                                 AS score_medio,
    ROUND(MAX(p.score_risco), 2)                                 AS score_maximo
FROM predicoes p
GROUP BY TRUNC(p.data_hora);

-- Dados iniciais
INSERT INTO equipamentos VALUES (1, 'CR9.90', 'New Holland', 2018, 'Fazenda Aurora',   'S');
INSERT INTO equipamentos VALUES (2, 'S780',   'John Deere',  2020, 'Fazenda Aurora',   'S');
INSERT INTO equipamentos VALUES (3, '7240',   'Case IH',     2012, 'Fazenda Boa Vista','S');

INSERT INTO operadores VALUES (1, 'Carlos Silva',   '111.111.111-11', 'Fazenda Aurora',   'S');
INSERT INTO operadores VALUES (2, 'Maria Oliveira', '222.222.222-22', 'Fazenda Aurora',   'S');
INSERT INTO operadores VALUES (3, 'Joao Pereira',   '333.333.333-33', 'Fazenda Boa Vista','S');

-- Usuários (senhas hash são simuladas para teste)
INSERT INTO usuarios (id_usuario, nome, email, senha_hash, role, id_operador, fazenda)
VALUES (1, 'Carlos (Operador)', 'carlos@fazenda.com', 'hash_simulado_123', 'OPERADOR', 1, NULL);

INSERT INTO usuarios (id_usuario, nome, email, senha_hash, role, id_operador, fazenda)
VALUES (2, 'Maria (Gestora)', 'maria@fazenda.com', 'hash_simulado_123', 'GESTOR', NULL, 'Fazenda Aurora');

INSERT INTO usuarios (id_usuario, nome, email, senha_hash, role, id_operador, fazenda)
VALUES (3, 'Ana (Analista Sompo)', 'ana@sompo.com', 'hash_simulado_123', 'ANALISTA_SOMPO', NULL, NULL);

COMMIT;

-- Verificação
SELECT table_name FROM user_tables
WHERE table_name IN ('EQUIPAMENTOS','OPERADORES','PREDICOES','ALERTAS','USUARIOS','LOGS_AUDITORIA');
SELECT 'Equipamentos: ' || COUNT(*) FROM equipamentos;
SELECT 'Operadores: ' || COUNT(*) FROM operadores;
SELECT 'Usuários: ' || COUNT(*) FROM usuarios;