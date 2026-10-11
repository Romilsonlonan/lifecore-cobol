-- ============================================================
-- LifeCore · Supabase — Tabelas de Movimentação de Vidas
-- Executar no SQL Editor: Settings → SQL Editor → New Query
-- ============================================================

-- ── 1. Lotes de importação ────────────────────────────────────
create table if not exists public.importacao_vidas (
  id_importacao   text        primary key,           -- UUID gerado pela API
  nr_apolice      text        not null,
  cd_empresa      integer     not null default 0,
  qt_registros    integer     not null default 0,
  qt_validos      integer     not null default 0,
  qt_gravados     integer     not null default 0,
  qt_erros        integer     not null default 0,
  cd_status       text        not null default 'PE', -- PE=pendente OK=ok PA=parcial
  dt_importacao   text        not null,              -- AAAAMMDD
  id_usuario      text        not null default 'CORRETOR',
  dry_run         boolean     not null default false,
  ts_inclusao     timestamptz not null default now()
);

create index if not exists idx_imp_vidas_apolice
  on public.importacao_vidas(nr_apolice, ts_inclusao desc);

-- ── 2. Itens (vidas individuais) de cada lote ─────────────────
create table if not exists public.importacao_vidas_item (
  id              bigint      generated always as identity primary key,
  id_importacao   text        not null references public.importacao_vidas(id_importacao) on delete cascade,
  nr_linha        integer     not null,
  cd_cpf          text        not null,
  nm_segurado     text        not null,
  dt_nascimento   text        default '',
  dt_admissao     text        default '',
  cd_subestipulante text      default '',
  cd_modulo       text        default '',
  cd_cargo        text        default '',
  vl_salario      numeric(15,2) default 0,
  nr_fator_mult   numeric(5,2)  default 1,
  vl_capital      numeric(15,2) default 0,
  cd_status       text        not null default 'OK', -- OK ERRO
  ds_erros        text        default ''
);

create index if not exists idx_imp_vidas_item_imp
  on public.importacao_vidas_item(id_importacao);

create index if not exists idx_imp_vidas_item_cpf
  on public.importacao_vidas_item(cd_cpf);

-- ── 3. Segurados (espelho do DB2 SEGURADO) ───────────────────
create table if not exists public.segurados (
  cd_cpf          text        primary key,
  nm_segurado     text        not null,
  dt_nascimento   text        default '',
  cd_empresa      integer     not null default 0,
  vl_salario      numeric(15,2) default 0,
  dt_admissao     text        default '',
  dt_inclusao     text        not null,
  id_usuario_incl text        not null default 'CORRETOR',
  ts_criado       timestamptz not null default now(),
  ts_atualizado   timestamptz not null default now()
);

create or replace function public.set_segurado_ts()
returns trigger language plpgsql as $$
begin new.ts_atualizado = now(); return new; end;
$$;

drop trigger if exists trg_segurado_ts on public.segurados;
create trigger trg_segurado_ts
  before update on public.segurados
  for each row execute function public.set_segurado_ts();

-- ── 4. Coberturas (espelho do DB2 COBERTURA) ─────────────────
create table if not exists public.coberturas (
  cd_cobertura    text        primary key,
  nr_apolice      text        not null,
  cd_cpf          text        not null,
  cd_tipo         text        not null default 'MORT',
  nm_cobertura    text        not null,
  vl_capital      numeric(15,2) not null default 0,
  nr_carencia_dias integer    not null default 0,
  cd_status       text        not null default 'AT',
  ts_criado       timestamptz not null default now(),
  ts_atualizado   timestamptz not null default now()
);

create index if not exists idx_coberturas_apolice
  on public.coberturas(nr_apolice);

create index if not exists idx_coberturas_cpf
  on public.coberturas(cd_cpf);

create or replace function public.set_cobertura_ts()
returns trigger language plpgsql as $$
begin new.ts_atualizado = now(); return new; end;
$$;

drop trigger if exists trg_cobertura_ts on public.coberturas;
create trigger trg_cobertura_ts
  before update on public.coberturas
  for each row execute function public.set_cobertura_ts();

-- ── 5. RLS ────────────────────────────────────────────────────
alter table public.importacao_vidas       enable row level security;
alter table public.importacao_vidas_item  enable row level security;
alter table public.segurados              enable row level security;
alter table public.coberturas             enable row level security;

create policy "service_role full access" on public.importacao_vidas
  for all using (true) with check (true);

create policy "service_role full access" on public.importacao_vidas_item
  for all using (true) with check (true);

create policy "service_role full access" on public.segurados
  for all using (true) with check (true);

create policy "service_role full access" on public.coberturas
  for all using (true) with check (true);

-- ── 6. Comentários ───────────────────────────────────────────
comment on table public.importacao_vidas      is 'Lotes de importação de vidas — espelho do DB2 IMPORTACAO_VIDAS';
comment on table public.importacao_vidas_item is 'Itens individuais de cada lote de importação';
comment on table public.segurados             is 'Segurados — espelho do DB2 SEGURADO (sync via importação)';
comment on table public.coberturas            is 'Coberturas — espelho do DB2 COBERTURA (sync via importação)';
