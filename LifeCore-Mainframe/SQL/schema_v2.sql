-- ================================================================
-- FILE   : schema_v2.sql
-- DESCRICAO: Schema v2 — Módulos completos do LifeCore-Mainframe
--            Baseado na análise do I4Pro (Prudential) + extensões
-- PROJETO: LifeCore-Mainframe
-- VERSAO : 2.0.0
--
-- Módulos cobertos:
--   Cadastros   : EMPRESA, CONGENERE, FILIAL, SEGURADO, GRUPO_USUARIO
--   Emissão     : PROPOSTA, APOLICE, COBERTURA, MATRICULA
--   Sinistro    : SINISTRO, SINISTRO_DOCUMENTO, KIT_SINISTRO
--   Financeiro  : FATURA, PAGAMENTO, CONCILIACAO, DISPUTA, COMISSAO
--   Parâmetros  : PARAMETRO_ROTINA, PARAMETRO_INTERFACE
--   ECM         : DOC_ECM, GRUPO_DOC_ECM
--   Controle    : CONTROLE_IMPRESSAO, PERMISSAO_FECHAMENTO
--   Audit       : AUDITORIA_ACAO
--
-- NOTA DB2/PostgreSQL: tipos CHAR(n) preservam largura fixa
-- compatível com os copybooks COBOL.
-- ================================================================

-- ================================================================
-- BLOCO 1 — CADASTROS
-- ================================================================

-- ----------------------------------------------------------------
-- EMPRESA (Estipulante / Seguradora / Congênere)
-- Referência: I4Pro › Cadastros › Empresa
-- Campos extras observados nas imagens:
--   Capital Vinculado, Capital Subscrito, Valor Aceite Cobrança
-- ----------------------------------------------------------------
CREATE TABLE EMPRESA (
    CD_EMPRESA          SERIAL          NOT NULL,
    NR_CODIGO           CHAR(6)         NOT NULL,           -- ex: 400
    NM_RAZAO_SOCIAL     VARCHAR(80)     NOT NULL,
    NM_NOME_REDUZIDO    VARCHAR(30),
    CD_CNPJ             CHAR(14)        NOT NULL,
    TP_EMPRESA          CHAR(2)         NOT NULL,           -- SE=Seguradora, ES=Estipulante, CO=Corretora, CN=Congenere
    NR_SUSEP            CHAR(10),
    VL_CAPITAL_VINCULADO    DECIMAL(15,2),
    VL_CAPITAL_SUBSCRITO    DECIMAL(15,2),
    VL_ACEITE_COBRANCA      DECIMAL(10,2),
    CD_STATUS           CHAR(2)         NOT NULL DEFAULT 'AT',  -- AT/IN
    DT_INCLUSAO         CHAR(8)         NOT NULL,
    ID_USUARIO_INCL     CHAR(8)         NOT NULL,
    TS_INCLUSAO         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    TS_ALTERACAO        TIMESTAMP,
    CONSTRAINT PK_EMPRESA        PRIMARY KEY (CD_EMPRESA),
    CONSTRAINT UK_EMPRESA_CNPJ   UNIQUE (CD_CNPJ),
    CONSTRAINT UK_EMPRESA_COD    UNIQUE (NR_CODIGO),
    CONSTRAINT CK_EMPRESA_TP     CHECK (TP_EMPRESA IN ('SE','ES','CO','CN','RE')),
    CONSTRAINT CK_EMPRESA_ST     CHECK (CD_STATUS IN ('AT','IN'))
);

-- ----------------------------------------------------------------
-- FILIAL (Filiais da Empresa)
-- Referência: I4Pro › Empresa › aba Filiais
-- ----------------------------------------------------------------
CREATE TABLE FILIAL (
    CD_FILIAL           SERIAL          NOT NULL,
    CD_EMPRESA          INTEGER         NOT NULL,
    NR_CODIGO           CHAR(6)         NOT NULL,
    NM_FILIAL           VARCHAR(60)     NOT NULL,
    CD_CNPJ             CHAR(14),
    CD_UF               CHAR(2),
    CD_STATUS           CHAR(2)         NOT NULL DEFAULT 'AT',
    DT_INCLUSAO         CHAR(8)         NOT NULL,
    CONSTRAINT PK_FILIAL    PRIMARY KEY (CD_FILIAL),
    CONSTRAINT FK_FIL_EMP   FOREIGN KEY (CD_EMPRESA) REFERENCES EMPRESA(CD_EMPRESA)
);

