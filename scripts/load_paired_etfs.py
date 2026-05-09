#!/usr/bin/env python3
"""
Load paired leveraged ETFs into Supabase.

- ETF metadata (etfs)
- Holdings parsed from csvs/<SYMBOL>.csv or csvs/<SYMBOL> Holdings.csv
  (Direxion or ProShares format; auto-detected from the first line)

Prices are not stored — the live site fetches them from /api/prices
(Yahoo Finance proxy, edge-cached daily).

Run from project root:  python3 scripts/load_paired_etfs.py
"""

import csv
import datetime as dt
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env.local")

SB_URL = os.environ.get("SUPABASE_URL")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
if not (SB_URL and SB_KEY):
    sys.exit("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env.local")

sb = create_client(SB_URL, SB_KEY)
CSV_DIR = ROOT / "csvs"

# (bull, bear, name_root, sponsor, lev_bull, lev_bear, underlying)
# lev_bull / lev_bear are integers; sign is implied by side.
# Most pairs are symmetric (e.g. +3x/-3x); UJB/SJB is the rare asymmetric
# pair (Ultra +2x bull / Short -1x bear) so we carry both leverages.
PAIRS = [
    # ---- Direxion 3X ----
    ("SPXL", "SPXS", "S&P 500",                  "Direxion", 3, 3, "S&P 500"),
    ("TNA",  "TZA",  "Small Cap",                "Direxion", 3, 3, "Russell 2000"),
    ("EDC",  "EDZ",  "MSCI Emerging Mkts",       "Direxion", 3, 3, "MSCI Emerging Markets"),
    ("YINN", "YANG", "FTSE China",               "Direxion", 3, 3, "FTSE China 50"),
    ("TYD",  "TYO",  "7-10 Year Treasury",       "Direxion", 3, 3, "ICE 7-10 Year Treasury"),
    ("TMF",  "TMV",  "20+ Year Treasury",        "Direxion", 3, 3, "ICE 20+ Year Treasury"),
    ("DRN",  "DRV",  "Real Estate",              "Direxion", 3, 3, "MSCI US REIT"),
    ("FAS",  "FAZ",  "Financial",                "Direxion", 3, 3, "Russell 1000 Financial"),
    ("HIBL", "HIBS", "S&P 500 High Beta",        "Direxion", 3, 3, "S&P 500 High Beta"),
    ("LABU", "LABD", "S&P Biotech",              "Direxion", 3, 3, "S&P Biotech"),
    ("SOXL", "SOXS", "Semiconductor",            "Direxion", 3, 3, "PHLX Semiconductor"),
    ("TECL", "TECS", "Technology",               "Direxion", 3, 3, "Tech Select Sector"),
    ("WEBL", "WEBS", "Dow Jones Internet",       "Direxion", 3, 3, "Dow Jones Internet"),
    # ---- Direxion 2X ----
    ("ERX",  "ERY",  "Energy",                   "Direxion", 2, 2, "Energy Select Sector"),
    ("GUSH", "DRIP", "S&P Oil & Gas E&P",        "Direxion", 2, 2, "S&P Oil & Gas E&P"),
    ("JNUG", "JDST", "Junior Gold Miners",       "Direxion", 2, 2, "MVIS Junior Gold Miners"),
    ("NUGT", "DUST", "Gold Miners",              "Direxion", 2, 2, "NYSE Arca Gold Miners"),
    ("TSXU", "TSXD", "Semiconductors Top 5",     "Direxion", 2, 2, "Semiconductors Top 5"),
    ("TTXU", "TTXD", "Technology Top 5",         "Direxion", 2, 2, "Technology Top 5"),
    ("AIBU", "AIBD", "AI and Big Data",          "Direxion", 2, 2, "AI & Big Data"),
    # ---- ProShares UltraPro (3X) ----
    ("TQQQ", "SQQQ", "QQQ",                      "ProShares", 3, 3, "Nasdaq-100"),
    ("UDOW", "SDOW", "Dow30",                    "ProShares", 3, 3, "Dow Jones Industrial Average"),
    ("UMDD", "SMDD", "MidCap400",                "ProShares", 3, 3, "S&P MidCap 400"),
    # ---- ProShares Ultra (2X) ----
    ("EZJ",  "EWV",  "MSCI Japan",               "ProShares", 2, 2, "MSCI Japan"),
    ("UGE",  "SZK",  "Consumer Staples",         "ProShares", 2, 2, "Consumer Staples Select Sector"),
    ("UBR",  "BZQ",  "MSCI Brazil Capped",       "ProShares", 2, 2, "MSCI Brazil Capped"),
    ("EFO",  "EFU",  "MSCI EAFE",                "ProShares", 2, 2, "MSCI EAFE"),
    ("SAA",  "SDD",  "SmallCap600",              "ProShares", 2, 2, "S&P SmallCap 600"),
    ("UPW",  "SDP",  "Utilities",                "ProShares", 2, 2, "Utilities Select Sector"),
    ("UPV",  "EPV",  "FTSE Europe",              "ProShares", 2, 2, "FTSE Developed Europe"),
    ("UCC",  "SCC",  "Consumer Discretionary",   "ProShares", 2, 2, "Consumer Discretionary Select Sector"),
    ("YCL",  "YCS",  "Yen",                      "ProShares", 2, 2, "JPY / USD"),
    ("UYM",  "SMN",  "Materials",                "ProShares", 2, 2, "Materials Select Sector"),
    ("ULE",  "EUO",  "Euro",                     "ProShares", 2, 2, "EUR / USD"),
    ("QQUP", "QQDN", "QQQ Mega",                 "ProShares", 2, 2, "Nasdaq-100 Mega Cap"),
    ("UXI",  "SIJ",  "Industrials",              "ProShares", 2, 2, "Industrials Select Sector"),
    ("BOIL", "KOLD", "Bloomberg Natural Gas",    "ProShares", 2, 2, "Bloomberg Natural Gas Sub-Index"),
    ("DIG",  "DUG",  "Energy",                   "ProShares", 2, 2, "Energy Select Sector"),
    ("BIB",  "BIS",  "Nasdaq Biotechnology",     "ProShares", 2, 2, "Nasdaq Biotechnology"),
    ("RXL",  "RXD",  "Health Care",              "ProShares", 2, 2, "Health Care Select Sector"),
    ("UCO",  "SCO",  "Bloomberg Crude Oil",      "ProShares", 2, 2, "Bloomberg Crude Oil Sub-Index"),
    ("UGL",  "GLL",  "Gold",                     "ProShares", 2, 2, "Gold (COMEX futures)"),
    ("UYG",  "SKF",  "Financials",               "ProShares", 2, 2, "Financials Select Sector"),
    ("USD",  "SSG",  "Semiconductors",           "ProShares", 2, 2, "Dow Jones U.S. Semiconductors"),
    ("AGQ",  "ZSL",  "Silver",                   "ProShares", 2, 2, "Silver"),
    # ---- ProShares asymmetric (Ultra +2X / Short -1X) ----
    ("UJB",  "SJB",  "High Yield",               "ProShares", 2, 1, "Markit iBoxx Liquid HY"),
]


