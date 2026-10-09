-- ================================================================
-- MIGRATION 002 — Tabelas para os módulos migrados de in-memory
-- Supabase (PostgreSQL)
-- Executar em: Supabase Dashboard → SQL Editor
-- ================================================================

-- ── PROPOSTA ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS propostas (
    nr_proposta         TEXT            PRIMARY KEY,
    cd_empresa          INTEGER         NOT NULL DEFAULT 0,
    cd_cpf_segurado     TEXT            NOT NULL DEFAULT '',
    cd_produto          TEXT            NOT NULL DEFAULT 'VGC',
    tp_capital          TEXT            NOT NULL DEFAULT 'F',
    vl_capital          NUMERIC(15,2)   NOT NULL DEFAULT 0,
    vl_salario_base     NUMERIC(13,2),
    nr_fator_mult       NUMERIC(5,2),
    vl_premio_bruto     NUMERIC(13,2),
    vl_premio_liquido   NUMERIC(13,2),
    cd_status           TEXT            NOT NULL DEFAULT 'AN',
    tp_aceite           TEXT,
    dt_proposta         TEXT            NOT NULL,
    dt_aceite           TEXT,
    dt_recusa           TEXT,
    cd_motivo_recusa    TEXT,
    ds_motivo_recusa    TEXT,
    nr_dias_analise     INTEGER         NOT NULL DEFAULT 15,
    id_usuario          TEXT            NOT NULL DEFAULT 'SYSTEM',
    nr_apolice_gerada   TEXT,
    ts_inclusao         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    ts_alteracao        TIMESTAMPTZ
);

-- ── APOLICE ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS apolices (
    nr_apolice          TEXT            PRIMARY KEY,
    nr_proposta         TEXT,
    cd_empresa          INTEGER         NOT NULL DEFAULT 0,
    cd_cpf_segurado     TEXT            NOT NULL DEFAULT '',
    cd_produto          TEXT            NOT NULL DEFAULT 'VGC',
    tp_capital          TEXT            NOT NULL DEFAULT 'F',
    vl_capital          NUMERIC(15,2)   NOT NULL DEFAULT 0,
    vl_salario_base     NUMERIC(13,2),
    nr_fator_mult       NUMERIC(5,2),
    vl_premio_bruto     NUMERIC(13,2),
    vl_premio_liquido   NUMERIC(13,2),
    dt_emissao          TEXT            NOT NULL,
    dt_inicio_vigencia  TEXT            NOT NULL,
    dt_fim_vigencia     TEXT,
    cd_status           TEXT            NOT NULL DEFAULT 'AT',
    id_usuario_emissao  TEXT            NOT NULL DEFAULT 'SYSTEM',
    id_usuario_aceit    TEXT,
    ts_inclusao         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    ts_alteracao        TIMESTAMPTZ
);

