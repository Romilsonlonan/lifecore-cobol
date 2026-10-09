-- ============================================================
-- LifeCore · Supabase — Fix permissões service_role
-- Executar no SQL Editor após o schema inicial
-- ============================================================

-- Garante que o service_role tem acesso total às tabelas
grant all on public.estipulantes  to service_role;
grant all on public.ecm_docs      to service_role;
grant all on public.apolice_seq   to service_role;

-- Garante acesso à sequência de identity da ecm_docs
grant usage, select on all sequences in schema public to service_role;

-- Remove policies antigas e recria com bypass correto
drop policy if exists "service_role full access" on public.estipulantes;
drop policy if exists "service_role full access" on public.ecm_docs;
drop policy if exists "service_role full access" on public.apolice_seq;

-- O service_role bypassa RLS por padrão no Supabase
-- Estas policies são para outros roles autenticados no futuro:
create policy "anon leitura" on public.estipulantes
  for select using (true);

create policy "anon leitura" on public.ecm_docs
  for select using (true);

create policy "anon leitura" on public.apolice_seq
  for select using (true);
