-- db/schema.sql
-- trades table
create extension if not exists "pgcrypto";

create table if not exists trades (
  id uuid default gen_random_uuid() primary key,
  timestamp timestamptz default now(),
  exchange text not null,
  symbol text not null,
  side text not null,
  amount numeric not null,
  price numeric not null,
  fee numeric default 0,
  mode text not null,
  raw jsonb
);

-- positions table
create table if not exists positions (
  id uuid default gen_random_uuid() primary key,
  symbol text not null,
  exchange text not null,
  side text not null,
  amount numeric not null,
  entry_price numeric not null,
  opened_at timestamptz default now()
);

-- logs
create table if not exists bot_logs (
  id bigserial primary key,
  level text,
  message text,
  created_at timestamptz default now()
);

-- settings
create table if not exists settings (
  key text primary key,
  value text
);
