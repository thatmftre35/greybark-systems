#!/usr/bin/env python3
"""
Load the first batch of 20 paired leveraged ETFs into Supabase:
- ETF metadata (etfs)
- Holdings parsed from csvs/<SYMBOL>.csv (etf_holdings)
- Daily + 1-minute intraday prices via yfinance (etf_prices)

Run from project root:  python3 scripts/load_paired_etfs.py
"""

import csv
import datetime as dt
import os
import sys
import time
from datetime import timedelta, timezone
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
    sys.exit("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env.local")

sb = create_client(SB_URL, SB_KEY)
SESSION = curl_requests.Session(impersonate="chrome")
CSV_DIR = ROOT / "csvs"

# (bull, bear, name_root, sponsor, leverage_int, underlying)
PAIRS = [
    ("SPXL", "SPXS", "S&P 500",              "Direxion", 3, "S&P 500"),
    ("TNA",  "TZA",  "Small Cap",            "Direxion", 3, "Russell 2000"),
    ("EDC",  "EDZ",  "MSCI Emerging Mkts",   "Direxion", 3, "MSCI Emerging Markets"),
    ("YINN", "YANG", "FTSE China",           "Direxion", 3, "FTSE China 50"),
    ("TYD",  "TYO",  "7-10 Year Treasury",   "Direxion", 3, "ICE 7-10 Year Treasury"),
    ("TMF",  "TMV",  "20+ Year Treasury",    "Direxion", 3, "ICE 20+ Year Treasury"),
    ("DRN",  "DRV",  "Real Estate",          "Direxion", 3, "MSCI US REIT"),
    ("FAS",  "FAZ",  "Financial",            "Direxion", 3, "Russell 1000 Financial"),
    ("HIBL", "HIBS", "S&P 500 High Beta",    "Direxion", 3, "S&P 500 High Beta"),
    ("LABU", "LABD", "S&P Biotech",          "Direxion", 3, "S&P Biotech"),
    ("SOXL", "SOXS", "Semiconductor",        "Direxion", 3, "PHLX Semiconductor"),
    ("TECL", "TECS", "Technology",           "Direxion", 3, "Tech Select Sector"),
    ("WEBL", "WEBS", "Dow Jones Internet",   "Direxion", 3, "Dow Jones Internet"),
    ("ERX",  "ERY",  "Energy",               "Direxion", 2, "Energy Select Sector"),
    ("GUSH", "DRIP", "S&P Oil & Gas E&P",    "Direxion", 2, "S&P Oil & Gas E&P"),
    ("JNUG", "JDST", "Junior Gold Miners",   "Direxion", 2, "MVIS Junior Gold Miners"),
    ("NUGT", "DUST", "Gold Miners",          "Direxion", 2, "NYSE Arca Gold Miners"),
    ("TSXU", "TSXD", "Semiconductors Top 5", "Direxion", 2, "Semiconductors Top 5"),
    ("TTXU", "TTXD", "Technology Top 5",     "Direxion", 2, "Technology Top 5"),
    ("AIBU", "AIBD", "AI and Big Data",      "Direxion", 2, "AI & Big Data"),
]


# -----------------------------------------------------------------------------
# CSV parsing (Direxion format)
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
        rows = []
        as_of = None
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
            rows.append({
                "ticker": ticker or None,
                "name":   name,
                "shares": shares,
                "value":  value,
                "weight": pct,
                "type":   ptype,
            })
    rows.sort(key=lambda x: -abs(x["weight"]))
    return as_of, rows


# -----------------------------------------------------------------------------
# Price fetching (yfinance)
# -----------------------------------------------------------------------------

def fetch_daily(sym):
    df = yf.Ticker(sym, session=SESSION).history(
        period="10y", interval="1d", auto_adjust=False, actions=False)
    if df is None or df.empty:
        return []
    out = []
    for ts, row in df.iterrows():
        c = float(row["Close"])
        if c > 0:
            out.append((ts.strftime("%Y-%m-%d"), round(c, 2)))
    return out


