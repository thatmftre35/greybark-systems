-- =====================================================================
-- Add denormalized aggregate columns on funds for the public list view.
-- (fund_holdings stays gated by RLS; these aggregates are safe to ship.)
-- Run once in the Supabase SQL editor.
-- =====================================================================

ALTER TABLE public.funds
  ADD COLUMN IF NOT EXISTS holdings_count INT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS total_usd      BIGINT NOT NULL DEFAULT 0;

-- Backfill from existing rows
UPDATE public.funds f
SET holdings_count = (
      SELECT COUNT(*)::INT FROM public.fund_holdings WHERE fund_id = f.id
    ),
    total_usd = (
      SELECT COALESCE(SUM(usd), 0)::BIGINT FROM public.fund_holdings WHERE fund_id = f.id
    );
