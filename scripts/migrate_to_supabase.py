"""
One-time migration: read every *-data.js file (via scripts/dump_data.js)
and push the contents into Supabase tables.

Requires:
  - SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY in .env.local at project root
  - Schema already created (run sql/01_schema.sql then 02_rls.sql)
  - node available (used to evaluate the JS data files)

Run from project root:
  python3 scripts/migrate_to_supabase.py [--reset] [--skip-prices]
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client, Client

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env.local")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    sys.exit("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env.local")

sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def dump_js_data():
    """Run node scripts/dump_data.js and return the parsed JSON."""
    print("→ Dumping JS data via node ...")
    result = subprocess.run(
        ["node", "scripts/dump_data.js"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        sys.exit(f"node dump failed:\n{result.stderr}")
    return json.loads(result.stdout)


# -----------------------------------------------------------------------------
# Date / time helpers
# -----------------------------------------------------------------------------

def parse_asof(s):
    """Direxion 'asOf' strings are like '5/1/2026'."""
    if not s:
        return None
    try:
        return datetime.strptime(s, "%m/%d/%Y").date().isoformat()
    except Exception:
        return None


def daily_to_iso(d):
    """'2025-05-04' -> '2025-05-04T00:00:00Z'"""
    return d + "T00:00:00Z"


# Intraday strings are stored in America/New_York (see fetch_prices.py).
# Treat them as ET, convert to UTC for storage.
ET_OFFSET_DST    = timedelta(hours=-4)   # EDT
ET_OFFSET_NO_DST = timedelta(hours=-5)   # EST


def intraday_to_iso(s):
    """'2026-05-04 09:30' (assumed ET) -> ISO UTC."""
    try:
        dt_et = datetime.strptime(s, "%Y-%m-%d %H:%M")
    except Exception:
        return None
    # Rough-and-ready DST: March-second-Sunday → November-first-Sunday is EDT.
    # Close enough for daily refresh; if a single bar lands on a DST cusp we
    # just approximate by year-month.
    m = dt_et.month
    is_dst = 3 <= m <= 11
    offset = ET_OFFSET_DST if is_dst else ET_OFFSET_NO_DST
    dt_utc = dt_et - offset  # subtract to convert local→UTC
    return dt_utc.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


# -----------------------------------------------------------------------------
# Batched upsert helper
# -----------------------------------------------------------------------------

def upsert_batched(table, rows, on_conflict, batch_size=1000, label=""):
    if not rows:
        print(f"  {label or table}: 0 rows, skipping")
        return
    print(f"  {label or table}: {len(rows):,} rows ...", flush=True)
    t0 = time.time()
    for i in range(0, len(rows), batch_size):
        chunk = rows[i:i + batch_size]
        sb.table(table).upsert(chunk, on_conflict=on_conflict).execute()
        if (i // batch_size) % 25 == 24 or i + batch_size >= len(rows):
            print(f"    ... {min(i+batch_size, len(rows)):,}/{len(rows):,}", flush=True)
    print(f"    done in {time.time()-t0:.1f}s")


def reset_tables():
    """Wipe all rows from migrated tables (does NOT touch auth.* schemas)."""
    print("→ Resetting tables")
    for tbl in ("etf_holdings", "etf_prices", "etfs",
                "fund_holdings", "funds", "fund_categories",
                "stock_info"):
        sb.table(tbl).delete().neq("id" if tbl in ("etf_holdings", "fund_holdings") else
                                   ("etf_symbol" if tbl == "etf_prices" else
                                    ("symbol" if tbl == "etfs" else
                                     ("ticker" if tbl == "stock_info" else "id"))),
                                   "__never_match__").execute()
        print(f"    cleared {tbl}")


# -----------------------------------------------------------------------------
# Per-table migrations
# -----------------------------------------------------------------------------

def migrate_stock_info(data):
    print("→ stock_info")
    rows = []
    for ticker, info in data["STOCK_INFO"].items():
        rows.append({
            "ticker": ticker,
            "name":   info.get("name") or None,
            "domain": info.get("domain") or None,
        })
    upsert_batched("stock_info", rows, on_conflict="ticker")


def migrate_fund_categories(data):
    print("→ fund_categories")
    rows = []
    for cat_id, cat in data["FUND_CATEGORIES"].items():
        rows.append({
            "id":          cat_id,
            "label":       cat.get("label", cat_id),
            "description": cat.get("description"),
            "fund_ids":    cat.get("fundIds") or [],
            "sort_order":  0,
        })
    upsert_batched("fund_categories", rows, on_conflict="id")


def migrate_funds(data):
    print("→ funds + fund_holdings")
    fund_rows = []
    holding_rows = []
    for fid, f in data["FUNDS"].items():
        fund_rows.append({
            "id":         fid,
            "name":       f.get("name") or fid,
            "est_return": f.get("estReturn"),
            "returns":    f.get("returns") or {},
            "series":     f.get("series") or [],
        })
        for i, h in enumerate(f.get("rows") or []):
            holding_rows.append({
                "fund_id": fid,
                "rank":    i + 1,
                "ticker":  h.get("ticker", ""),
                "shares":  h.get("shares"),
                "usd":     h.get("usd"),
                "weight":  h.get("weight"),
            })
    upsert_batched("funds", fund_rows, on_conflict="id", label="funds")
    upsert_batched("fund_holdings", holding_rows, on_conflict="fund_id,rank",
                   label="fund_holdings")


def migrate_etfs(data):
    print("→ etfs")
    etf_rows = []

    def add(side_key, side_etf, category, pair_underlying):
        etf_rows.append({
            "symbol":          side_etf["symbol"],
            "name":            side_etf.get("name"),
            "sponsor":         side_etf.get("sponsor"),
            "leverage":        side_etf.get("leverage"),
            "underlying":      side_etf.get("underlying"),
            "category":        category,
            "side":            side_key,
            "pair_underlying": pair_underlying,
            "base_price":      side_etf.get("basePrice"),
            "day_change":      side_etf.get("dayChange"),
            "year_change":     side_etf.get("yearChange"),
        })

    for pair in data["ETF_DATA"].get("pairs", []):
        ul = pair["bull"].get("underlying")
        add("bull", pair["bull"], "pair", ul)
        add("bear", pair["bear"], "pair", ul)
    for etf in data["ETF_DATA"].get("single", []):
        add("single", etf, "single", None)
    for pair in data["ETF_DATA"].get("stocks", []):
        ul = pair["bull"].get("underlying")
        add("bull", pair["bull"], "stock_pair", ul)
        add("bear", pair["bear"], "stock_pair", ul)

    upsert_batched("etfs", etf_rows, on_conflict="symbol")


def migrate_etf_holdings(data):
    print("→ etf_holdings")
    rows = []
    for symbol, payload in data["HOLDINGS"].items():
        as_of = parse_asof(payload.get("asOf"))
        for i, h in enumerate(payload.get("rows") or []):
            rows.append({
                "etf_symbol":    symbol,
                "rank":          i + 1,
                "ticker":        (h.get("ticker") or "").strip() or None,
                "name":          h.get("name"),
                "shares":        h.get("shares"),
                "value":         h.get("value"),
                "weight":        h.get("weight"),
                "position_type": h.get("type"),
                "as_of":         as_of,
            })
    upsert_batched("etf_holdings", rows, on_conflict="etf_symbol,rank")


def migrate_etf_prices(data):
    print("→ etf_prices")
    rows = []
    for symbol, payload in data["PRICES"].items():
        for d, close in payload.get("daily") or []:
            rows.append({
                "etf_symbol":  symbol,
                "ts":          daily_to_iso(d),
                "granularity": "daily",
                "close":       close,
            })
        for ts, close in payload.get("intraday") or []:
            iso = intraday_to_iso(ts)
            if not iso:
                continue
            rows.append({
                "etf_symbol":  symbol,
                "ts":          iso,
                "granularity": "intraday",
                "close":       close,
            })
    print(f"  total {len(rows):,} price rows")
    upsert_batched("etf_prices", rows, on_conflict="etf_symbol,granularity,ts",
                   batch_size=2000, label="etf_prices")


# -----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="Truncate tables before insert")
    ap.add_argument("--skip-prices", action="store_true", help="Don't migrate the ~290K-row etf_prices table")
    args = ap.parse_args()

    data = dump_js_data()

    if args.reset:
        reset_tables()

    # Order matters because of foreign keys.
    migrate_stock_info(data)
    migrate_fund_categories(data)
    migrate_funds(data)
    migrate_etfs(data)
    migrate_etf_holdings(data)
    if not args.skip_prices:
        migrate_etf_prices(data)

    print("\n✓ Migration complete.")


if __name__ == "__main__":
    main()
