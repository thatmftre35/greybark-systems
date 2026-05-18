#!/usr/bin/env python3
"""
Refresh base_price / day_change / year_change on every row in the
public.etfs table from yfinance.

The leveraged-etfs page reads these columns directly so it doesn't
need a live API roundtrip on every page load. Run this whenever you
want the cards to show fresh numbers (daily is plenty).

Run from project root:  python3 scripts/refresh_etf_prices.py
"""

import os
import sys
import time
from pathlib import Path

from curl_cffi import requests as curl_requests
from dotenv import load_dotenv
from supabase import create_client
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env.local")

SB_URL = os.environ.get("SUPABASE_URL")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
if not (SB_URL and SB_KEY):
    sys.exit("Missing SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY in .env.local")

sb = create_client(SB_URL, SB_KEY)
SESSION = curl_requests.Session(impersonate="chrome")


def split_adjust_closes(history, splits):
    """Apply manual split adjustment to a yfinance daily history's Close
    column — Yahoo's Adj Close is unreliable for ETFs with many reverse
    splits (e.g. SOXS)."""
    out = []
    if history is None or history.empty:
        return out
    for ts, row in history.iterrows():
        c = float(row["Close"])
        if c <= 0:
            continue
        if splits is not None and not splits.empty:
            future = splits[splits.index > ts]
            if len(future) > 0:
                c = c * float(future.prod())
        out.append(c)
    return out


def summarize(symbol):
    try:
        t = yf.Ticker(symbol, session=SESSION)
        df = t.history(period="1y", interval="1d", auto_adjust=False, actions=False)
        closes = split_adjust_closes(df, t.splits)
    except Exception as e:
        print(f"    ! {symbol}: {e}")
        return None
    if len(closes) < 2:
        return None
    last = closes[-1]
    prev = closes[-2]
    year_ago = closes[0]
    return {
        "base_price":  round(last, 2),
        "day_change":  round((last - prev) / prev * 100, 2) if prev > 0 else None,
        "year_change": round((last - year_ago) / year_ago * 100, 2) if year_ago > 0 else None,
    }


def main():
    r = sb.table("etfs").select("symbol").execute()
    symbols = sorted(row["symbol"] for row in r.data)
    print(f"Refreshing {len(symbols)} ETFs")

    ok = 0
    for i, sym in enumerate(symbols, 1):
        s = summarize(sym)
        if s is None:
            print(f"  {i}/{len(symbols)} {sym}: no data")
            continue
        sb.table("etfs").update(s).eq("symbol", sym).execute()
        ok += 1
        if i % 10 == 0 or i == len(symbols):
            print(f"  {i}/{len(symbols)} {sym}: ${s['base_price']} "
                  f"day={s['day_change']}% year={s['year_change']}%")
        time.sleep(0.15)

    print(f"\n✓ {ok}/{len(symbols)} refreshed")


if __name__ == "__main__":
    main()
