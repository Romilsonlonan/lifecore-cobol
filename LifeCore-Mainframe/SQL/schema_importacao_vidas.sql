-- ================================================================
-- FILE   : schema_importacao_vidas.sql
-- DESCRICAO: Tabelas para importação de vidas via planilha.
--            Compartilhadas entre FastAPI e CICS/COBOL.
-- ================================================================

-- ----------------------------------------------------------------
-- IMPORTACAO_VIDAS — cabeçalho do lote importado
-- ----------------------------------------------------------------
CREATE TABLE IMPORTACAO_VIDAS (
    ID_IMPORTACAO       CHAR(36)        NOT NULL,
    NR_APOLICE          CHAR(14)        NOT NULL,
    CD_EMPRESA          INTEGER         NOT NULL,
    QT_REGISTROS        INTEGER         NOT NULL DEFAULT 0,
    QT_VALIDOS          INTEGER         NOT NULL DEFAULT 0,
    QT_ERROS            INTEGER         NOT NULL DEFAULT 0,
    QT_GRAVADOS         INTEGER         NOT NULL DEFAULT 0,
    CD_STATUS           CHAR(2)         NOT NULL DEFAULT 'PE',
    -- PE=Pendente · OK=Gravado · PA=Parcial · ER=Erro
    DT_IMPORTACAO       CHAR(8)         NOT NULL,
    ID_USUARIO          CHAR(8)         NOT NULL,
    TS_INCLUSAO         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT PK_IMP_VIDAS     PRIMARY KEY (ID_IMPORTACAO),
    CONSTRAINT FK_IV_EMP        FOREIGN KEY (CD_EMPRESA)
                                    REFERENCES EMPRESA(CD_EMPRESA),
    CONSTRAINT CK_IV_ST         CHECK (CD_STATUS IN ('PE','OK','PA','ER'))
);

-- ----------------------------------------------------------------
-- IMPORTACAO_VIDAS_ITEM — cada linha da planilha
-- ----------------------------------------------------------------
CREATE TABLE IMPORTACAO_VIDAS_ITEM (
    ID_IMPORTACAO       CHAR(36)        NOT NULL,
    NR_LINHA            INTEGER         NOT NULL,
    CD_CPF              CHAR(11)        NOT NULL,
    NM_SEGURADO         VARCHAR(60)     NOT NULL,
    CD_SUBESTIPULANTE   CHAR(10),
    CD_MODULO           CHAR(10),
    CD_CARGO            VARCHAR(30),
    VL_SALARIO          DECIMAL(13,2)   NOT NULL DEFAULT 0,
    NR_FATOR_MULT       DECIMAL(5,2)    NOT NULL DEFAULT 1,
    VL_CAPITAL          DECIMAL(15,2)   NOT NULL DEFAULT 0,
    DT_ADMISSAO         CHAR(8)         NOT NULL,
    CD_STATUS           CHAR(2)         NOT NULL DEFAULT 'OK',
    -- OK=Gravado · ER=Erro
    DS_ERRO             VARCHAR(200),
    CONSTRAINT PK_IMP_VIDAS_ITEM    PRIMARY KEY (ID_IMPORTACAO, NR_LINHA),
    CONSTRAINT FK_IVI_IMP           FOREIGN KEY (ID_IMPORTACAO)
                                        REFERENCES IMPORTACAO_VIDAS(ID_IMPORTACAO),
    CONSTRAINT CK_IVI_ST            CHECK (CD_STATUS IN ('OK','ER'))
);

-- Índices para consulta CICS
CREATE INDEX IX_IV_APOLICE     ON IMPORTACAO_VIDAS(NR_APOLICE);
CREATE INDEX IX_IV_EMPRESA     ON IMPORTACAO_VIDAS(CD_EMPRESA);
CREATE INDEX IX_IV_STATUS      ON IMPORTACAO_VIDAS(CD_STATUS);
CREATE INDEX IX_IVI_CPF        ON IMPORTACAO_VIDAS_ITEM(CD_CPF);
CREATE INDEX IX_IVI_SUB        ON IMPORTACAO_VIDAS_ITEM(CD_SUBESTIPULANTE);
