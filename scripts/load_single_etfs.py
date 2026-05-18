#!/usr/bin/env python3
"""
Load single-direction Direxion ETFs into Supabase.

For each <SYMBOL>.csv in csvs/, fetches the canonical longName via
yfinance, parses sponsor + leverage + underlying out of the name, and
upserts into:
  - etfs        (category='single', side='single')
  - etf_holdings (parsed from the CSV)

The list of symbols comes from copying CSVs from the source folder
into csvs/ before running. Run from project root:
    python3 scripts/load_single_etfs.py
"""

import csv
import datetime as dt
import os
import re
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
CSV_DIR = ROOT / "csvs"


# -----------------------------------------------------------------------------
# CSV parsing (Direxion format — same as load_paired_etfs.py)
# -----------------------------------------------------------------------------

def parse_asof(s):
    if not s:
        return None
    try:
        return dt.datetime.strptime(s, "%m/%d/%Y").date().isoformat()
    except Exception:
        return None


def parse_direxion(path):
    with open(path, encoding="utf-8-sig") as f:
        while True:
            pos = f.tell()
            line = f.readline()
            if not line:
                return None, []
            if line.lstrip().startswith('"TradeDate"') or line.startswith("TradeDate"):
                f.seek(pos); break
        reader = csv.DictReader(f)
        rows = []; as_of = None
        for r in reader:
            ticker = (r.get("StockTicker") or "").strip()
            name   = (r.get("SecurityDescription") or "").strip()
            cusip  = (r.get("Cusip") or "").strip()
            shares = float(r.get("Shares") or 0)
            value  = float(r.get("MarketValue") or 0)
            pct    = float(r.get("HoldingsPercent") or 0)
            if not ticker and not name:
                continue
            up = name.upper()
            if cusip.startswith("X9USD") or "CASH" in up or "TRSRY" in up or "TREASURY" in up or "GOVT" in up:
                ptype = "Cash"
            elif "SWAP" in up or cusip.startswith(("SPX", "RTY", "NDX", "RUT")):
                ptype = "Swap"
            elif ticker:
                ptype = "Equity"
            else:
                ptype = "Other"
            if not as_of:
                as_of = parse_asof((r.get("TradeDate") or "").split(" ")[0])
            rows.append({"ticker": ticker or None, "name": name, "shares": shares,
                         "value": value, "weight": pct, "type": ptype})
    rows.sort(key=lambda x: -abs(x["weight"]))
    return as_of, rows


# -----------------------------------------------------------------------------
# Name parser
# -----------------------------------------------------------------------------

LEV_RE = re.compile(r'Bull\s+(\d)\s*X', re.IGNORECASE)


def parse_name(longname):
    """Returns (sponsor, leverage_str, underlying, display_name)."""
    if not longname:
        return None, None, None, None
    sponsor = "Direxion" if longname.lower().startswith("direxion") else None

    m = LEV_RE.search(longname)
    leverage = f"+{m.group(1)}x" if m else None

    underlying = longname
    if sponsor:
        underlying = re.sub(r'^Direxion\s+Daily\s+', '', underlying, flags=re.IGNORECASE)
        underlying = re.sub(r'^Direxion\s+', '', underlying, flags=re.IGNORECASE)
    # Strip trailing "Bull NX ETF/Shares" + optional trailing punctuation
    underlying = re.sub(r'\s+Bull\s+\d\s*X.*$', '', underlying, flags=re.IGNORECASE)
    underlying = re.sub(r'\s+(ETF|Shares|Fund)$', '', underlying, flags=re.IGNORECASE)
    underlying = underlying.strip().rstrip(',').strip()

    return sponsor, leverage, underlying, longname


def fetch_longname(symbol):
    try:
        info = yf.Ticker(symbol, session=SESSION).info
    except Exception as e:
        print(f"  ! {symbol}: yfinance error {e}")
        return None
    return info.get("longName") or info.get("shortName")


# -----------------------------------------------------------------------------
# Upsert helper
# -----------------------------------------------------------------------------

def upsert_batched(table, rows, on_conflict, batch=1000, label=""):
    if not rows:
        print(f"  {label or table}: 0 rows")
        return
    label = label or table
    t0 = time.time()
    for i in range(0, len(rows), batch):
        sb.table(table).upsert(rows[i:i + batch], on_conflict=on_conflict).execute()
        end = min(i + batch, len(rows))
        print(f"  {label}: {end:,}/{len(rows):,}", flush=True)
    print(f"  {label}: done in {time.time() - t0:.1f}s")


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        sys.exit("usage: load_single_etfs.py SYM1 SYM2 ...")
    symbols = [s.upper() for s in sys.argv[1:]]
    print(f"Loading {len(symbols)} single-direction ETFs")

    etf_rows = []
    holding_rows = []

    for sym in symbols:
        csv_path = CSV_DIR / f"{sym}.csv"
        if not csv_path.exists():
            print(f"  ! {sym}: no CSV at {csv_path}, skipping")
            continue

        longname = fetch_longname(sym)
        sponsor, leverage, underlying, display = parse_name(longname)
        if not display:
            display = sym
        print(f"  {sym}  →  {display}   sponsor={sponsor} lev={leverage} ul={underlying}")

        as_of, rows = parse_direxion(csv_path)
        for i, h in enumerate(rows):
            holding_rows.append({
                "etf_symbol":    sym,
                "rank":          i + 1,
                "ticker":        h["ticker"],
                "name":          h["name"],
                "shares":        h["shares"],
                "value":         h["value"],
                "weight":        h["weight"],
                "position_type": h["type"],
                "as_of":         as_of,
            })

        etf_rows.append({
            "symbol":          sym,
            "name":            display,
            "sponsor":         sponsor,
            "leverage":        leverage,
            "underlying":      underlying,
            "category":        "single",
            "side":            "single",
            "pair_underlying": None,
            "base_price":      None,
            "day_change":      None,
            "year_change":     None,
        })
        time.sleep(0.2)

    print(f"\n→ Upserting {len(etf_rows)} etfs, {len(holding_rows):,} holdings")
    upsert_batched("etfs", etf_rows, "symbol")
    upsert_batched("etf_holdings", holding_rows, "etf_symbol,rank")
    print("\n✓ Done.")


if __name__ == "__main__":
    main()
