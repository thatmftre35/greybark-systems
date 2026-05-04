-- =====================================================================
-- GreyBark Systems — Supabase schema
-- Run this in the Supabase SQL editor (one time).
-- =====================================================================

-- Auth tables (auth.users) are created by Supabase automatically;
-- we just reference them.

-- ---------------------------------------------------------------------
-- Stocks (per-ticker company name + domain for logo lookups)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.stock_info (
  ticker TEXT PRIMARY KEY,
  name   TEXT,
  domain TEXT
);

-- ---------------------------------------------------------------------
-- Leveraged ETFs
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.etfs (
  symbol           TEXT PRIMARY KEY,
  name             TEXT NOT NULL,
  sponsor          TEXT,
  leverage         TEXT,
  underlying       TEXT,
  category         TEXT NOT NULL CHECK (category IN ('pair','single','stock_pair')),
  side             TEXT CHECK (side IN ('bull','bear','single')),
  pair_underlying  TEXT,        -- groups paired ETFs (e.g. "S&P 500" matches SPXL/SPXS)
  base_price       NUMERIC,
  day_change       NUMERIC,
  year_change      NUMERIC,
  updated_at       TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS etfs_category_idx       ON public.etfs(category);
CREATE INDEX IF NOT EXISTS etfs_pair_underlying_idx ON public.etfs(pair_underlying);

CREATE TABLE IF NOT EXISTS public.etf_holdings (
  id          BIGSERIAL PRIMARY KEY,
  etf_symbol  TEXT NOT NULL REFERENCES public.etfs(symbol) ON DELETE CASCADE,
  rank        INT NOT NULL,
  ticker      TEXT,
  name        TEXT,
  shares      NUMERIC,
  value       NUMERIC,
  weight      NUMERIC,
  position_type TEXT,
  as_of       DATE,
  UNIQUE(etf_symbol, rank)
);
CREATE INDEX IF NOT EXISTS etf_holdings_symbol_idx ON public.etf_holdings(etf_symbol);

CREATE TABLE IF NOT EXISTS public.etf_prices (
  etf_symbol   TEXT NOT NULL REFERENCES public.etfs(symbol) ON DELETE CASCADE,
  ts           TIMESTAMPTZ NOT NULL,
  granularity  TEXT NOT NULL CHECK (granularity IN ('daily','intraday')),
  close        NUMERIC NOT NULL,
  PRIMARY KEY (etf_symbol, granularity, ts)
);
CREATE INDEX IF NOT EXISTS etf_prices_lookup_idx ON public.etf_prices(etf_symbol, granularity, ts);

-- ---------------------------------------------------------------------
-- Funds (institutional)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.fund_categories (
  id          TEXT PRIMARY KEY,
  label       TEXT NOT NULL,
  description TEXT,
  fund_ids    JSONB,        -- ordered list of fund ids in this category
  sort_order  INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS public.funds (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  est_return  NUMERIC,
  returns     JSONB,        -- {"1D":0.5, "1W":1.2, "1Y":127.6, ...}
  series      JSONB,        -- [["2023-05-04", 100.0], ["2023-05-05", 100.4], ...]
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.fund_holdings (
  id        BIGSERIAL PRIMARY KEY,
  fund_id   TEXT NOT NULL REFERENCES public.funds(id) ON DELETE CASCADE,
  rank      INT NOT NULL,
  ticker    TEXT NOT NULL,
  shares    BIGINT,
  usd       BIGINT,
  weight    NUMERIC,
  UNIQUE(fund_id, rank)
);
CREATE INDEX IF NOT EXISTS fund_holdings_fund_idx ON public.fund_holdings(fund_id);
