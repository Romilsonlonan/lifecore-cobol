-- ============================================================
-- LifeCore · Supabase — Migração v2
-- Adiciona colunas faltantes na tabela estipulantes
-- Executar no SQL Editor do dashboard do Supabase
-- ============================================================

-- ── Colunas de status e tipo ───────────────────────────────
alter table public.estipulantes
  add column if not exists cd_status          text not null default 'AT',
  add column if not exists tp_estipulante     text not null default 'PJ',
  add column if not exists tp_termino_contrato text not null default 'negociacao',
  add column if not exists tp_renovacao       text not null default 'manual';

-- ── Colunas de capital / tarifação ────────────────────────
alter table public.estipulantes
  add column if not exists tp_capital         text not null default 'F',
  add column if not exists vl_capital_global  text not null default '0',
  add column if not exists nr_fator_mult      text not null default '24';

-- ── Coberturas (substitui coberturas_extras) ──────────────
-- Mantém coberturas_extras por retrocompatibilidade e
-- adiciona coberturas (nome correto esperado pelo código).
alter table public.estipulantes
  add column if not exists coberturas         jsonb not null default '[]';

-- ── IPCA ──────────────────────────────────────────────────
alter table public.estipulantes
  add column if not exists vl_ipca_vigente    text not null default '0',
  add column if not exists fl_reajuste_ipca   text not null default 'N';

-- ── Cancelamento ──────────────────────────────────────────
alter table public.estipulantes
  add column if not exists dt_cancelamento        text,
  add column if not exists ds_motivo_cancelamento text,
  add column if not exists tp_suspensao           text,
  add column if not exists dt_inicio_suspensao    text,
  add column if not exists dt_prev_reativacao     text,
  add column if not exists nr_processo_judicial   text,
  add column if not exists nm_orgao_judicial      text,
  add column if not exists fl_cobranca_suspensa   text not null default 'N',
  add column if not exists cd_subestipulante_suc  integer;

-- ── Constraint de status ──────────────────────────────────
-- Permite: AT=Ativo, CA=Cancelado, SU=Suspenso
do $$
begin
  if not exists (
    select 1 from information_schema.table_constraints
    where table_name = 'estipulantes'
      and constraint_name = 'ck_estipulantes_status'
  ) then
    alter table public.estipulantes
      add constraint ck_estipulantes_status
      check (cd_status in ('AT','CA','SU'));
  end if;
end $$;

-- ── Sincroniza coberturas_extras → coberturas nos registros existentes ─
update public.estipulantes
  set coberturas = coberturas_extras
where coberturas = '[]'::jsonb
  and coberturas_extras != '[]'::jsonb;

-- ── Índice em cd_status para queries de cancelamento ──────
create index if not exists idx_estipulantes_status
  on public.estipulantes(cd_status);
