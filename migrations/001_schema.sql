-- Monitor de Licitações — Schema PostgreSQL Multi-tenant
-- Deploy: Supabase (free tier)
-- Executar via Supabase SQL Editor

create extension if not exists "uuid-ossp";
create extension if not exists "pg_trgm";

create table tenants (
  id            uuid primary key default uuid_generate_v4(),
  name          text not null,
  email         text not null unique,
  phone_whatsapp text,
  plan          text not null default 'trial' check (plan in ('trial','starter','pro','enterprise')),
  plan_expires_at timestamptz,
  is_active     boolean not null default true,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create table user_profiles (
  id            uuid primary key references auth.users(id) on delete cascade,
  tenant_id     uuid not null references tenants(id) on delete cascade,
  role          text not null default 'admin' check (role in ('admin','viewer')),
  created_at    timestamptz not null default now()
);

create table tenant_configs (
  id            uuid primary key default uuid_generate_v4(),
  tenant_id     uuid not null references tenants(id) on delete cascade,
  segments      text[] not null default '{}',
  keywords_must text[] not null default '{}',
  keywords_want text[] not null default '{}',
  keywords_skip text[] not null default '{}',
  min_value     numeric default 0,
  max_value     numeric,
  states        text[] default '{}',
  notify_email  boolean default true,
  notify_whatsapp boolean default false,
  notify_hour   int default 8,
  min_score     float default 5.0,
  updated_at    timestamptz not null default now(),
  unique(tenant_id)
);

create table licitacoes (
  id            uuid primary key default uuid_generate_v4(),
  source        text not null,
  external_id   text not null,
  portal_url    text not null,
  titulo        text not null,
  descricao     text,
  orgao         text,
  uf            text,
  municipio     text,
  modalidade    text,
  valor_estimado numeric,
  data_abertura timestamptz,
  data_publicacao timestamptz,
  status        text default 'aberta',
  raw_json      jsonb,
  created_at    timestamptz not null default now(),
  unique(source, external_id)
);

create index idx_licitacoes_source on licitacoes(source);
create index idx_licitacoes_uf on licitacoes(uf);
create index idx_licitacoes_abertura on licitacoes(data_abertura);
create index idx_licitacoes_titulo_gin on licitacoes using gin(titulo gin_trgm_ops);

create table matches (
  id            uuid primary key default uuid_generate_v4(),
  tenant_id     uuid not null references tenants(id) on delete cascade,
  licitacao_id  uuid not null references licitacoes(id) on delete cascade,
  score         float not null,
  score_detail  jsonb,
  notified_at   timestamptz,
  seen_at       timestamptz,
  is_favorite   boolean default false,
  note          text,
  created_at    timestamptz not null default now(),
  unique(tenant_id, licitacao_id)
);

create index idx_matches_tenant on matches(tenant_id);
create index idx_matches_score on matches(tenant_id, score desc);

create table leads (
  id            uuid primary key default uuid_generate_v4(),
  company_name  text not null,
  contact_email text,
  contact_name  text,
  segment       text,
  source        text,
  enriched_data jsonb,
  status        text not null default 'new' check (status in ('new','email_1_sent','email_2_sent','email_3_sent','replied','converted','unsubscribed')),
  last_email_at timestamptz,
  next_email_at timestamptz,
  tenant_id     uuid references tenants(id),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create index idx_leads_status on leads(status);
create index idx_leads_next_email on leads(next_email_at) where status not in ('converted','unsubscribed');

alter table tenant_configs enable row level security;
alter table matches enable row level security;

create or replace function set_updated_at() returns trigger language plpgsql as $$ begin new.updated_at = now(); return new; end; $$;
create trigger trg_tenants_upd before update on tenants for each row execute function set_updated_at();
create trigger trg_configs_upd before update on tenant_configs for each row execute function set_updated_at();
create trigger trg_leads_upd before update on leads for each row execute function set_updated_at();