-- ----------------------------------------------------------------
-- CONGENERE (Resseguradoras / Congêneres / Parceiros)
-- Referência: I4Pro › Cadastros › Congêneres
-- Campos: Nº SUSEP, Congênere, Tipo de pessoa, Empresa
-- ----------------------------------------------------------------
CREATE TABLE CONGENERE (
    CD_CONGENERE        SERIAL          NOT NULL,
    NR_SUSEP            CHAR(10)        NOT NULL,
    NM_CONGENERE        VARCHAR(80)     NOT NULL,
    TP_PESSOA           CHAR(2)         NOT NULL,           -- PF=Física, PJ=Jurídica
    CD_EMPRESA          INTEGER,                            -- empresa vinculada
    CD_CNPJ_CPF         CHAR(14),
    CD_STATUS           CHAR(2)         NOT NULL DEFAULT 'AT',
    DT_INCLUSAO         CHAR(8)         NOT NULL,
    ID_USUARIO_INCL     CHAR(8)         NOT NULL,
    CONSTRAINT PK_CONGENERE  PRIMARY KEY (CD_CONGENERE),
    CONSTRAINT FK_CON_EMP    FOREIGN KEY (CD_EMPRESA) REFERENCES EMPRESA(CD_EMPRESA),
    CONSTRAINT CK_CON_TP     CHECK (TP_PESSOA IN ('PF','PJ'))
);

-- ----------------------------------------------------------------
-- SEGURADO
-- (mantida da v1, expandida com campos de matrícula e vínculo)
-- ----------------------------------------------------------------
CREATE TABLE SEGURADO (
    CD_CPF              CHAR(11)        NOT NULL,
    NM_SEGURADO         VARCHAR(60)     NOT NULL,
    DT_NASCIMENTO       CHAR(8)         NOT NULL,
    CD_SEXO             CHAR(1),                            -- M/F
    DS_EMAIL            VARCHAR(80),
    NR_TELEFONE         CHAR(15),
    CD_ESTADO_CIVIL     CHAR(2),                            -- SO/CA/DI/VI/UE
    CD_EMPRESA          INTEGER,                            -- empresa empregadora
    NR_MATRICULA        CHAR(10),                           -- matrícula no estipulante
    VL_SALARIO          DECIMAL(13,2),
    DT_ADMISSAO         CHAR(8),
    DT_INCLUSAO         CHAR(8)         NOT NULL,
    ID_USUARIO_INCL     CHAR(8)         NOT NULL,
    TS_INCLUSAO         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT PK_SEGURADO   PRIMARY KEY (CD_CPF),
    CONSTRAINT FK_SEG_EMP    FOREIGN KEY (CD_EMPRESA) REFERENCES EMPRESA(CD_EMPRESA)
);

-- ----------------------------------------------------------------
-- GRUPO_USUARIO (Perfis de acesso — RBAC)
-- Referência: I4Pro › Empresa › Permissão Fechamento
-- Grupos vistos: Administrador, Aceitação, Auditoria, Cobrança,
--   Comercial, Compliance, Contabilidade, Ouvidoria, etc.
-- ----------------------------------------------------------------
CREATE TABLE GRUPO_USUARIO (
    CD_GRUPO            SERIAL          NOT NULL,
    NM_GRUPO            VARCHAR(40)     NOT NULL,
    DS_DESCRICAO        VARCHAR(100),
    FL_ATIVO            CHAR(1)         NOT NULL DEFAULT 'S',
    TS_INCLUSAO         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT PK_GRUPO  PRIMARY KEY (CD_GRUPO),
    CONSTRAINT UK_GRUPO  UNIQUE (NM_GRUPO)
);

-- Seed dos grupos observados no I4Pro
INSERT INTO GRUPO_USUARIO (NM_GRUPO, DS_DESCRICAO) VALUES
  ('Administrador',          'Acesso total ao sistema'),
  ('Aceitação',              'Análise e aceitação de propostas'),
  ('Auditoria',              'Auditoria de dados e processos'),
  ('Cobrança',               'Módulo de cobrança e faturamento'),
  ('Cadastro',               'Manutenção de cadastros'),
  ('Cadastro Sinistro',      'Abertura e gestão de sinistros'),
  ('Comercial',              'Equipe comercial e corretores'),
  ('Comercial SMT',          'Comercial segmento SMT'),
  ('Compliance',             'Conformidade e regulatório'),
  ('Contabilidade',          'Módulo contábil e conciliação'),
  ('Ouvidoria',              'Atendimento e ouvidoria'),
  ('Prestadora de Bem',      'Prestadores de serviço'),
  ('Serviços e Reembolso',   'Reembolso e assistências'),
  ('Suporte Consultoria',    'TI e suporte técnico'),
  ('Usuário Master',         'Superusuário — acesso irrestrito');

-- ================================================================
-- BLOCO 2 — EMISSÃO
-- ================================================================

