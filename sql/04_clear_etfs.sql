-- =====================================================================
-- Wipe all leveraged-ETF data so the universe can be rebuilt from scratch.
-- The category structure (pair / single / stock_pair) lives in the schema's
-- CHECK constraint, so it survives this — only rows are removed.
--
-- Funds tables (funds, fund_holdings, fund_categories) are untouched.
-- stock_info is shared with funds and is also untouched.
--
-- Run in the Supabase SQL editor.
-- =====================================================================

TRUNCATE TABLE
  public.etf_holdings,
  public.etfs
RESTART IDENTITY;