-- ── TAXA IPCA ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS taxas_ipca (
    cd_competencia      TEXT            PRIMARY KEY,  -- AAAAMM
    vl_taxa_ipca        NUMERIC(8,4)    NOT NULL,
    vl_taxa_acumulada   NUMERIC(8,4),
    dt_divulgacao       TEXT,
    ds_fonte            TEXT            NOT NULL DEFAULT 'IBGE/IPCA',
    fl_vigente          BOOLEAN         NOT NULL DEFAULT FALSE,
    ts_inclusao         TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Seed das taxas reais 2025
INSERT INTO taxas_ipca (cd_competencia, vl_taxa_ipca, vl_taxa_acumulada, dt_divulgacao, fl_vigente)
VALUES
  ('202501', 0.16, 4.83, '20250212', FALSE),
  ('202502', 1.31, 5.06, '20250312', FALSE),
  ('202503', 0.56, 5.48, '20250410', FALSE),
  ('202504', 0.43, 5.53, '20250514', FALSE),
  ('202505', 0.43, 5.30, '20250612', FALSE),
  ('202506', 0.24, 5.35, '20250710', FALSE),
  ('202507', 0.38, 4.50, '20250813', TRUE)
ON CONFLICT (cd_competencia) DO NOTHING;

-- ── ENDOSSO ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS endossos (
    nr_endosso          TEXT            PRIMARY KEY,
    nr_apolice          TEXT            NOT NULL,
    cd_cpf_segurado     TEXT            NOT NULL,
    nm_segurado         TEXT,
    tp_endosso          TEXT            NOT NULL,
    vl_capital          NUMERIC(15,2),
    vl_salario_base     NUMERIC(13,2),
    nr_fator_mult       NUMERIC(5,2),
    dt_inicio_vigencia  TEXT,
    cd_status           TEXT            NOT NULL DEFAULT 'PROCESSADO',
    vl_capital_calculado NUMERIC(15,2),
    vl_premio_calculado  NUMERIC(13,2),
    id_usuario          TEXT            NOT NULL DEFAULT 'SYSTEM',
    ts_inclusao         TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_endossos_apolice ON endossos(nr_apolice);

-- ── FATURA ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS faturas (
    nr_fatura           TEXT            PRIMARY KEY,
    nr_apolice          TEXT            NOT NULL,
    cd_empresa          INTEGER         NOT NULL DEFAULT 0,
    cd_competencia      TEXT            NOT NULL,  -- AAAAMM
    dt_emissao          TEXT            NOT NULL,
    dt_vencimento       TEXT,
    forma_cobranca      TEXT,
    vl_total_bruto      NUMERIC(15,2)   NOT NULL DEFAULT 0,
    vl_total_liquido    NUMERIC(15,2)   NOT NULL DEFAULT 0,
    vl_reajuste_ipca    NUMERIC(13,2)   NOT NULL DEFAULT 0,
    nr_segurados        INTEGER         NOT NULL DEFAULT 0,
    itens               JSONB           NOT NULL DEFAULT '[]',
    cd_status           TEXT            NOT NULL DEFAULT 'EM_ABERTO',
    ts_geracao          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_faturas_apolice ON faturas(nr_apolice);
CREATE INDEX IF NOT EXISTS ix_faturas_comp    ON faturas(cd_competencia);
CREATE UNIQUE INDEX IF NOT EXISTS uq_faturas_apolice_comp ON faturas(nr_apolice, cd_competencia);

-- ── SINISTRO ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sinistros (
    nr_sinistro         TEXT            PRIMARY KEY,
    nr_apolice          TEXT            NOT NULL,
    cd_cpf_segurado     TEXT            NOT NULL,
    cd_empresa          INTEGER         NOT NULL DEFAULT 0,
    cd_tipo_evento      TEXT            NOT NULL,
    nm_tipo_evento      TEXT,
    dt_evento           TEXT            NOT NULL,
    dt_abertura         TEXT            NOT NULL,
    dt_encerramento     TEXT,
    dt_pagamento        TEXT,
    vl_capital_averbado NUMERIC(15,2),
    vl_indenizacao      NUMERIC(15,2),
    vl_pago             NUMERIC(15,2)   NOT NULL DEFAULT 0,
    cd_status           TEXT            NOT NULL DEFAULT 'AB',
    ds_observacao       TEXT,
    parecer             TEXT,
    ds_parecer          TEXT,
    nr_doc_banco        TEXT,
    ds_encerramento     TEXT,
    id_usuario_incl     TEXT            NOT NULL DEFAULT 'SYSTEM',
    ts_inclusao         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    ts_alteracao        TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_sinistros_apolice ON sinistros(nr_apolice);
CREATE INDEX IF NOT EXISTS ix_sinistros_status  ON sinistros(cd_status);

-- ── KIT ECM (SINISTRO) ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sinistro_docs_ecm (
    cd_doc_ecm          BIGSERIAL       PRIMARY KEY,
    nr_sinistro         TEXT            NOT NULL,
    nm_grupo            TEXT            NOT NULL,
    nm_tipo             TEXT            NOT NULL,
    nr_ref              TEXT,
    nm_arquivo          TEXT            NOT NULL,
    ds_observacao       TEXT,
    id_usuario_incl     TEXT            NOT NULL DEFAULT 'SYSTEM',
    dt_gravacao         TEXT            NOT NULL,
    hr_gravacao         TEXT            NOT NULL,
    fl_selecionado      TEXT            NOT NULL DEFAULT 'S',
    ts_inclusao         TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_sin_docs_sinistro ON sinistro_docs_ecm(nr_sinistro);

-- ── CORRETORAS ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS corretoras (
    cd_corretora        BIGSERIAL       PRIMARY KEY,
    nm_razao_social     TEXT            NOT NULL,
    nm_nome_reduzido    TEXT,
    cd_cnpj             TEXT            NOT NULL UNIQUE,
    nr_susep            TEXT            NOT NULL,
    cd_email            TEXT,
    nr_telefone         TEXT,
    nr_celular          TEXT,
    ds_endereco         TEXT,
    cd_cep              TEXT,
    nm_cidade           TEXT,
    sg_estado           TEXT,
    ds_site             TEXT,
    ds_observacao       TEXT,
    cd_status           TEXT            NOT NULL DEFAULT 'AT',
    dt_inclusao         TEXT            NOT NULL,
    ts_inclusao         TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Seed: corretora exemplo
INSERT INTO corretoras (nm_razao_social, nm_nome_reduzido, cd_cnpj, nr_susep,
    cd_email, nr_telefone, nr_celular, nm_cidade, sg_estado, ds_site,
    cd_status, dt_inclusao)
VALUES ('Corretora Exemplo Ltda', 'CORRETORA EX', '12345678000199', 'J1234',
    'contato@corretora.com.br', '1133445566', '11987654321',
    'São Paulo', 'SP', 'https://corretora.com.br', 'AT', '20240101')
ON CONFLICT (cd_cnpj) DO NOTHING;

-- ── CORRETORES ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS corretores (
    cd_corretor         BIGSERIAL       PRIMARY KEY,
    cd_corretora        BIGINT          NOT NULL REFERENCES corretoras(cd_corretora),
    nm_nome             TEXT            NOT NULL,
    nr_cpf              TEXT            NOT NULL UNIQUE,
    nr_susep            TEXT            NOT NULL,
    cd_email_principal  TEXT            NOT NULL,
    cd_email_secundario TEXT,
    nr_telefone         TEXT,
    nr_celular          TEXT,
    ds_especialidade    TEXT,
    dt_inicio_vigencia  TEXT,
    dt_fim_vigencia     TEXT,
    ds_observacao       TEXT,
    cd_status           TEXT            NOT NULL DEFAULT 'AT',
    dt_inclusao         TEXT            NOT NULL,
    ts_inclusao         TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Seed: corretor exemplo
INSERT INTO corretores (cd_corretora, nm_nome, nr_cpf, nr_susep,
    cd_email_principal, cd_email_secundario, nr_celular, ds_especialidade,
    dt_inicio_vigencia, cd_status, dt_inclusao)
SELECT cd_corretora, 'João Corretor Silva', '98765432100', 'J12345',
    'joao@corretora.com.br', 'joao.silva@gmail.com', '11976543210',
    'Vida em Grupo, VGC', '20240101', 'AT', '20240101'
FROM corretoras WHERE cd_cnpj = '12345678000199' LIMIT 1
ON CONFLICT (nr_cpf) DO NOTHING;

-- ── VÍNCULOS EMPRESA ↔ CORRETORA ────────────────────────────────
CREATE TABLE IF NOT EXISTS vinculos_corretagem (
    cd_vinculo          BIGSERIAL       PRIMARY KEY,
    cd_empresa          INTEGER         NOT NULL,
    cd_corretora        BIGINT          NOT NULL REFERENCES corretoras(cd_corretora),
    cd_corretor         BIGINT          REFERENCES corretores(cd_corretor),
    pct_comissao        NUMERIC(5,2),
    dt_inicio           TEXT            NOT NULL,
    dt_fim              TEXT,
    ds_observacao       TEXT,
    cd_status           TEXT            NOT NULL DEFAULT 'AT',
    dt_inclusao         TEXT            NOT NULL,
    ts_inclusao         TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_vinculos_empresa   ON vinculos_corretagem(cd_empresa);
CREATE INDEX IF NOT EXISTS ix_vinculos_corretora ON vinculos_corretagem(cd_corretora);

-- ── CRÍTICAS PENDENTES ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS criticas_pendentes (
    id_critica          TEXT            PRIMARY KEY,
    nr_apolice          TEXT            NOT NULL,
    cpf                 TEXT            NOT NULL,
    nome                TEXT            NOT NULL,
    codigo              TEXT            NOT NULL,
    severidade          TEXT            NOT NULL,
    descricao           TEXT            NOT NULL,
    payload_linha       JSONB           NOT NULL DEFAULT '{}',
    cd_status           TEXT            NOT NULL DEFAULT 'PENDENTE',
    id_operador         TEXT,
    ds_justificativa    TEXT,
    ts_criacao          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    ts_resolucao        TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_criticas_apolice ON criticas_pendentes(nr_apolice);
CREATE INDEX IF NOT EXISTS ix_criticas_status  ON criticas_pendentes(cd_status);