-- ----------------------------------------------------------------
-- PROPOSTA (antecede a apólice — pipeline de aceitação)
-- Referência: I4Pro › Painel › Pipeline de Aceitação
-- Status: Em análise / Aceitação automática / Pendente doc / Recusada
-- ----------------------------------------------------------------
CREATE TABLE PROPOSTA (
    NR_PROPOSTA         CHAR(14)        NOT NULL,           -- ex: 2026.PROP.007109
    CD_EMPRESA          INTEGER         NOT NULL,
    CD_CPF_SEGURADO     CHAR(11)        NOT NULL,
    CD_PRODUTO          CHAR(3)         NOT NULL,           -- VGC/GLB
    TP_CAPITAL          CHAR(1)         NOT NULL,
    VL_CAPITAL          DECIMAL(15,2)   NOT NULL,
    VL_SALARIO_BASE     DECIMAL(13,2),
    NR_FATOR_MULT       DECIMAL(5,2),
    VL_PREMIO_LIQUIDO   DECIMAL(13,2),
    VL_PREMIO_BRUTO     DECIMAL(13,2),
    CD_STATUS           CHAR(2)         NOT NULL DEFAULT 'AN',
    -- AN=Em análise, AA=Aceitação auto, PD=Pendente doc,
    -- AC=Aceita, RC=Recusada, CA=Cancelada
    TP_ACEITE           CHAR(2),                            -- AU=Automático, MA=Manual
    DT_PROPOSTA         CHAR(8)         NOT NULL,
    DT_ACEITE           CHAR(8),
    DT_RECUSA           CHAR(8),
    CD_MOTIVO_RECUSA    CHAR(4),
    DS_MOTIVO_RECUSA    VARCHAR(100),
    NR_DIAS_ANALISE     SMALLINT        DEFAULT 15,
    ID_USUARIO_INCL     CHAR(8)         NOT NULL,
    ID_USUARIO_ACEITE   CHAR(8),
    TS_INCLUSAO         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    TS_ALTERACAO        TIMESTAMP,
    CONSTRAINT PK_PROPOSTA   PRIMARY KEY (NR_PROPOSTA),
    CONSTRAINT FK_PROP_EMP   FOREIGN KEY (CD_EMPRESA) REFERENCES EMPRESA(CD_EMPRESA),
    CONSTRAINT FK_PROP_SEG   FOREIGN KEY (CD_CPF_SEGURADO) REFERENCES SEGURADO(CD_CPF),
    CONSTRAINT CK_PROP_ST    CHECK (CD_STATUS IN ('AN','AA','PD','AC','RC','CA')),
    CONSTRAINT CK_PROP_PROD  CHECK (CD_PRODUTO IN ('VGC','GLB'))
);

-- ----------------------------------------------------------------
-- APOLICE (expandida da v1 — vínculo com proposta e matrícula)
-- Referência: I4Pro › Emissão › ex: 2026.APL.882314
-- ----------------------------------------------------------------
CREATE TABLE APOLICE (
    NR_APOLICE          CHAR(14)        NOT NULL,           -- ex: 2026.APL.882314
    NR_PROPOSTA         CHAR(14),
    CD_EMPRESA          INTEGER         NOT NULL,
    CD_CPF_SEGURADO     CHAR(11)        NOT NULL,
    CD_PRODUTO          CHAR(3)         NOT NULL,
    TP_CAPITAL          CHAR(1)         NOT NULL,
    VL_CAPITAL_SEGURADO DECIMAL(15,2)   NOT NULL,
    VL_SALARIO_BASE     DECIMAL(13,2),
    NR_FATOR_MULT       DECIMAL(5,2),
    VL_PREMIO_LIQUIDO   DECIMAL(13,2)   NOT NULL,
    VL_PREMIO_BRUTO     DECIMAL(13,2)   NOT NULL,
    VL_IOF              DECIMAL(11,2),
    VL_IPCA_APLICADO    DECIMAL(5,4),                       -- IPCA do reajuste
    TP_FORMA_PAGAMENTO  CHAR(2)         NOT NULL,
    TP_PERIODICIDADE    CHAR(2)         NOT NULL,
    NR_MATRICULA        CHAR(10),                           -- sequencial matrícula
    DT_VIGENCIA_INI     CHAR(8)         NOT NULL,
    DT_VIGENCIA_FIM     CHAR(8)         NOT NULL,
    DT_EMISSAO          CHAR(8)         NOT NULL,
    CD_STATUS           CHAR(2)         NOT NULL DEFAULT 'AT',
    ID_USUARIO_EMISSAO  CHAR(8)         NOT NULL,
    TS_INCLUSAO         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    TS_ALTERACAO        TIMESTAMP,
    CONSTRAINT PK_APOLICE    PRIMARY KEY (NR_APOLICE),
    CONSTRAINT FK_APO_EMP    FOREIGN KEY (CD_EMPRESA) REFERENCES EMPRESA(CD_EMPRESA),
    CONSTRAINT FK_APO_SEG    FOREIGN KEY (CD_CPF_SEGURADO) REFERENCES SEGURADO(CD_CPF),
    CONSTRAINT FK_APO_PROP   FOREIGN KEY (NR_PROPOSTA) REFERENCES PROPOSTA(NR_PROPOSTA),
    CONSTRAINT CK_APO_PROD   CHECK (CD_PRODUTO IN ('VGC','GLB')),
    CONSTRAINT CK_APO_ST     CHECK (CD_STATUS IN ('AT','CA','SU','EX')),
    CONSTRAINT CK_APO_CAP    CHECK (TP_CAPITAL IN ('F','E','M','B','P')),
    CONSTRAINT CK_APO_PGTO   CHECK (TP_FORMA_PAGAMENTO IN ('BO','CC','DB'))
);

