-- ================================================================
-- FILE   : schema.sql
-- DESCRICAO: DDL das tabelas DB2/PostgreSQL do LifeCore-Mainframe
-- PROJETO: LifeCore-Mainframe
-- NOTA   : Sintaxe compativel com DB2 z/OS e PostgreSQL (ocesql)
-- ================================================================

-- ----------------------------------------------------------------
-- SEGURADO
-- ----------------------------------------------------------------
CREATE TABLE SEGURADO (
    CD_CPF              CHAR(11)        NOT NULL,
    NM_SEGURADO         VARCHAR(40)     NOT NULL,
    DT_NASCIMENTO       CHAR(8)         NOT NULL,
    DS_EMAIL            VARCHAR(80),
    NR_TELEFONE         CHAR(15),
    DT_INCLUSAO         CHAR(8)         NOT NULL,
    ID_USUARIO_INCL     CHAR(8)         NOT NULL,
    CONSTRAINT PK_SEGURADO PRIMARY KEY (CD_CPF)
);

-- ----------------------------------------------------------------
-- APOLICE
-- ----------------------------------------------------------------
CREATE TABLE APOLICE (
    NR_APOLICE          CHAR(12)        NOT NULL,
    CD_PRODUTO          CHAR(3)         NOT NULL,   -- VGC / GLB
    CD_CNPJ_ESTIPULANTE CHAR(14)        NOT NULL,
    CD_CPF_SEGURADO     CHAR(11)        NOT NULL,
    DT_VIGENCIA_INI     CHAR(8)         NOT NULL,
    DT_VIGENCIA_FIM     CHAR(8)         NOT NULL,
    CD_STATUS           CHAR(2)         NOT NULL DEFAULT 'AT',
    TP_CAPITAL          CHAR(1)         NOT NULL,   -- F/E/M/B/P
    VL_CAPITAL_SEGURADO DECIMAL(15,2)   NOT NULL,
    VL_SALARIO_BASE     DECIMAL(13,2),
    NR_FATOR_MULT       DECIMAL(5,2),
    VL_PREMIO_LIQUIDO   DECIMAL(13,2)   NOT NULL,
    VL_PREMIO_BRUTO     DECIMAL(13,2)   NOT NULL,
    VL_IOF              DECIMAL(11,2),
    TP_FORMA_PAGAMENTO  CHAR(2)         NOT NULL,   -- BO/CC/DB
    TP_PERIODICIDADE    CHAR(2)         NOT NULL,   -- MN/AN/UN
    DT_EMISSAO          CHAR(8)         NOT NULL,
    ID_USUARIO_INCL     CHAR(8)         NOT NULL,
    TS_INCLUSAO         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT PK_APOLICE    PRIMARY KEY (NR_APOLICE),
    CONSTRAINT FK_APO_SEG    FOREIGN KEY (CD_CPF_SEGURADO)
                             REFERENCES SEGURADO(CD_CPF),
    CONSTRAINT CK_APO_PROD   CHECK (CD_PRODUTO IN ('VGC','GLB')),
    CONSTRAINT CK_APO_STATUS CHECK (CD_STATUS  IN ('AT','CA','SU')),
    CONSTRAINT CK_APO_CAPITAL CHECK (TP_CAPITAL IN ('F','E','M','B','P')),
    CONSTRAINT CK_APO_PGTO   CHECK (TP_FORMA_PAGAMENTO IN ('BO','CC','DB'))
);

-- ----------------------------------------------------------------
-- COBERTURA
-- ----------------------------------------------------------------
CREATE TABLE COBERTURA (
    NR_COBERTURA        CHAR(16)        NOT NULL,
    NR_APOLICE          CHAR(12)        NOT NULL,
    CD_TIPO_COBERTURA   CHAR(4)         NOT NULL,   -- MORT/INVA/DIT
    NM_COBERTURA        VARCHAR(60)     NOT NULL,
    VL_CAPITAL          DECIMAL(15,2)   NOT NULL,
    PC_CARENCIA_DIAS    SMALLINT,
    CD_STATUS           CHAR(2)         NOT NULL DEFAULT 'AT',
    CONSTRAINT PK_COBERTURA PRIMARY KEY (NR_COBERTURA),
    CONSTRAINT FK_COB_APO   FOREIGN KEY (NR_APOLICE)
                            REFERENCES APOLICE(NR_APOLICE)
);

-- ----------------------------------------------------------------
-- FATURA
-- ----------------------------------------------------------------
CREATE TABLE FATURA (
    NR_FATURA           CHAR(14)        NOT NULL,
    CD_CNPJ_ESTIPULANTE CHAR(14)        NOT NULL,
    DS_ESTIPULANTE      VARCHAR(40),
    CD_COMPETENCIA      CHAR(6)         NOT NULL,
    DT_EMISSAO          CHAR(8)         NOT NULL,
    DT_VENCIMENTO       CHAR(8),
    DT_PAGAMENTO        CHAR(8),
    QT_APOLICES         INTEGER         NOT NULL DEFAULT 0,
    VL_BRUTO            DECIMAL(15,2)   NOT NULL DEFAULT 0,
    VL_DESCONTO         DECIMAL(13,2)   NOT NULL DEFAULT 0,
    VL_LIQUIDO          DECIMAL(15,2)   NOT NULL DEFAULT 0,
    VL_PAGO             DECIMAL(15,2)   NOT NULL DEFAULT 0,
    CD_STATUS           CHAR(2)         NOT NULL DEFAULT 'PE',
    TP_FORMA_PAGAMENTO  CHAR(2),
    DS_NOSSO_NUMERO     CHAR(20),
    DS_LINHA_DIGITAVEL  CHAR(47),
    ID_USUARIO_EMISSAO  CHAR(8),
    TS_INCLUSAO         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT PK_FATURA    PRIMARY KEY (NR_FATURA),
    CONSTRAINT CK_FAT_STATUS CHECK (CD_STATUS IN ('PE','PG','PP','AT','CA'))
);

