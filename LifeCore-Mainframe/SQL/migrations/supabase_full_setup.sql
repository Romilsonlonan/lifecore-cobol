-- ================================================================
-- LifeCore IQ · Supabase — Setup Completo
-- ================================================================
-- Colar inteiro no Supabase Dashboard → SQL Editor → Run
-- Totalmente idempotente: seguro de executar múltiplas vezes.
-- Ordem: schema 001 (portal) → schema 002 (módulos batch) → RLS
-- ================================================================

-- ────────────────────────────────────────────────────────────────
-- 001 · PORTAL (estipulantes, ecm_docs, apolice_seq)
-- ────────────────────────────────────────────────────────────────

-- Sequência de apólice por ano
CREATE TABLE IF NOT EXISTS public.apolice_seq (
  ano  INTEGER PRIMARY KEY,
  seq  INTEGER NOT NULL DEFAULT 0
);

-- Estipulantes cadastrados via Portal do Corretor
CREATE TABLE IF NOT EXISTS public.estipulantes (
  nr_apolice             TEXT        PRIMARY KEY,
  nm_razao_social        TEXT        NOT NULL,
  cd_cnpj                TEXT        NOT NULL UNIQUE,
  periodo_contrato       TEXT        NOT NULL DEFAULT '12',
  dt_cadastro            TEXT        NOT NULL,
  ts_cadastro            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ts_atualizado          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  ds_logradouro          TEXT        DEFAULT '',
  ds_numero              TEXT        DEFAULT '',
  ds_bairro              TEXT        DEFAULT '',
  cd_cep                 TEXT        DEFAULT '',
  ds_cidade              TEXT        DEFAULT '',
  cd_uf                  TEXT        DEFAULT '',

  nm_contato             TEXT        DEFAULT '',
  ds_telefone            TEXT        DEFAULT '',
  ds_email               TEXT        DEFAULT '',
  emails_extra           JSONB       NOT NULL DEFAULT '[]',
  telefones_extra        JSONB       NOT NULL DEFAULT '[]',

  nm_corretora           TEXT        DEFAULT '',
  cd_cnpj_corretora      TEXT        DEFAULT '',
  nm_corretor            TEXT        DEFAULT '',
  ds_telefone_corretor   TEXT        DEFAULT '',
  ds_email_corretor      TEXT        DEFAULT '',

  nr_dia_corte           TEXT        DEFAULT '',
  nr_dia_vencimento      TEXT        DEFAULT '',
  fat_automatico         TEXT        NOT NULL DEFAULT 'nao',

  tp_cobertura           TEXT        NOT NULL DEFAULT 'F',
  coberturas_extras      JSONB       NOT NULL DEFAULT '[]',
  subestipulantes        JSONB       NOT NULL DEFAULT '[]'
);

-- Trigger: atualiza ts_atualizado automaticamente
CREATE OR REPLACE FUNCTION public.set_ts_atualizado()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.ts_atualizado = NOW();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_estipulantes_ts ON public.estipulantes;
CREATE TRIGGER trg_estipulantes_ts
  BEFORE UPDATE ON public.estipulantes
  FOR EACH ROW EXECUTE FUNCTION public.set_ts_atualizado();