-- ----------------------------------------------------------------
-- COBERTURA
-- ----------------------------------------------------------------
CREATE TABLE COBERTURA (
    CD_COBERTURA        CHAR(16)        NOT NULL,
    NR_APOLICE          CHAR(14)        NOT NULL,
    CD_TIPO             CHAR(4)         NOT NULL,   -- MORT/INVA/DIT/DM/VIAG
    NM_COBERTURA        VARCHAR(60)     NOT NULL,
    VL_CAPITAL          DECIMAL(15,2)   NOT NULL,
    NR_CARENCIA_DIAS    SMALLINT        DEFAULT 0,
    CD_STATUS           CHAR(2)         NOT NULL DEFAULT 'AT',
    CONSTRAINT PK_COBERTURA  PRIMARY KEY (CD_COBERTURA),
    CONSTRAINT FK_COB_APO    FOREIGN KEY (NR_APOLICE) REFERENCES APOLICE(NR_APOLICE)
);

-- ----------------------------------------------------------------
-- MATRICULA (sequencial de matrícula por empresa)
-- Referência: I4Pro › Parâmetros Rotinas
-- ----------------------------------------------------------------
CREATE TABLE MATRICULA_SEQ (
    CD_EMPRESA          INTEGER         NOT NULL,
    NR_SEQ_INICIAL      INTEGER         NOT NULL DEFAULT 1,
    NR_SEQ_FINAL        INTEGER         NOT NULL DEFAULT 999999,
    NR_SEQ_ATUAL        INTEGER         NOT NULL DEFAULT 1,
    DT_ALTERACAO        CHAR(8),
    ID_USUARIO          CHAR(8),
    CONSTRAINT PK_MATSEQ  PRIMARY KEY (CD_EMPRESA),
    CONSTRAINT FK_MAT_EMP FOREIGN KEY (CD_EMPRESA) REFERENCES EMPRESA(CD_EMPRESA)
);

-- ================================================================
-- BLOCO 3 — SINISTRO
-- ================================================================

-- ----------------------------------------------------------------
-- SINISTRO
-- Referência: I4Pro › Sinistro (ex: 2026.SIN.008420)
-- ----------------------------------------------------------------
CREATE TABLE SINISTRO (
    NR_SINISTRO         CHAR(14)        NOT NULL,           -- ex: 2026.SIN.008420
    NR_APOLICE          CHAR(14)        NOT NULL,
    CD_CPF_SEGURADO     CHAR(11)        NOT NULL,
    CD_EMPRESA          INTEGER         NOT NULL,
    CD_TIPO_EVENTO      CHAR(4)         NOT NULL,
    -- MORT=Morte, INVA=Invalidez, DIT=DIT, VIAG=Viagem, DMH=Desp.Med.
    NM_TIPO_EVENTO      VARCHAR(60),
    DT_EVENTO           CHAR(8)         NOT NULL,
    DT_ABERTURA         CHAR(8)         NOT NULL,
    DT_ENCERRAMENTO     CHAR(8),
    VL_CAPITAL_AVERBADO DECIMAL(15,2),
    VL_INDENIZACAO      DECIMAL(15,2),
    VL_PAGO             DECIMAL(15,2)   DEFAULT 0,
    CD_STATUS           CHAR(2)         NOT NULL DEFAULT 'AB',
    -- AB=Aberto, AN=Em análise, PG=Pago, EN=Encerrado, RC=Recusado
    DS_OBSERVACAO       VARCHAR(200),
    ID_USUARIO_INCL     CHAR(8)         NOT NULL,
    TS_INCLUSAO         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    TS_ALTERACAO        TIMESTAMP,
    CONSTRAINT PK_SINISTRO   PRIMARY KEY (NR_SINISTRO),
    CONSTRAINT FK_SIN_APO    FOREIGN KEY (NR_APOLICE) REFERENCES APOLICE(NR_APOLICE),
    CONSTRAINT FK_SIN_SEG    FOREIGN KEY (CD_CPF_SEGURADO) REFERENCES SEGURADO(CD_CPF),
    CONSTRAINT FK_SIN_EMP    FOREIGN KEY (CD_EMPRESA) REFERENCES EMPRESA(CD_EMPRESA),
    CONSTRAINT CK_SIN_ST     CHECK (CD_STATUS IN ('AB','AN','PG','EN','RC'))
);

