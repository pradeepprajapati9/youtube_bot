-- ============================================================
-- YouTube_Bot — Supabase schema (multi-user)
-- Paste this whole file into: Supabase -> SQL Editor -> New query -> Run
-- ============================================================

-- 1) Channel a user connected (non-secret info; the owner may read it)
create table if not exists public.channels (
  user_id     uuid primary key references auth.users(id) on delete cascade,
  channel_id  text not null,
  title       text,
  created_at  timestamptz default now()
);

-- 2) The user's OAuth refresh token (SECRET). RLS is on but NO client policy
--    is added -> browsers can never read this table. Only the worker, using
--    the service_role key (which bypasses RLS), can read/write it.
create table if not exists public.channel_tokens (
  user_id       uuid primary key references auth.users(id) on delete cascade,
  refresh_token text not null,
  updated_at    timestamptz default now()
);

-- 3) The user's chosen content field (set once, the bot reuses it)
create table if not exists public.settings (
  user_id     uuid primary key references auth.users(id) on delete cascade,
  category    text,
  subcategory text,
  language    text default 'en',
  format      text default 'short',
  auto_daily  boolean default true,
  updated_at  timestamptz default now()
);

-- 4) Video job queue (dashboard inserts; worker processes)
create table if not exists public.jobs (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  category    text,
  subcategory text,
  language    text,
  format      text,
  status      text default 'queued',   -- queued | building | done | error
  video_url   text,
  error       text,
  created_at  timestamptz default now(),
  updated_at  timestamptz default now()
);

-- ============================================================
-- Row Level Security: each user can only see their OWN rows.
-- ============================================================
alter table public.channels       enable row level security;
alter table public.channel_tokens enable row level security;  -- no policy = client-locked
alter table public.settings       enable row level security;
alter table public.jobs           enable row level security;

-- channels: owner full access
drop policy if exists "own channels" on public.channels;
create policy "own channels" on public.channels
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- settings: owner full access
drop policy if exists "own settings" on public.settings;
create policy "own settings" on public.settings
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- jobs: owner may read + create their own
drop policy if exists "own jobs read"   on public.jobs;
drop policy if exists "own jobs insert" on public.jobs;
create policy "own jobs read"   on public.jobs for select using (auth.uid() = user_id);
create policy "own jobs insert" on public.jobs for insert with check (auth.uid() = user_id);

-- channel_tokens: user can save/update their OWN token, but canNOT read it back.
-- (Only the worker, via the service_role key, reads it — for uploading.)
drop policy if exists "save own token"   on public.channel_tokens;
drop policy if exists "update own token" on public.channel_tokens;
create policy "save own token"   on public.channel_tokens for insert with check (auth.uid() = user_id);
create policy "update own token" on public.channel_tokens for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