-- Documentos ECM vinculados às apólices
CREATE TABLE IF NOT EXISTS public.ecm_docs (
  id             BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nr_apolice     TEXT        NOT NULL REFERENCES public.estipulantes(nr_apolice) ON DELETE CASCADE,
  nm_arquivo     TEXT        NOT NULL,
  tp_arquivo     TEXT        NOT NULL,
  nr_tamanho_kb  NUMERIC(10,1) NOT NULL,
  storage_path   TEXT        DEFAULT '',
  ts_upload      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ecm_docs_apolice ON public.ecm_docs(nr_apolice);

COMMENT ON TABLE public.apolice_seq  IS 'Controle de sequência de apólice por ano (AAAA → último seq)';
COMMENT ON TABLE public.estipulantes IS 'Estipulantes cadastrados via Portal do Corretor';
COMMENT ON TABLE public.ecm_docs     IS 'Metadados dos documentos ECM vinculados às apólices';

-- ────────────────────────────────────────────────────────────────
-- 002 · MÓDULOS BATCH (proposta, apolice, fatura, sinistro, etc.)
-- ────────────────────────────────────────────────────────────────

-- Propostas de seguro
CREATE TABLE IF NOT EXISTS public.propostas (
  nr_proposta        TEXT            PRIMARY KEY,
  cd_empresa         INTEGER         NOT NULL DEFAULT 0,
  cd_cpf_segurado    TEXT            NOT NULL DEFAULT '',
  cd_produto         TEXT            NOT NULL DEFAULT 'VGC',
  tp_capital         TEXT            NOT NULL DEFAULT 'F',
  vl_capital         NUMERIC(15,2)   NOT NULL DEFAULT 0,
  vl_salario_base    NUMERIC(13,2),
  nr_fator_mult      NUMERIC(5,2),
  vl_premio_bruto    NUMERIC(13,2),
  vl_premio_liquido  NUMERIC(13,2),
  cd_status          TEXT            NOT NULL DEFAULT 'AN',
  tp_aceite          TEXT,
  dt_proposta        TEXT            NOT NULL,
  dt_aceite          TEXT,
  dt_recusa          TEXT,
  cd_motivo_recusa   TEXT,
  ds_motivo_recusa   TEXT,
  nr_dias_analise    INTEGER         NOT NULL DEFAULT 15,
  id_usuario         TEXT            NOT NULL DEFAULT 'SYSTEM',
  nr_apolice_gerada  TEXT,
  ts_inclusao        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
  ts_alteracao       TIMESTAMPTZ
);

-- Apólices emitidas
CREATE TABLE IF NOT EXISTS public.apolices (
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
  ts_emissao          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
  ts_inclusao         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
  ts_alteracao        TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_apolices_empresa ON public.apolices(cd_empresa);
CREATE INDEX IF NOT EXISTS ix_apolices_status  ON public.apolices(cd_status);

-- Taxas IPCA (seed com dados reais 2025)
CREATE TABLE IF NOT EXISTS public.taxas_ipca (
  cd_competencia    TEXT            PRIMARY KEY,
  vl_taxa_ipca      NUMERIC(8,4)    NOT NULL,
  vl_taxa_acumulada NUMERIC(8,4),
  dt_divulgacao     TEXT,
  ds_fonte          TEXT            NOT NULL DEFAULT 'IBGE/IPCA',
  fl_vigente        BOOLEAN         NOT NULL DEFAULT FALSE,
  ts_inclusao       TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

INSERT INTO public.taxas_ipca
  (cd_competencia, vl_taxa_ipca, vl_taxa_acumulada, dt_divulgacao, fl_vigente)
VALUES
  ('202501', 0.16, 4.83, '20250212', FALSE),
  ('202502', 1.31, 5.06, '20250312', FALSE),
  ('202503', 0.56, 5.48, '20250410', FALSE),
  ('202504', 0.43, 5.53, '20250514', FALSE),
  ('202505', 0.43, 5.30, '20250612', FALSE),
  ('202506', 0.24, 5.35, '20250710', FALSE),
  ('202507', 0.38, 4.50, '20250813', TRUE)
ON CONFLICT (cd_competencia) DO NOTHING;

-- Endossos por apólice
CREATE TABLE IF NOT EXISTS public.endossos (
  nr_endosso            TEXT            PRIMARY KEY,
  nr_apolice            TEXT            NOT NULL,
  cd_cpf_segurado       TEXT            NOT NULL,
  nm_segurado           TEXT,
  tp_endosso            TEXT            NOT NULL,
  vl_capital            NUMERIC(15,2),
  vl_salario_base       NUMERIC(13,2),
  nr_fator_mult         NUMERIC(5,2),
  dt_inicio_vigencia    TEXT,
  cd_status             TEXT            NOT NULL DEFAULT 'PROCESSADO',
  vl_capital_calculado  NUMERIC(15,2),
  vl_premio_calculado   NUMERIC(13,2),
  id_usuario            TEXT            NOT NULL DEFAULT 'SYSTEM',
  ts_inclusao           TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_endossos_apolice ON public.endossos(nr_apolice);

-- Faturas mensais
CREATE TABLE IF NOT EXISTS public.faturas (
  nr_fatura        TEXT            PRIMARY KEY,
  nr_apolice       TEXT            NOT NULL,
  cd_empresa       INTEGER         NOT NULL DEFAULT 0,
  cd_competencia   TEXT            NOT NULL,
  dt_emissao       TEXT            NOT NULL,
  dt_vencimento    TEXT,
  forma_cobranca   TEXT,
  vl_total_bruto   NUMERIC(15,2)   NOT NULL DEFAULT 0,
  vl_total_liquido NUMERIC(15,2)   NOT NULL DEFAULT 0,
  vl_reajuste_ipca NUMERIC(13,2)   NOT NULL DEFAULT 0,
  nr_segurados     INTEGER         NOT NULL DEFAULT 0,
  itens            JSONB           NOT NULL DEFAULT '[]',
  cd_status        TEXT            NOT NULL DEFAULT 'EM_ABERTO',
  ts_geracao       TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_faturas_apolice         ON public.faturas(nr_apolice);
CREATE INDEX IF NOT EXISTS ix_faturas_comp            ON public.faturas(cd_competencia);
CREATE UNIQUE INDEX IF NOT EXISTS uq_faturas_apolice_comp ON public.faturas(nr_apolice, cd_competencia);

-- Sinistros
CREATE TABLE IF NOT EXISTS public.sinistros (
  nr_sinistro          TEXT            PRIMARY KEY,
  nr_apolice           TEXT            NOT NULL,
  cd_cpf_segurado      TEXT            NOT NULL,
  cd_empresa           INTEGER         NOT NULL DEFAULT 0,
  cd_tipo_evento       TEXT            NOT NULL,
  nm_tipo_evento       TEXT,
  dt_evento            TEXT            NOT NULL,
  dt_abertura          TEXT            NOT NULL,
  dt_encerramento      TEXT,
  dt_pagamento         TEXT,
  vl_capital_averbado  NUMERIC(15,2),
  vl_indenizacao       NUMERIC(15,2),
  vl_pago              NUMERIC(15,2)   NOT NULL DEFAULT 0,
  cd_status            TEXT            NOT NULL DEFAULT 'AB',
  ds_observacao        TEXT,
  parecer              TEXT,
  ds_parecer           TEXT,
  nr_doc_banco         TEXT,
  ds_encerramento      TEXT,
  id_usuario_incl      TEXT            NOT NULL DEFAULT 'SYSTEM',
  ts_inclusao          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
  ts_alteracao         TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_sinistros_apolice ON public.sinistros(nr_apolice);
CREATE INDEX IF NOT EXISTS ix_sinistros_status  ON public.sinistros(cd_status);

-- Documentos ECM de sinistro (kit ECM)
CREATE TABLE IF NOT EXISTS public.sinistro_docs_ecm (
  cd_doc_ecm       BIGSERIAL       PRIMARY KEY,
  nr_sinistro      TEXT            NOT NULL,
  nm_grupo         TEXT            NOT NULL,
  nm_tipo          TEXT            NOT NULL,
  nr_ref           TEXT,
  nm_arquivo       TEXT            NOT NULL,
  ds_observacao    TEXT,
  id_usuario_incl  TEXT            NOT NULL DEFAULT 'SYSTEM',
  dt_gravacao      TEXT            NOT NULL,
  hr_gravacao      TEXT            NOT NULL,
  fl_selecionado   TEXT            NOT NULL DEFAULT 'S',
  ts_inclusao      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_sin_docs_sinistro ON public.sinistro_docs_ecm(nr_sinistro);

-- Corretoras
CREATE TABLE IF NOT EXISTS public.corretoras (
  cd_corretora     BIGSERIAL       PRIMARY KEY,
  nm_razao_social  TEXT            NOT NULL,
  nm_nome_reduzido TEXT,
  cd_cnpj          TEXT            NOT NULL UNIQUE,
  nr_susep         TEXT            NOT NULL,
  cd_email         TEXT,
  nr_telefone      TEXT,
  nr_celular       TEXT,
  ds_endereco      TEXT,
  cd_cep           TEXT,
  nm_cidade        TEXT,
  sg_estado        TEXT,
  ds_site          TEXT,
  ds_observacao    TEXT,
  cd_status        TEXT            NOT NULL DEFAULT 'AT',
  dt_inclusao      TEXT            NOT NULL,
  ts_inclusao      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

INSERT INTO public.corretoras
  (nm_razao_social, nm_nome_reduzido, cd_cnpj, nr_susep,
   cd_email, nr_telefone, nr_celular, nm_cidade, sg_estado, ds_site,
   cd_status, dt_inclusao)
VALUES
  ('Corretora Exemplo Ltda', 'CORRETORA EX', '12345678000199', 'J1234',
   'contato@corretora.com.br', '1133445566', '11987654321',
   'São Paulo', 'SP', 'https://corretora.com.br', 'AT', '20240101')
ON CONFLICT (cd_cnpj) DO NOTHING;

-- Corretores (pessoas físicas vinculadas a corretoras)
CREATE TABLE IF NOT EXISTS public.corretores (
  cd_corretor          BIGSERIAL       PRIMARY KEY,
  cd_corretora         BIGINT          NOT NULL REFERENCES public.corretoras(cd_corretora),
  nm_nome              TEXT            NOT NULL,
  nr_cpf               TEXT            NOT NULL UNIQUE,
  nr_susep             TEXT            NOT NULL,
  cd_email_principal   TEXT            NOT NULL,
  cd_email_secundario  TEXT,
  nr_telefone          TEXT,
  nr_celular           TEXT,
  ds_especialidade     TEXT,
  dt_inicio_vigencia   TEXT,
  dt_fim_vigencia      TEXT,
  ds_observacao        TEXT,
  cd_status            TEXT            NOT NULL DEFAULT 'AT',
  dt_inclusao          TEXT            NOT NULL,
  ts_inclusao          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

INSERT INTO public.corretores
  (cd_corretora, nm_nome, nr_cpf, nr_susep, cd_email_principal,
   cd_email_secundario, nr_celular, ds_especialidade,
   dt_inicio_vigencia, cd_status, dt_inclusao)
SELECT
  cd_corretora, 'João Corretor Silva', '98765432100', 'J12345',
  'joao@corretora.com.br', 'joao.silva@gmail.com', '11976543210',
  'Vida em Grupo, VGC', '20240101', 'AT', '20240101'
FROM public.corretoras WHERE cd_cnpj = '12345678000199' LIMIT 1
ON CONFLICT (nr_cpf) DO NOTHING;

-- Vínculos empresa ↔ corretora
CREATE TABLE IF NOT EXISTS public.vinculos_corretagem (
  cd_vinculo    BIGSERIAL       PRIMARY KEY,
  cd_empresa    INTEGER         NOT NULL,
  cd_corretora  BIGINT          NOT NULL REFERENCES public.corretoras(cd_corretora),
  cd_corretor   BIGINT          REFERENCES public.corretores(cd_corretor),
  pct_comissao  NUMERIC(5,2),
  dt_inicio     TEXT            NOT NULL,
  dt_fim        TEXT,
  ds_observacao TEXT,
  cd_status     TEXT            NOT NULL DEFAULT 'AT',
  dt_inclusao   TEXT            NOT NULL,
  ts_inclusao   TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_vinculos_empresa   ON public.vinculos_corretagem(cd_empresa);
CREATE INDEX IF NOT EXISTS ix_vinculos_corretora ON public.vinculos_corretagem(cd_corretora);

-- Críticas pendentes (motor de críticas de segurados)
CREATE TABLE IF NOT EXISTS public.criticas_pendentes (
  id_critica      TEXT        PRIMARY KEY,
  nr_apolice      TEXT        NOT NULL,
  cpf             TEXT        NOT NULL,
  nome            TEXT        NOT NULL,
  codigo          TEXT        NOT NULL,
  severidade      TEXT        NOT NULL,
  descricao       TEXT        NOT NULL,
  payload_linha   JSONB       NOT NULL DEFAULT '{}',
  cd_status       TEXT        NOT NULL DEFAULT 'PENDENTE',
  id_operador     TEXT,
  ds_justificativa TEXT,
  ts_criacao      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ts_resolucao    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_criticas_apolice ON public.criticas_pendentes(nr_apolice);
CREATE INDEX IF NOT EXISTS ix_criticas_status  ON public.criticas_pendentes(cd_status);

-- ────────────────────────────────────────────────────────────────
-- RLS · Row Level Security
-- ────────────────────────────────────────────────────────────────
-- O service_role bypassa RLS por padrão no Supabase.
-- Habilitamos RLS em todas as tabelas para segurança e adicionamos
-- políticas permissivas — o backend acessa via service_role key.

ALTER TABLE public.apolice_seq          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.estipulantes         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ecm_docs             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.propostas            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.apolices             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.taxas_ipca           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.endossos             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.faturas              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sinistros            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sinistro_docs_ecm    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.corretoras           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.corretores           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vinculos_corretagem  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.criticas_pendentes   ENABLE ROW LEVEL SECURITY;

-- Remove políticas antigas (idempotência)
DO $$ DECLARE tbl TEXT; BEGIN
  FOR tbl IN VALUES
    ('apolice_seq'),('estipulantes'),('ecm_docs'),('propostas'),('apolices'),
    ('taxas_ipca'),('endossos'),('faturas'),('sinistros'),('sinistro_docs_ecm'),
    ('corretoras'),('corretores'),('vinculos_corretagem'),('criticas_pendentes')
  LOOP
    EXECUTE format(
      'DROP POLICY IF EXISTS "service_role full access" ON public.%I', tbl
    );
    EXECUTE format(
      'DROP POLICY IF EXISTS "anon leitura" ON public.%I', tbl
    );
    EXECUTE format(
      'DROP POLICY IF EXISTS "backend full access" ON public.%I', tbl
    );
  END LOOP;
END $$;

-- Política única: acesso total via service_role (backend Python)
CREATE POLICY "backend full access" ON public.apolice_seq
  FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "backend full access" ON public.estipulantes
  FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "backend full access" ON public.ecm_docs
  FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "backend full access" ON public.propostas
  FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "backend full access" ON public.apolices
  FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "backend full access" ON public.taxas_ipca
  FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "backend full access" ON public.endossos
  FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "backend full access" ON public.faturas
  FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "backend full access" ON public.sinistros
  FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "backend full access" ON public.sinistro_docs_ecm
  FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "backend full access" ON public.corretoras
  FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "backend full access" ON public.corretores
  FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "backend full access" ON public.vinculos_corretagem
  FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "backend full access" ON public.criticas_pendentes
  FOR ALL USING (TRUE) WITH CHECK (TRUE);

-- ────────────────────────────────────────────────────────────────
-- GRANTS · Permissões explícitas para service_role
-- ────────────────────────────────────────────────────────────────
GRANT ALL ON public.apolice_seq          TO service_role;
GRANT ALL ON public.estipulantes         TO service_role;
GRANT ALL ON public.ecm_docs             TO service_role;
GRANT ALL ON public.propostas            TO service_role;
GRANT ALL ON public.apolices             TO service_role;
GRANT ALL ON public.taxas_ipca           TO service_role;
GRANT ALL ON public.endossos             TO service_role;
GRANT ALL ON public.faturas              TO service_role;
GRANT ALL ON public.sinistros            TO service_role;
GRANT ALL ON public.sinistro_docs_ecm    TO service_role;
GRANT ALL ON public.corretoras           TO service_role;
GRANT ALL ON public.corretores           TO service_role;
GRANT ALL ON public.vinculos_corretagem  TO service_role;
GRANT ALL ON public.criticas_pendentes   TO service_role;

-- Garante acesso a todas as sequences (BIGSERIAL / IDENTITY)
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;

-- ────────────────────────────────────────────────────────────────
-- STORAGE · Bucket ecm-docs (documentos sinistro / portal)
-- ────────────────────────────────────────────────────────────────
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'ecm-docs', 'ecm-docs', FALSE, 20971520,
  ARRAY[
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  ]
)
ON CONFLICT (id) DO UPDATE
  SET file_size_limit    = EXCLUDED.file_size_limit,
      allowed_mime_types = EXCLUDED.allowed_mime_types;

DROP POLICY IF EXISTS "service_role upload ecm-docs" ON storage.objects;
DROP POLICY IF EXISTS "service_role select ecm-docs" ON storage.objects;
DROP POLICY IF EXISTS "service_role delete ecm-docs" ON storage.objects;

CREATE POLICY "service_role upload ecm-docs"
  ON storage.objects FOR INSERT TO service_role
  WITH CHECK (bucket_id = 'ecm-docs');

CREATE POLICY "service_role select ecm-docs"
  ON storage.objects FOR SELECT TO service_role
  USING (bucket_id = 'ecm-docs');

CREATE POLICY "service_role delete ecm-docs"
  ON storage.objects FOR DELETE TO service_role
  USING (bucket_id = 'ecm-docs');

-- ────────────────────────────────────────────────────────────────
-- FIM DO SCRIPT
-- ────────────────────────────────────────────────────────────────
-- Tabelas criadas / verificadas:
--   001 portal:  apolice_seq · estipulantes · ecm_docs
--   002 módulos: propostas · apolices · taxas_ipca · endossos
--                faturas · sinistros · sinistro_docs_ecm
--                corretoras · corretores · vinculos_corretagem
--                criticas_pendentes
-- Seeds:  taxas_ipca 2025 · corretora exemplo · corretor exemplo
-- ────────────────────────────────────────────────────────────────