-- ----------------------------------------------------------------
-- KIT_SINISTRO (documentos do kit — visto na aba ECM do I4Pro)
-- Referência: I4Pro › Empresa › Documentos ECM
-- Tipos: OAM Kit Sinistro, Kits de Sinistro
-- ----------------------------------------------------------------
CREATE TABLE KIT_SINISTRO (
    CD_KIT              SERIAL          NOT NULL,
    NR_SINISTRO         CHAR(14)        NOT NULL,
    NM_TIPO_KIT         VARCHAR(40)     NOT NULL,           -- ex: OAM Kit Sinistro
    NM_DOCUMENTO        VARCHAR(100)    NOT NULL,
    NM_ARQUIVO          VARCHAR(200),
    DS_OBSERVACAO       VARCHAR(100),
    CD_STATUS           CHAR(2)         NOT NULL DEFAULT 'PE', -- PE/EN/OK
    DT_INCLUSAO         CHAR(8)         NOT NULL,
    ID_USUARIO_INCL     CHAR(8)         NOT NULL,
    CONSTRAINT PK_KIT       PRIMARY KEY (CD_KIT),
    CONSTRAINT FK_KIT_SIN   FOREIGN KEY (NR_SINISTRO) REFERENCES SINISTRO(NR_SINISTRO)
);

-- ================================================================
-- BLOCO 4 — FINANCEIRO (mantido da v1 + expansões)
-- ================================================================

CREATE TABLE FATURA (
    NR_FATURA           CHAR(14)        NOT NULL,
    CD_EMPRESA          INTEGER         NOT NULL,
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
    NR_REMESSA          INTEGER,                            -- número de remessa SUSEP
    ID_USUARIO_EMISSAO  CHAR(8),
    TS_INCLUSAO         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT PK_FATURA    PRIMARY KEY (NR_FATURA),
    CONSTRAINT FK_FAT_EMP   FOREIGN KEY (CD_EMPRESA) REFERENCES EMPRESA(CD_EMPRESA),
    CONSTRAINT CK_FAT_ST    CHECK (CD_STATUS IN ('PE','PG','PP','AT','CA'))
);

CREATE TABLE PAGAMENTO (
    NR_PAGAMENTO        CHAR(16)        NOT NULL,
    NR_FATURA           CHAR(14)        NOT NULL,
    DT_PAGAMENTO        CHAR(8)         NOT NULL,
    VL_PAGAMENTO        DECIMAL(15,2)   NOT NULL,
    TP_FORMA            CHAR(2)         NOT NULL,
    CD_STATUS           CHAR(2)         NOT NULL DEFAULT 'CF',
    CD_BANDEIRA         CHAR(4),
    DS_TOKEN_CARTAO     CHAR(32),
    NR_CARTAO_ULTIMOS4  CHAR(4),
    NR_NSU              CHAR(12),
    CD_AUTORIZACAO      CHAR(6),
    DS_ADQUIRENTE       CHAR(8),
    TS_INCLUSAO         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT PK_PAGAMENTO  PRIMARY KEY (NR_PAGAMENTO),
    CONSTRAINT FK_PAG_FAT    FOREIGN KEY (NR_FATURA) REFERENCES FATURA(NR_FATURA),
    CONSTRAINT CK_PAG_ST     CHECK (CD_STATUS IN ('CF','CA','ES','CB')),
    CONSTRAINT CK_PAG_FORMA  CHECK (TP_FORMA IN ('BO','CC','DB'))
);

CREATE TABLE CONCILIACAO (
    NR_CONCILIACAO      CHAR(16)        NOT NULL,
    NR_FATURA           CHAR(14)        NOT NULL,
    NR_PAGAMENTO        CHAR(16),
    DT_CONCILIACAO      CHAR(8)         NOT NULL,
    VL_FATURADO         DECIMAL(15,2)   NOT NULL,
    VL_PAGO             DECIMAL(15,2)   NOT NULL DEFAULT 0,
    VL_DIFERENCA        DECIMAL(13,2)   NOT NULL DEFAULT 0,
    CD_STATUS           CHAR(2)         NOT NULL,
    NR_NSU              CHAR(12),
    CD_CICLO_CLEARING   CHAR(8),
    ID_USUARIO          CHAR(8),
    TS_INCLUSAO         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT PK_CONCIL     PRIMARY KEY (NR_CONCILIACAO),
    CONSTRAINT FK_CON_FAT    FOREIGN KEY (NR_FATURA) REFERENCES FATURA(NR_FATURA),
    CONSTRAINT CK_CON_ST     CHECK (CD_STATUS IN ('OK','DV','SP','SF','DU','CB'))
);

CREATE TABLE DISPUTA (
    NR_DISPUTA          INTEGER         NOT NULL,
    NR_NSU              CHAR(12)        NOT NULL,
    TP_DISPUTA          CHAR(4)         NOT NULL,
    VL_DISPUTA          DECIMAL(15,2)   NOT NULL,
    DT_ABERTURA         CHAR(8)         NOT NULL,
    CD_STATUS           CHAR(2)         NOT NULL DEFAULT 'AB',
    DS_OBSERVACAO       VARCHAR(200),
    TS_INCLUSAO         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT PK_DISPUTA  PRIMARY KEY (NR_DISPUTA),
    CONSTRAINT CK_DIS_ST   CHECK (CD_STATUS IN ('AB','EN','GA','PE'))
);

