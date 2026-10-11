-- ============================================================
-- DB2 for z/OS — Migração 003: Cancelamento de Apólice
-- Aplicar em produção quando DB2_DSN estiver configurado.
-- ============================================================
-- CONTEXTO:
--   A tabela LIFECORE.EMPRESA usa CD_STATUS CHAR(2) com
--   CHECK IN ('AT','IN'). O cancelamento via Portal gera
--   status 'CA' (Cancelado) e 'SU' (Suspenso), que precisam
--   ser aceitos pela constraint.
--
--   A tabela LIFECORE.APOLICE já aceita 'AT','CA','SU','EX'
--   — nenhuma alteração necessária lá.
-- ============================================================

-- ── 1. Remove constraint antiga de status da EMPRESA ─────────
ALTER TABLE LIFECORE.EMPRESA
  DROP CONSTRAINT CK_EMPRESA_ST;

-- ── 2. Recria com os novos valores ───────────────────────────
--   AT = Ativo
--   IN = Inativo (legado)
--   CA = Cancelado (cancelamento definitivo)
--   SU = Suspenso (suspensão temporária)
ALTER TABLE LIFECORE.EMPRESA
  ADD CONSTRAINT CK_EMPRESA_ST
  CHECK (CD_STATUS IN ('AT','IN','CA','SU'));

-- ── 3. Adiciona campos de cancelamento à EMPRESA ─────────────
--   (espelha as colunas adicionadas no Supabase pela migração v2)
ALTER TABLE LIFECORE.EMPRESA
  ADD COLUMN DT_CANCELAMENTO   CHAR(8),
  ADD COLUMN DS_MOTIVO_CANCEL  VARCHAR(300),
  ADD COLUMN TP_SUSPENSAO      CHAR(8),       -- CLIENTE / JUDICIAL
  ADD COLUMN DT_INI_SUSPENSAO  CHAR(8),
  ADD COLUMN DT_PREV_REATIV    CHAR(8),
  ADD COLUMN NR_PROC_JUDICIAL  CHAR(30),
  ADD COLUMN NM_ORGAO_JUDICIAL VARCHAR(80),
  ADD COLUMN FL_COBR_SUSPENSA  CHAR(1) NOT NULL DEFAULT 'N',
  ADD COLUMN CD_SUBESTIP_SUC   INTEGER;

-- ── 4. Adiciona FK para subestipulante sucessor ───────────────
--   (somente se a tabela SUBESTIPULANTE existir)
-- ALTER TABLE LIFECORE.EMPRESA
--   ADD CONSTRAINT FK_EMP_SUBESTIP_SUC
--   FOREIGN KEY (CD_SUBESTIP_SUC) REFERENCES LIFECORE.EMPRESA(CD_EMPRESA);

-- ── ROLLBACK (em caso de erro) ────────────────────────────────
-- ALTER TABLE LIFECORE.EMPRESA DROP CONSTRAINT CK_EMPRESA_ST;
-- ALTER TABLE LIFECORE.EMPRESA ADD CONSTRAINT CK_EMPRESA_ST
--   CHECK (CD_STATUS IN ('AT','IN'));
-- ALTER TABLE LIFECORE.EMPRESA
--   DROP COLUMN DT_CANCELAMENTO
--   DROP COLUMN DS_MOTIVO_CANCEL
--   DROP COLUMN TP_SUSPENSAO
--   DROP COLUMN DT_INI_SUSPENSAO
--   DROP COLUMN DT_PREV_REATIV
--   DROP COLUMN NR_PROC_JUDICIAL
--   DROP COLUMN NM_ORGAO_JUDICIAL
--   DROP COLUMN FL_COBR_SUSPENSA
--   DROP COLUMN CD_SUBESTIP_SUC;
