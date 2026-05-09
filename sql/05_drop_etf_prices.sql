-- =====================================================================
-- Drop etf_prices: prices are now fetched live from Yahoo Finance via
-- the /api/prices Vercel edge function (cached daily). The table is no
-- longer queried by the site.
-- =====================================================================

DROP TABLE IF EXISTS public.etf_prices;