-- ================================================================
-- BLOCO 5 — PARÂMETROS
-- ================================================================

-- ----------------------------------------------------------------
-- PARAMETRO_ROTINA
-- Referência: I4Pro › Empresa › Parâmetros rotinas
-- ----------------------------------------------------------------
CREATE TABLE PARAMETRO_ROTINA (
    CD_EMPRESA              INTEGER         NOT NULL,
    FL_APENAS_DIAS_UTEIS    CHAR(1)         NOT NULL DEFAULT 'S',
    NR_DIAS_ACEITACAO_AUTO  SMALLINT        NOT NULL DEFAULT 15,
    CD_STATUS_ACEITACAO     CHAR(2)         NOT NULL DEFAULT 'AN',
    DS_MOTIVO_ACEIT_AUTO    VARCHAR(60)     DEFAULT 'Iniciativa da empresa',
    NR_DIAS_RECUSA_LEGAL    SMALLINT        NOT NULL DEFAULT 15,
    NR_DIAS_RECUSA_AUTO     SMALLINT        NOT NULL DEFAULT 13,
    CD_STATUS_RECUSA_AUTO   CHAR(2)         NOT NULL DEFAULT 'RC',
    DS_MOTIVO_RECUSA_AUTO   VARCHAR(60)     DEFAULT 'Fora da política de aceitação',
    TP_PERIODO_XML          CHAR(5)         DEFAULT 'Diário',
    DT_ALTERACAO            CHAR(8),
    ID_USUARIO              CHAR(8),
    TS_INCLUSAO             TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT PK_PARM_ROT  PRIMARY KEY (CD_EMPRESA),
    CONSTRAINT FK_PR_EMP    FOREIGN KEY (CD_EMPRESA) REFERENCES EMPRESA(CD_EMPRESA)
);

-- ----------------------------------------------------------------
-- PARAMETRO_INTERFACE
-- Referência: I4Pro › Empresa › Parâmetros Interface
-- Parâmetros observados nas imagens (20 linhas visíveis)
-- ----------------------------------------------------------------
CREATE TABLE PARAMETRO_INTERFACE (
    CD_PARAMETRO        SERIAL          NOT NULL,
    CD_EMPRESA          INTEGER         NOT NULL,
    CD_CODIGO           CHAR(40)        NOT NULL,
    DS_DESCRICAO        VARCHAR(100)    NOT NULL,
    VL_VALOR            VARCHAR(300)    NOT NULL,           -- path, email, flag
    TP_PARAMETRO        CHAR(3)         NOT NULL DEFAULT 'STR', -- STR/NUM/FLG/PTH
    FL_ATIVO            CHAR(1)         NOT NULL DEFAULT 'S',
    ID_USUARIO_INCL     CHAR(8),
    TS_INCLUSAO         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    TS_ALTERACAO        TIMESTAMP,
    CONSTRAINT PK_PARM_INT  PRIMARY KEY (CD_PARAMETRO),
    CONSTRAINT FK_PI_EMP    FOREIGN KEY (CD_EMPRESA) REFERENCES EMPRESA(CD_EMPRESA),
    CONSTRAINT UK_PI_COD    UNIQUE (CD_EMPRESA, CD_CODIGO)
);

-- Seed dos parâmetros observados no I4Pro (imagem 8)
INSERT INTO PARAMETRO_INTERFACE (CD_EMPRESA, CD_CODIGO, DS_DESCRICAO, VL_VALOR, TP_PARAMETRO) VALUES
  (1, 'PATH_ARQ_FATURAMENTO_EMISSAO',   'Diretório arquivo faturamento emissão',         '/interfaces/faturamento/emissao', 'PTH'),
  (1, 'INTERFACE_SUSEP_CORRETOR_MES',   'Caminho interface SUSEP corretores mensal',     '/interfaces/susep/corretor_mes',  'PTH'),
  (1, 'ASSISTENCIAS',                   'Diretório arquivo TXT Assistências',            '/interfaces/assistencias',        'PTH'),
  (1, 'GLOBAL_INTERFACE',               'Diretório Global Interface',                    '/interfaces/global',              'PTH'),
  (1, 'INTERFACE_SUSEP_CORRETOR_FILIAIS','Interface SUSEP corretoras filiais',           '/interfaces/susep/filiais',       'PTH'),
  (1, 'IMPORTACAO_CARGA_PASTA_JUDICIAL','Importação pasta judicial',                     '/interfaces/judicial',            'PTH'),
  (1, 'ARQ_FATU_ODEBRECHT',            'Arquivo Faturamento Odebrecht',                 '/interfaces/odebrecht/fatura',    'PTH'),
  (1, 'ARQ_EMISS_ODEBRECHT',           'Arquivo Emissão Odebrecht',                     '/interfaces/odebrecht/emissao',   'PTH'),
  (1, 'EXP_RETORNO_PAG_SIN_JUD',       'Arquivo Retorno pagamento sinistro judicial',   '/interfaces/judicial/retorno',    'PTH'),
  (1, 'EXPORT_CAP_ICATU',              'Exportação remessa ICATU',                      '/interfaces/icatu/cap',           'PTH'),
  (1, 'DESTINATARIO_EMAIL_ARQ_FATURAMENTO','E-mail destinatário arquivo faturamento',   'faturamento@lifecore.com.br',     'STR'),
  (1, 'ARQ_PATH_FATURAMENTO',          'Arquivo Faturamento',                           '/interfaces/faturamento',         'PTH'),
  (1, 'NM_PATH_IMP_SIGES_SUCES',       'Diretório importação SIGES sucesso',            '/interfaces/siges/sucesso',       'PTH'),
  (1, 'NM_PATH_IMP_SIGES_ERRO',        'Diretório importação SIGES erro',               '/interfaces/siges/erro',          'PTH');

