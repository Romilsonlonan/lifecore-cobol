-- ============================================================
-- LifeCore · Supabase — Schema inicial
-- Executar no SQL Editor do dashboard do Supabase
-- Settings → SQL Editor → New Query → colar e executar
-- ============================================================

-- ── 1. Sequência de apólice por ano ───────────────────────────
create table if not exists public.apolice_seq (
  ano   integer primary key,
  seq   integer not null default 0
);

-- ── 2. Estipulantes ───────────────────────────────────────────
create table if not exists public.estipulantes (
  nr_apolice        text        primary key,          -- ex: 20260001
  nm_razao_social   text        not null,
  cd_cnpj           text        not null unique,
  periodo_contrato  text        not null default '12',
  dt_cadastro       text        not null,             -- AAAAMMDD
  ts_cadastro       timestamptz not null default now(),
  ts_atualizado     timestamptz not null default now(),

  -- Endereço
  ds_logradouro     text        default '',
  ds_numero         text        default '',
  ds_bairro         text        default '',
  cd_cep            text        default '',
  ds_cidade         text        default '',
  cd_uf             text        default '',

  -- Contato principal
  nm_contato        text        default '',
  ds_telefone       text        default '',
  ds_email          text        default '',
  -- Contatos extras (lista JSON)
  emails_extra      jsonb       not null default '[]',
  telefones_extra   jsonb       not null default '[]',

  -- Corretora / Corretor
  nm_corretora           text  default '',
  cd_cnpj_corretora      text  default '',
  nm_corretor            text  default '',
  ds_telefone_corretor   text  default '',
  ds_email_corretor      text  default '',

  -- Faturamento
  nr_dia_corte       text  default '',
  nr_dia_vencimento  text  default '',
  fat_automatico     text  not null default 'nao',

  -- Produto
  tp_cobertura       text  not null default 'F',
  coberturas_extras  jsonb not null default '[]',

  -- Subestipulantes
  subestipulantes    jsonb not null default '[]'
);

-- Atualiza ts_atualizado automaticamente
create or replace function public.set_ts_atualizado()
returns trigger language plpgsql as $$
begin
  new.ts_atualizado = now();
  return new;
end;
$$;

drop trigger if exists trg_estipulantes_ts on public.estipulantes;
create trigger trg_estipulantes_ts
  before update on public.estipulantes
  for each row execute function public.set_ts_atualizado();

-- ── 3. Documentos ECM ─────────────────────────────────────────
create table if not exists public.ecm_docs (
  id              bigint      generated always as identity primary key,
  nr_apolice      text        not null references public.estipulantes(nr_apolice) on delete cascade,
  nm_arquivo      text        not null,
  tp_arquivo      text        not null,           -- PDF, DOC, DOCX
  nr_tamanho_kb   numeric(10,1) not null,
  storage_path    text        default '',          -- caminho no bucket do Supabase Storage
  ts_upload       timestamptz not null default now()
);

create index if not exists idx_ecm_docs_apolice on public.ecm_docs(nr_apolice);

-- ── 4. RLS — Row Level Security ───────────────────────────────
-- Por ora: acesso livre via service_role (backend Python).
-- Em produção: adicionar políticas por usuário autenticado.

alter table public.apolice_seq   enable row level security;
alter table public.estipulantes  enable row level security;
alter table public.ecm_docs      enable row level security;

-- Política: service_role tem acesso total (usado pelo backend)
create policy "service_role full access" on public.apolice_seq
  for all using (true) with check (true);

create policy "service_role full access" on public.estipulantes
  for all using (true) with check (true);

create policy "service_role full access" on public.ecm_docs
  for all using (true) with check (true);

-- ── 5. Comentários ───────────────────────────────────────────
comment on table public.estipulantes is 'Estipulantes cadastrados via Portal do Corretor';
comment on table public.ecm_docs     is 'Metadados dos documentos ECM vinculados às apólices';
comment on table public.apolice_seq  is 'Controle de sequência de apólice por ano (AAAA → último seq)';

-- ── 6. Supabase Storage — bucket ecm-docs ────────────────────
-- Executar APÓS as tabelas acima.
-- Cria o bucket privado para armazenar os arquivos ECM (PDF/DOC/DOCX).
-- O acesso é feito via signed URLs geradas pelo backend (service_role).

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'ecm-docs',
  'ecm-docs',
  false,                          -- privado: nunca exposto diretamente
  20971520,                       -- 20 MB
  array[
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  ]
)
on conflict (id) do update
  set file_size_limit    = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;

-- Policy: somente service_role pode fazer upload, download e delete.
-- O acesso público está bloqueado; o frontend recebe signed URLs (1h de validade).

create policy "service_role upload ecm-docs"
  on storage.objects for insert
  to service_role
  with check (bucket_id = 'ecm-docs');

create policy "service_role select ecm-docs"
  on storage.objects for select
  to service_role
  using (bucket_id = 'ecm-docs');

create policy "service_role delete ecm-docs"
  on storage.objects for delete
  to service_role
  using (bucket_id = 'ecm-docs');
