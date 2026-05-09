-- =====================================================================
-- Row-Level Security policies
-- Public read on most tables; HOLDINGS tables require authenticated user.
-- Run this AFTER 01_schema.sql.
-- =====================================================================

-- Stocks: public read
ALTER TABLE public.stock_info ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "stock_info read" ON public.stock_info;
CREATE POLICY "stock_info read" ON public.stock_info
  FOR SELECT TO anon, authenticated USING (true);

-- ETFs: public read
ALTER TABLE public.etfs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "etfs read" ON public.etfs;
CREATE POLICY "etfs read" ON public.etfs
  FOR SELECT TO anon, authenticated USING (true);

-- ETF holdings: AUTHENTICATED ONLY
ALTER TABLE public.etf_holdings ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "etf_holdings read auth" ON public.etf_holdings;
CREATE POLICY "etf_holdings read auth" ON public.etf_holdings
  FOR SELECT TO authenticated USING (true);

-- Fund categories: public read
ALTER TABLE public.fund_categories ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "fund_categories read" ON public.fund_categories;
CREATE POLICY "fund_categories read" ON public.fund_categories
  FOR SELECT TO anon, authenticated USING (true);

-- Funds: public read (list, returns, series — backtest chart is public)
ALTER TABLE public.funds ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "funds read" ON public.funds;
CREATE POLICY "funds read" ON public.funds
  FOR SELECT TO anon, authenticated USING (true);

-- Fund holdings: AUTHENTICATED ONLY
ALTER TABLE public.fund_holdings ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "fund_holdings read auth" ON public.fund_holdings;
CREATE POLICY "fund_holdings read auth" ON public.fund_holdings
  FOR SELECT TO authenticated USING (true);