-- ================================================================
-- BLOCO 6 — ECM (Documentos Eletrônicos)
-- ================================================================

-- ----------------------------------------------------------------
-- GRUPO_DOC_ECM
-- Referência: I4Pro › ECM (Grupo de documento / Tipo)
-- ----------------------------------------------------------------
CREATE TABLE GRUPO_DOC_ECM (
    CD_GRUPO_ECM        SERIAL          NOT NULL,
    NM_GRUPO            VARCHAR(40)     NOT NULL,           -- ex: OAM Kit Sinistro
    NM_TIPO             VARCHAR(40)     NOT NULL,           -- ex: Kits de Sinistro
    DS_DESCRICAO        VARCHAR(100),
    FL_ATIVO            CHAR(1)         NOT NULL DEFAULT 'S',
    CONSTRAINT PK_GRUPO_ECM  PRIMARY KEY (CD_GRUPO_ECM)
);

INSERT INTO GRUPO_DOC_ECM (NM_GRUPO, NM_TIPO) VALUES
  ('OAM Kit Sinistro', 'Kits de Sinistro'),
  ('OAM Emissão',      'Documentos Emissão'),
  ('OAM Cadastro',     'Documentos Cadastrais'),
  ('OAM Cobrança',     'Documentos Cobrança');

-- ----------------------------------------------------------------
-- DOC_ECM (Documentos ECM por empresa/sinistro/apólice)
-- Referência: I4Pro › Empresa › Documentos ECM
-- ----------------------------------------------------------------
CREATE TABLE DOC_ECM (
    CD_DOC_ECM          SERIAL          NOT NULL,
    CD_GRUPO_ECM        INTEGER         NOT NULL,
    CD_EMPRESA          INTEGER,
    NR_APOLICE          CHAR(14),
    NR_SINISTRO         CHAR(14),
    NR_REF              CHAR(10),
    NM_ARQUIVO          VARCHAR(200)    NOT NULL,
    DS_OBSERVACAO       VARCHAR(100),
    DT_GRAVACAO         CHAR(8)         NOT NULL,
    HR_GRAVACAO         CHAR(5),
    ID_USUARIO_INCL     CHAR(8)         NOT NULL,
    FL_SELECIONADO      CHAR(1)         DEFAULT 'N',
    TS_INCLUSAO         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT PK_DOC_ECM    PRIMARY KEY (CD_DOC_ECM),
    CONSTRAINT FK_ECM_GRP    FOREIGN KEY (CD_GRUPO_ECM) REFERENCES GRUPO_DOC_ECM(CD_GRUPO_ECM),
    CONSTRAINT FK_ECM_EMP    FOREIGN KEY (CD_EMPRESA) REFERENCES EMPRESA(CD_EMPRESA)
);

-- ================================================================
-- BLOCO 7 — CONTROLE OPERACIONAL
-- ================================================================

-- ----------------------------------------------------------------
-- CONTROLE_IMPRESSAO
-- Referência: I4Pro › Empresa › Controle das Impressões
-- Módulos: Emissão, Fechamento Diário
-- ----------------------------------------------------------------
CREATE TABLE CONTROLE_IMPRESSAO (
    CD_CONTROLE         SERIAL          NOT NULL,
    CD_EMPRESA          INTEGER         NOT NULL,
    NM_MODULO           VARCHAR(30)     NOT NULL,           -- Emissão / Fechamento Diário
    DT_MOVIMENTO_CONTABIL CHAR(8)       NOT NULL,
    NR_PENDENTES        INTEGER         NOT NULL DEFAULT 0,
    NR_GERADOS          INTEGER         NOT NULL DEFAULT 0,
    NR_NAO_GERADOS      INTEGER         NOT NULL DEFAULT 0,
    TS_PROCESSAMENTO    TIMESTAMP,
    CONSTRAINT PK_CTRL_IMP   PRIMARY KEY (CD_CONTROLE),
    CONSTRAINT FK_CI_EMP     FOREIGN KEY (CD_EMPRESA) REFERENCES EMPRESA(CD_EMPRESA)
);

