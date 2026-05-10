#!/usr/bin/env python3
"""
Populate Supabase stock_info with longName + domain for every ticker
in funds-data.js + funds-under-aum-data.js. The fund detail page reads
this table to fill the "Name" column on the holdings table.

Skips tickers that already have a populated row. Run from project root:
    python3 scripts/populate_stock_info.py
"""

import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

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


def extract_tickers(js_path: Path):
    if not js_path.exists():
        return set()
    text = js_path.read_text()
    return set(re.findall(r'ticker:"([A-Z0-9.\-]+)"', text))


def to_domain(url):
    if not url:
        return None
    try:
        parsed = urlparse(url if "://" in url else "https://" + url)
        host = (parsed.netloc or parsed.path).lstrip(".")
        if host.startswith("www."):
            host = host[4:]
        return host or None
    except Exception:
        return None


def fetch_info(symbol):
    try:
        info = yf.Ticker(symbol, session=SESSION).info
    except Exception as e:
        print(f"  ! {symbol}: {e}")
        return None, None
    name = info.get("longName") or info.get("shortName")
    domain = to_domain(info.get("website"))
    return name, domain


def main():
    tickers = set()
    for fname in ("funds-data.js", "funds-under-aum-data.js"):
        tickers |= extract_tickers(ROOT / fname)
    tickers = sorted(tickers)
    print(f"Total unique fund tickers: {len(tickers)}")

    # Skip ones already populated (have a name)
    have_name = set()
    BATCH = 200
    for i in range(0, len(tickers), BATCH):
        chunk = tickers[i:i + BATCH]
        r = sb.table("stock_info").select("ticker, name").in_("ticker", chunk).execute()
        for row in r.data:
            if row.get("name"):
                have_name.add(row["ticker"])
    todo = [t for t in tickers if t not in have_name]
    print(f"Already have names for: {len(have_name)}  ·  to fetch: {len(todo)}")

    upserts = []
    for i, sym in enumerate(todo, 1):
        name, domain = fetch_info(sym)
        if name:
            upserts.append({"ticker": sym, "name": name, "domain": domain})
        if i % 25 == 0 or i == len(todo):
            print(f"  {i}/{len(todo)}  (last: {sym} → {name})")
        time.sleep(0.25)

    if not upserts:
        print("\nNothing to upsert.")
        return

    print(f"\nUpserting {len(upserts)} rows to stock_info ...")
    for i in range(0, len(upserts), 500):
        sb.table("stock_info").upsert(upserts[i:i + 500], on_conflict="ticker").execute()
    print("✓ Done.")


if __name__ == "__main__":
    main()