-- ----------------------------------------------------------------
-- PAGAMENTO
-- ----------------------------------------------------------------
CREATE TABLE PAGAMENTO (
    NR_PAGAMENTO        CHAR(16)        NOT NULL,
    NR_FATURA           CHAR(14)        NOT NULL,
    NR_APOLICE          CHAR(12),
    DT_PAGAMENTO        CHAR(8)         NOT NULL,
    HR_PAGAMENTO        CHAR(6),
    VL_PAGAMENTO        DECIMAL(15,2)   NOT NULL,
    TP_FORMA            CHAR(2)         NOT NULL,
    CD_STATUS           CHAR(2)         NOT NULL DEFAULT 'CF',
    CD_BANDEIRA         CHAR(4),
    -- PCI: nunca armazena PAN. Token + mascara somente.
    DS_TOKEN_CARTAO     CHAR(32),
    NR_CARTAO_ULTIMOS4  CHAR(4),
    NR_NSU              CHAR(12),
    CD_AUTORIZACAO      CHAR(6),
    DS_ADQUIRENTE       CHAR(8),
    NR_PARCELAS         SMALLINT        DEFAULT 1,
    CD_ISO8583          CHAR(4),
    TS_INCLUSAO         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT PK_PAGAMENTO  PRIMARY KEY (NR_PAGAMENTO),
    CONSTRAINT FK_PAG_FAT    FOREIGN KEY (NR_FATURA)
                             REFERENCES FATURA(NR_FATURA),
    CONSTRAINT CK_PAG_STATUS CHECK (CD_STATUS IN ('CF','CA','ES','CB')),
    CONSTRAINT CK_PAG_FORMA  CHECK (TP_FORMA  IN ('BO','CC','DB'))
);

-- ----------------------------------------------------------------
-- CONCILIACAO
-- ----------------------------------------------------------------
CREATE TABLE CONCILIACAO (
    NR_CONCILIACAO      CHAR(16)        NOT NULL,
    NR_FATURA           CHAR(14)        NOT NULL,
    NR_PAGAMENTO        CHAR(16),
    NR_APOLICE          CHAR(12),
    DT_CONCILIACAO      CHAR(8)         NOT NULL,
    VL_FATURADO         DECIMAL(15,2)   NOT NULL,
    VL_PAGO             DECIMAL(15,2)   NOT NULL DEFAULT 0,
    VL_DIFERENCA        DECIMAL(13,2)   NOT NULL DEFAULT 0,
    CD_STATUS           CHAR(2)         NOT NULL,   -- OK/DV/SP/SF/DU/CB
    TP_CANAL            CHAR(2),
    NR_NSU              CHAR(12),
    CD_AUTORIZACAO      CHAR(6),
    CD_CICLO_CLEARING   CHAR(8),
    ID_USUARIO          CHAR(8),
    DS_OBSERVACAO       VARCHAR(100),
    TS_INCLUSAO         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT PK_CONCIL     PRIMARY KEY (NR_CONCILIACAO),
    CONSTRAINT FK_CON_FAT    FOREIGN KEY (NR_FATURA)
                             REFERENCES FATURA(NR_FATURA),
    CONSTRAINT CK_CON_STATUS CHECK (CD_STATUS IN ('OK','DV','SP','SF','DU','CB'))
);

-- ----------------------------------------------------------------
-- DISPUTA  (chargebacks e divergencias de liquidacao)
-- ----------------------------------------------------------------
CREATE TABLE DISPUTA (
    NR_DISPUTA          INTEGER         NOT NULL,
    NR_NSU              CHAR(12)        NOT NULL,
    TP_DISPUTA          CHAR(4)         NOT NULL,   -- CB00 / DIVG
    VL_DISPUTA          DECIMAL(15,2)   NOT NULL,
    DT_ABERTURA         CHAR(8)         NOT NULL,
    CD_STATUS           CHAR(2)         NOT NULL DEFAULT 'AB',
    DS_OBSERVACAO       VARCHAR(200),
    DT_ENCERRAMENTO     CHAR(8),
    TS_INCLUSAO         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT PK_DISPUTA    PRIMARY KEY (NR_DISPUTA),
    CONSTRAINT CK_DIS_STATUS CHECK (CD_STATUS IN ('AB','EN','GA','PE'))
);

-- ----------------------------------------------------------------
-- INDEXES
-- ----------------------------------------------------------------
CREATE INDEX IX_APO_ESTIP    ON APOLICE(CD_CNPJ_ESTIPULANTE);
CREATE INDEX IX_APO_SEG      ON APOLICE(CD_CPF_SEGURADO);
CREATE INDEX IX_FAT_COMP     ON FATURA(CD_COMPETENCIA);
CREATE INDEX IX_FAT_ESTIP    ON FATURA(CD_CNPJ_ESTIPULANTE);
CREATE INDEX IX_PAG_FAT      ON PAGAMENTO(NR_FATURA);
CREATE INDEX IX_PAG_NSU      ON PAGAMENTO(NR_NSU);
CREATE INDEX IX_CON_FAT      ON CONCILIACAO(NR_FATURA);
CREATE INDEX IX_DIS_NSU      ON DISPUTA(NR_NSU);