def fetch_intraday(sym):
    df = yf.Ticker(sym, session=SESSION).history(
        period="7d", interval="1m",
        auto_adjust=False, actions=False, prepost=False)
    if df is None or df.empty:
        return []
    out = []
    for ts, row in df.iterrows():
        c = float(row["Close"])
        if c <= 0:
            continue
        try:
            ts_local = ts.tz_convert("America/New_York")
        except Exception:
            ts_local = ts
        out.append((ts_local.strftime("%Y-%m-%d %H:%M"), round(c, 2)))
    return out


# -----------------------------------------------------------------------------
# Time-string helpers (mirror migrate_to_supabase.py)
# -----------------------------------------------------------------------------

def daily_to_iso(d):
    return d + "T00:00:00Z"


ET_OFF_DST    = timedelta(hours=-4)
ET_OFF_NO_DST = timedelta(hours=-5)


def intraday_to_iso(s):
    try:
        d = dt.datetime.strptime(s, "%Y-%m-%d %H:%M")
    except Exception:
        return None
    is_dst = 3 <= d.month <= 11
    off = ET_OFF_DST if is_dst else ET_OFF_NO_DST
    return (d - off).replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


# -----------------------------------------------------------------------------
# Supabase upsert helper
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
# Build & load
# -----------------------------------------------------------------------------

def build_etf_row(symbol, side, name_root, sponsor, lev_x, underlying, daily_rows):
    base_price = day_change = year_change = None
    if daily_rows:
        last = daily_rows[-1][1]
        base_price = last
        if len(daily_rows) >= 2:
            prev = daily_rows[-2][1]
            if prev > 0:
                day_change = round((last - prev) / prev * 100, 2)
        ya = daily_rows[-253][1] if len(daily_rows) >= 253 else daily_rows[0][1]
        if ya and ya > 0:
            year_change = round((last - ya) / ya * 100, 2)
    leverage_str = ("+" if side == "bull" else "-") + f"{lev_x}x"
    direction    = "Bull" if side == "bull" else "Bear"
    return {
        "symbol":          symbol,
        "name":            f"{sponsor} Daily {name_root} {direction} {lev_x}X",
        "sponsor":         sponsor,
        "leverage":        leverage_str,
        "underlying":      underlying,
        "category":        "pair",
        "side":            side,
        "pair_underlying": underlying,
        "base_price":      base_price,
        "day_change":      day_change,
        "year_change":     year_change,
    }


def main():
    etf_rows = []
    holding_rows = []
    price_rows = []

    for bull, bear, name_root, sponsor, lev, underlying in PAIRS:
        for sym, side in [(bull, "bull"), (bear, "bear")]:
            print(f"\n→ {sym} ({side})")

            csv_path = CSV_DIR / f"{sym}.csv"
            as_of, rows = parse_direxion(csv_path)
            print(f"   holdings: {len(rows)} rows, as_of={as_of}")
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

            daily = fetch_daily(sym)
            intraday = fetch_intraday(sym)
            print(f"   prices:   {len(daily)} daily, {len(intraday)} intraday")
            time.sleep(0.4)

            for d, c in daily:
                price_rows.append({
                    "etf_symbol":  sym,
                    "ts":          daily_to_iso(d),
                    "granularity": "daily",
                    "close":       c,
                })
            for ts, c in intraday:
                iso = intraday_to_iso(ts)
                if iso:
                    price_rows.append({
                        "etf_symbol":  sym,
                        "ts":          iso,
                        "granularity": "intraday",
                        "close":       c,
                    })

            etf_rows.append(build_etf_row(sym, side, name_root, sponsor, lev, underlying, daily))

    print(f"\n→ Upserting {len(etf_rows)} etfs, "
          f"{len(holding_rows):,} holdings, {len(price_rows):,} prices")
    upsert_batched("etfs", etf_rows, "symbol")
    upsert_batched("etf_holdings", holding_rows, "etf_symbol,rank")
    upsert_batched("etf_prices", price_rows, "etf_symbol,granularity,ts", batch=2000)
    print("\n✓ Done.")


if __name__ == "__main__":
    main()