-- ----------------------------------------------------------------
-- PERMISSAO_FECHAMENTO
-- Referência: I4Pro › Empresa › Permissão Fechamento
-- ----------------------------------------------------------------
CREATE TABLE PERMISSAO_FECHAMENTO (
    CD_EMPRESA          INTEGER         NOT NULL,
    CD_GRUPO            INTEGER         NOT NULL,
    FL_SELECIONADO      CHAR(1)         NOT NULL DEFAULT 'N',
    ID_USUARIO_INCL     CHAR(8),
    TS_ALTERACAO        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT PK_PERM_FECH  PRIMARY KEY (CD_EMPRESA, CD_GRUPO),
    CONSTRAINT FK_PF_EMP     FOREIGN KEY (CD_EMPRESA) REFERENCES EMPRESA(CD_EMPRESA),
    CONSTRAINT FK_PF_GRP     FOREIGN KEY (CD_GRUPO) REFERENCES GRUPO_USUARIO(CD_GRUPO)
);

-- ================================================================
-- BLOCO 8 — AUDITORIA
-- Referência: I4Pro › Empresa › Auditor de dados
-- Registra todas as ações: Emissão, Sinistro, Aceitação, Rotina, ECM
-- ================================================================
CREATE TABLE AUDITORIA_ACAO (
    CD_AUDITORIA        BIGSERIAL       NOT NULL,
    CD_EMPRESA          INTEGER,
    ID_USUARIO          CHAR(8)         NOT NULL,
    DT_HORA_ACAO        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    NM_MODULO           VARCHAR(20)     NOT NULL,
    -- Emissão / Sinistro / Aceitação / Cadastro / Cobrança / Rotina / ECM
    NM_ACAO             VARCHAR(40)     NOT NULL,
    NR_REFERENCIA       VARCHAR(20),                        -- nr apólice / sinistro / proposta
    DS_DETALHE          VARCHAR(200),
    CD_IP               CHAR(15),
    CONSTRAINT PK_AUDIT  PRIMARY KEY (CD_AUDITORIA)
);

-- ================================================================
-- ÍNDICES GERAIS
-- ================================================================
CREATE INDEX IX_EMP_CNPJ        ON EMPRESA(CD_CNPJ);
CREATE INDEX IX_EMP_TP          ON EMPRESA(TP_EMPRESA);
CREATE INDEX IX_PROP_EMP        ON PROPOSTA(CD_EMPRESA);
CREATE INDEX IX_PROP_ST         ON PROPOSTA(CD_STATUS);
CREATE INDEX IX_PROP_SEG        ON PROPOSTA(CD_CPF_SEGURADO);
CREATE INDEX IX_APO_EMP         ON APOLICE(CD_EMPRESA);
CREATE INDEX IX_APO_SEG         ON APOLICE(CD_CPF_SEGURADO);
CREATE INDEX IX_APO_ST          ON APOLICE(CD_STATUS);
CREATE INDEX IX_APO_VIG         ON APOLICE(DT_VIGENCIA_INI, DT_VIGENCIA_FIM);
CREATE INDEX IX_SIN_APO         ON SINISTRO(NR_APOLICE);
CREATE INDEX IX_SIN_ST          ON SINISTRO(CD_STATUS);
CREATE INDEX IX_SIN_DT          ON SINISTRO(DT_ABERTURA);
CREATE INDEX IX_FAT_EMP         ON FATURA(CD_EMPRESA);
CREATE INDEX IX_FAT_COMP        ON FATURA(CD_COMPETENCIA);
CREATE INDEX IX_FAT_ST          ON FATURA(CD_STATUS);
CREATE INDEX IX_PAG_FAT         ON PAGAMENTO(NR_FATURA);
CREATE INDEX IX_PAG_NSU         ON PAGAMENTO(NR_NSU);
CREATE INDEX IX_CON_FAT         ON CONCILIACAO(NR_FATURA);
CREATE INDEX IX_PARM_COD        ON PARAMETRO_INTERFACE(CD_CODIGO);
CREATE INDEX IX_DOC_EMP         ON DOC_ECM(CD_EMPRESA);
CREATE INDEX IX_DOC_SIN         ON DOC_ECM(NR_SINISTRO);
CREATE INDEX IX_AUD_USR         ON AUDITORIA_ACAO(ID_USUARIO);
CREATE INDEX IX_AUD_DT          ON AUDITORIA_ACAO(DT_HORA_ACAO);
CREATE INDEX IX_AUD_MOD         ON AUDITORIA_ACAO(NM_MODULO);
