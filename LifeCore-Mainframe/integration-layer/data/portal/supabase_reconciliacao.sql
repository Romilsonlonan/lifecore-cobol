-- ============================================================
-- LifeCore · Supabase — Migração: Reconciliação de Coberturas
--
-- Adiciona campos de saída à tabela coberturas para suportar
-- a exclusão automática de segurados ausentes na planilha mensal.
--
-- Executar no SQL Editor: Settings → SQL Editor → New Query
-- ============================================================

-- ── 1. Novos campos na tabela coberturas ─────────────────────
--   dt_saida           : competência AAAAMM em que a cobertura foi desativada
--   id_importacao_saida: ID do lote de importação que gerou a exclusão
alter table public.coberturas
  add column if not exists dt_saida             text default null,
  add column if not exists id_importacao_saida  text default null
    references public.importacao_vidas(id_importacao) on delete set null;

-- Índice para consultas de coberturas excluídas por apólice
create index if not exists idx_coberturas_saida
  on public.coberturas(nr_apolice, cd_status)
  where cd_status = 'EX';

-- ── 2. Comentários ───────────────────────────────────────────
comment on column public.coberturas.dt_saida            is 'Competência AAAAMM em que a cobertura foi excluída por reconciliação';
comment on column public.coberturas.id_importacao_saida is 'ID do lote de importação que originou a exclusão da cobertura';

-- ── 3. View auxiliar: situação atual de coberturas por apólice ─
-- Útil para auditoria e conferência mensal.
create or replace view public.vw_coberturas_ativas as
select
  c.nr_apolice,
  c.cd_cpf,
  c.nm_cobertura,
  c.vl_capital,
  c.cd_status,
  c.dt_saida,
  c.ts_criado,
  c.ts_atualizado,
  s.nm_segurado,
  s.dt_nascimento,
  s.vl_salario,
  s.dt_admissao
from public.coberturas c
left join public.segurados s on s.cd_cpf = c.cd_cpf
where c.cd_status = 'AT';

comment on view public.vw_coberturas_ativas is 'Coberturas ativas com dados do segurado — base para faturamento mensal';

-- ── 4. View de histórico de exclusões ─────────────────────────
create or replace view public.vw_historico_exclusoes as
select
  c.nr_apolice,
  c.cd_cpf,
  c.nm_cobertura,
  c.vl_capital,
  c.dt_saida       as competencia_saida,
  c.ts_atualizado  as dt_exclusao,
  c.id_importacao_saida,
  i.id_usuario     as usuario_exclusao,
  s.nm_segurado,
  s.dt_admissao
from public.coberturas c
left join public.importacao_vidas i on i.id_importacao = c.id_importacao_saida
left join public.segurados s on s.cd_cpf = c.cd_cpf
where c.cd_status = 'EX'
order by c.ts_atualizado desc;

comment on view public.vw_historico_exclusoes is 'Histórico de coberturas excluídas por reconciliação mensal';