# -----------------------------------------------------------------------------
# CSV parsing — Direxion + ProShares formats, auto-detected
# -----------------------------------------------------------------------------

def parse_asof(s):
    if not s:
        return None
    try:
        return dt.datetime.strptime(s, "%m/%d/%Y").date().isoformat()
    except Exception:
        return None


def _to_float(s):
    if s is None:
        return 0.0
    s = str(s).strip().replace(",", "").replace("$", "").replace("%", "")
    if s in ("", "--", "-", "N/A"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def detect_format(path):
    """Sniff format from the first non-empty line."""
    with open(path, encoding="utf-8-sig") as f:
        first = f.readline().strip()
    if first.lower().startswith("exposure weight"):
        return "proshares"
    return "direxion"


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


def parse_proshares(path):
    """ProShares CSVs have no TradeDate — use the file mtime as as_of."""
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            ticker = (r.get("Ticker") or "").strip()
            if ticker == "--":
                ticker = ""
            name   = (r.get("Description") or "").strip()
            weight = _to_float(r.get("Exposure Weight"))
            shares = _to_float(r.get("Shares/Contracts"))
            mv     = _to_float(r.get("Market Value"))
            ev     = _to_float(r.get("Exposure Value(Notional + GL)"))
            value  = mv if mv != 0 else ev
            if not ticker and not name:
                continue
            up = name.upper()
            if "SWAP" in up:
                ptype = "Swap"
            elif ("CASH" in up or "MONEY MARKET" in up or "TREASURY" in up
                  or "TRSRY" in up or "GOVT" in up or "REPURCHASE" in up):
                ptype = "Cash"
            elif ticker:
                ptype = "Equity"
            else:
                ptype = "Other"
            rows.append({
                "ticker": ticker or None,
                "name":   name,
                "shares": shares,
                "value":  value,
                "weight": weight,
                "type":   ptype,
            })
    as_of = dt.datetime.fromtimestamp(os.path.getmtime(path)).date().isoformat()
    rows.sort(key=lambda x: -abs(x["weight"]))
    return as_of, rows


def parse_holdings(path):
    return parse_proshares(path) if detect_format(path) == "proshares" else parse_direxion(path)


def find_csv(symbol):
    """ProShares CSVs ship as '<SYMBOL> Holdings.csv'; Direxion as '<SYMBOL>.csv'."""
    for name in (f"{symbol}.csv", f"{symbol} Holdings.csv"):
        p = CSV_DIR / name
        if p.exists():
            return p
    raise FileNotFoundError(f"No CSV for {symbol} in {CSV_DIR}")


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

def build_etf_row(symbol, side, name_root, sponsor, lev_bull, lev_bear, underlying):
    lev = lev_bull if side == "bull" else lev_bear
    sign = "+" if side == "bull" else "-"
    leverage_str = f"{sign}{lev}x"

    if sponsor == "Direxion":
        direction = "Bull" if side == "bull" else "Bear"
        name = f"Direxion Daily {name_root} {direction} {lev}X"
    elif sponsor == "ProShares":
        if side == "bull":
            prefix = "UltraPro" if lev == 3 else "Ultra"
        else:
            prefix = ("UltraPro Short" if lev == 3
                      else "UltraShort"     if lev == 2
                      else "Short")
        name = f"ProShares {prefix} {name_root}"
    else:
        name = f"{sponsor} {name_root}"

    return {
        "symbol":          symbol,
        "name":            name,
        "sponsor":         sponsor,
        "leverage":        leverage_str,
        "underlying":      underlying,
        "category":        "pair",
        "side":            side,
        "pair_underlying": underlying,
        "base_price":      None,
        "day_change":      None,
        "year_change":     None,
    }


def main():
    etf_rows = []
    holding_rows = []

    for bull, bear, name_root, sponsor, lev_bull, lev_bear, underlying in PAIRS:
        for sym, side in [(bull, "bull"), (bear, "bear")]:
            print(f"→ {sym} ({side})")
            csv_path = find_csv(sym)
            as_of, rows = parse_holdings(csv_path)
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
            etf_rows.append(build_etf_row(sym, side, name_root, sponsor, lev_bull, lev_bear, underlying))

    print(f"\n→ Upserting {len(etf_rows)} etfs, {len(holding_rows):,} holdings")
    upsert_batched("etfs", etf_rows, "symbol")
    upsert_batched("etf_holdings", holding_rows, "etf_symbol,rank")
    print("\n✓ Done.")


if __name__ == "__main__":
    main()
