-- ================================================================
-- LifeCore IQ · Migration 003 — Tabelas de Config de Apólice
-- ================================================================
-- Colar no Supabase Dashboard → SQL Editor → Run
-- Totalmente idempotente: seguro de executar múltiplas vezes.
-- ================================================================

-- Configuração de faturamento por apólice
CREATE TABLE IF NOT EXISTS public.config_faturamento (
  nr_apolice              TEXT          PRIMARY KEY,
  dia_vencimento          INTEGER       NOT NULL DEFAULT 5,
  dia_corte               INTEGER       NOT NULL DEFAULT 1,
  mes_competencia_ini     TEXT          NOT NULL DEFAULT '',
  periodicidade           TEXT          NOT NULL DEFAULT 'MENSAL',
  fl_repetir_sem_movimento TEXT         NOT NULL DEFAULT 'N',
  ds_obs_repeticao        TEXT,
  forma_cobranca          TEXT          NOT NULL DEFAULT 'BO',
  fl_nf_eletronica        TEXT          NOT NULL DEFAULT 'N',
  cd_email_fatura         TEXT,
  cd_email_copia          TEXT,
  ds_observacao           TEXT,
  dt_proximo_vencimento   TEXT,
  dt_ultima_atualizacao   TEXT,
  id_usuario_atualizacao  TEXT,
  ts_criado               TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
  ts_atualizado           TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- Subestipulantes (filiais/departamentos) de uma apólice
CREATE TABLE IF NOT EXISTS public.subestipulantes (
  cd_subestipulante       BIGINT        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nr_apolice              TEXT          NOT NULL,
  cd_cnpj                 TEXT          NOT NULL,
  nm_razao_social         TEXT          NOT NULL,
  nm_nome_reduzido        TEXT,
  cd_email                TEXT,
  nr_telefone             TEXT,
  nm_responsavel          TEXT,
  cd_email_responsavel    TEXT,
  dt_inclusao_apolice     TEXT          NOT NULL DEFAULT '',
  ds_observacao           TEXT,
  id_usuario              TEXT          NOT NULL DEFAULT 'SISTEMA',
  cd_status               TEXT          NOT NULL DEFAULT 'AT',
  dt_cancelamento         TEXT,
  ds_motivo_cancel        TEXT,
  ts_criado               TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
  ts_atualizado           TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_subestipulantes_apolice
  ON public.subestipulantes(nr_apolice);
CREATE INDEX IF NOT EXISTS idx_subestipulantes_status
  ON public.subestipulantes(nr_apolice, cd_status);

-- Contatos de uma apólice (para envio de fatura, apólice, certificado)
CREATE TABLE IF NOT EXISTS public.contatos_apolice (
  cd_contato              BIGINT        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nr_apolice              TEXT          NOT NULL,
  tp_contato              TEXT          NOT NULL DEFAULT 'FINANCEIRO',
  nm_contato              TEXT          NOT NULL,
  cd_cargo                TEXT,
  cd_email                TEXT          NOT NULL,
  cd_email_copia          TEXT,
  nr_telefone             TEXT,
  nr_celular              TEXT,
  fl_recebe_fatura        TEXT          NOT NULL DEFAULT 'N',
  fl_recebe_apolice       TEXT          NOT NULL DEFAULT 'N',
  fl_recebe_certificado   TEXT          NOT NULL DEFAULT 'N',
  ds_observacao           TEXT,
  cd_status               TEXT          NOT NULL DEFAULT 'AT',
  ts_criado               TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_contatos_apolice_nr
  ON public.contatos_apolice(nr_apolice);

-- Histórico de alterações de uma apólice (trilha de auditoria)
CREATE TABLE IF NOT EXISTS public.historico_apolice (
  id                      BIGINT        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nr_apolice              TEXT          NOT NULL,
  dt_hora_acao            TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
  tp_acao                 TEXT          NOT NULL,
  ds_descricao            TEXT          NOT NULL,
  id_usuario              TEXT          NOT NULL DEFAULT 'SISTEMA',
  ds_valor_antes          TEXT,
  ds_valor_depois         TEXT
);
CREATE INDEX IF NOT EXISTS idx_historico_apolice_nr
  ON public.historico_apolice(nr_apolice);
CREATE INDEX IF NOT EXISTS idx_historico_apolice_acao
  ON public.historico_apolice(nr_apolice, tp_acao);

-- Triggers de ts_atualizado
CREATE OR REPLACE FUNCTION public.set_ts_atualizado()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.ts_atualizado = NOW();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_config_fat_ts ON public.config_faturamento;
CREATE TRIGGER trg_config_fat_ts
  BEFORE UPDATE ON public.config_faturamento
  FOR EACH ROW EXECUTE FUNCTION public.set_ts_atualizado();

DROP TRIGGER IF EXISTS trg_subestipulantes_ts ON public.subestipulantes;
CREATE TRIGGER trg_subestipulantes_ts
  BEFORE UPDATE ON public.subestipulantes
  FOR EACH ROW EXECUTE FUNCTION public.set_ts_atualizado();

-- RLS: acesso anônimo permitido (integrado com service_role no backend)
ALTER TABLE public.config_faturamento ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subestipulantes    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.contatos_apolice   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.historico_apolice  ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'config_faturamento' AND policyname = 'anon_all'
  ) THEN
    CREATE POLICY anon_all ON public.config_faturamento
      FOR ALL TO anon USING (true) WITH CHECK (true);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'subestipulantes' AND policyname = 'anon_all'
  ) THEN
    CREATE POLICY anon_all ON public.subestipulantes
      FOR ALL TO anon USING (true) WITH CHECK (true);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'contatos_apolice' AND policyname = 'anon_all'
  ) THEN
    CREATE POLICY anon_all ON public.contatos_apolice
      FOR ALL TO anon USING (true) WITH CHECK (true);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'historico_apolice' AND policyname = 'anon_all'
  ) THEN
    CREATE POLICY anon_all ON public.historico_apolice
      FOR ALL TO anon USING (true) WITH CHECK (true);
  END IF;
END $$;

GRANT ALL ON public.config_faturamento TO anon, authenticated, service_role;
GRANT ALL ON public.subestipulantes    TO anon, authenticated, service_role;
GRANT ALL ON public.contatos_apolice   TO anon, authenticated, service_role;
GRANT ALL ON public.historico_apolice  TO anon, authenticated, service_role;
