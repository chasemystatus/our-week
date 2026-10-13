-- Our Week: database setup for Supabase.
-- Paste this whole file into the Supabase SQL Editor and run it. It can be run again safely.
--
-- BEFORE YOU RUN IT: change the two example emails in section 1 to the two people who should
-- be allowed in, written in lower case. Only those two will ever be able to read or write the
-- planner, however many accounts exist.
--
-- What it does:
--   1. Lists who is allowed in.
--   2-4. Creates the planner tables.
--   5. Turns on row-level security, so access is decided by the database and not by the web page.
--   6. Switches on live updates, so a change on one phone shows on the other.
--   7. Prints a check: every table should say true.

-- 1. Who is allowed in. Nobody can read this list through the app; only the rules below can.
create table if not exists public.members (email text primary key);
insert into public.members (email) values
  ('person-one@example.com'),
  ('person-two@example.com')
on conflict do nothing;

-- 2. One-off entries
create table if not exists public.entries (
  id uuid primary key default gen_random_uuid(),
  date date not null,
  name text not null check (char_length(name) between 1 and 120),
  owner text not null check (owner in ('eloise','toby','both')),
  type text not null check (type in ('task','plan','shift')),
  start_time text, end_time text, label text,
  close boolean not null default false,
  done boolean not null default false,
  created_at timestamptz not null default now()
);

-- 3. Repeating entries, stored once with a rule
create table if not exists public.series (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(name) between 1 and 120),
  owner text not null check (owner in ('eloise','toby','both')),
  type text not null check (type in ('task','plan','shift')),
  start_time text, end_time text, label text,
  close boolean not null default false,
  from_date date not null,
  last_date date,
  rule jsonb not null,
  created_at timestamptz not null default now()
);

-- 4. Changes to a single repeat: skipped, ticked off, or edited
create table if not exists public.exceptions (
  id uuid primary key default gen_random_uuid(),
  series_id uuid not null references public.series(id) on delete cascade,
  orig date not null,
  skip boolean not null default false,
  done boolean not null default false,
  data jsonb,
  unique (series_id, orig)
);

-- 5. Lock everything down
alter table public.members enable row level security;
alter table public.entries enable row level security;
alter table public.series enable row level security;
alter table public.exceptions enable row level security;

-- Is the person signed in right now on the members list? It runs with its owner's rights so it
-- can read `members`, which nobody else can. Emails in `members` must be lower case.
create or replace function public.is_member() returns boolean
language sql stable security definer set search_path = ''
as $$ select exists (select 1 from public.members m where m.email = lower(auth.jwt() ->> 'email')) $$;
revoke execute on function public.is_member() from public, anon;
grant execute on function public.is_member() to authenticated;

drop policy if exists members_only on public.entries;
drop policy if exists members_only on public.series;
drop policy if exists members_only on public.exceptions;
create policy members_only on public.entries for all to authenticated using (public.is_member()) with check (public.is_member());
create policy members_only on public.series for all to authenticated using (public.is_member()) with check (public.is_member());
create policy members_only on public.exceptions for all to authenticated using (public.is_member()) with check (public.is_member());

-- Older Supabase projects give new tables broad access by default, so start from nothing.
-- (Newer projects already do; this changes nothing there.)
revoke all on public.members, public.entries, public.series, public.exceptions from anon, authenticated;

-- Signed-in people get access (the rules above then decide who); signed-out visitors get none.
grant select, insert, update, delete on public.entries, public.series, public.exceptions to authenticated;

-- 6. So a change on one phone appears on the other (skips any table already added)
do $$
declare t text;
begin
  foreach t in array array['entries', 'series', 'exceptions'] loop
    if not exists (select 1 from pg_publication_tables
                   where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = t) then
      execute format('alter publication supabase_realtime add table public.%I', t);
    end if;
  end loop;
end
$$;

-- 7. Check: every table should say true
select tablename, rowsecurity from pg_tables where schemaname = 'public' order by tablename;
