#!/usr/bin/env python3
"""
Parse RTF holdings from /Users/tre/Downloads/under 100 aum holdings/ into
funds-under-aum-data.js — extends the global FUNDS dict and adds
FUND_CATEGORIES.top20under so funds.html can render a second tab.

Mirrors parse_funds.py's RTF stripper and backtest-series math.
"""

import csv
import datetime as dt
import io
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote

from curl_cffi import requests as curl_requests
import yfinance as yf

ROOT     = Path(__file__).resolve().parent.parent
SRC_DIR  = Path("/Users/tre/Downloads/under 100 aum holdings")
OUT_PATH = ROOT / "funds-under-aum-data.js"

YF_SESSION   = curl_requests.Session(impersonate="chrome")
PRICE_PERIOD = "3y"


# -----------------------------------------------------------------------------
# RTF + CSV helpers (lifted from parse_funds.py)
# -----------------------------------------------------------------------------

def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower())
    return s.strip("_")[:32]


def strip_rtf(text: str) -> str:
    text = re.sub(r"\\[a-zA-Z]+-?\d*\s?", " ", text)
    text = re.sub(r"\\.", "", text)
    text = text.replace("{", "").replace("}", "")
    lines = []
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def _clean_num(s: str) -> str:
    return s.strip().rstrip("\\").replace(",", "").replace("$", "").replace("%", "").strip()


def parse_rows(content: str):
    cleaned = []
    for raw in content.splitlines():
        line = raw.rstrip().rstrip("\\").rstrip(",").rstrip()
        if line:
            cleaned.append(line)
    blob = "\n".join(cleaned)
    reader = csv.reader(io.StringIO(blob), skipinitialspace=True)
    rows = []
    for parts in reader:
        if len(parts) < 4:
            continue
        head = parts[0].strip().lower()
        if head in ("stock", "ticker", "symbol"):
            continue
        ticker = parts[0].strip().upper()
        if not ticker or not re.match(r"^[A-Z0-9.\-]+$", ticker):
            continue
        try:
            shares = int(float(_clean_num(parts[1])))
            usd    = int(round(float(_clean_num(parts[2]))))
            weight = float(_clean_num(parts[3]))
        except (ValueError, IndexError):
            continue
        rows.append({"ticker": ticker, "shares": shares, "usd": usd, "weight": weight})
    rows.sort(key=lambda r: -r["weight"])
    return rows


def parse_rtf_file(path: Path):
    """Returns (fund_name, holdings_rows). Pulls the name from the QuiverQuant
    URL in the file's HYPERLINK target (URL-decoded)."""
    raw = path.read_text(encoding="utf-8", errors="ignore")
    name = None
    m = re.search(r'HYPERLINK\s*"([^"]+)"', raw)
    if m:
        url = m.group(1).rstrip("/")
        last = url.split("/")[-1]
        name = unquote(last).replace("+", " ").strip()
    if not name:
        name = path.stem
    rows = parse_rows(strip_rtf(raw))
    return name, rows


# -----------------------------------------------------------------------------
# yfinance + backtest (also lifted from parse_funds.py)
# -----------------------------------------------------------------------------

def fetch_daily_prices(symbol):
    try:
        df = yf.Ticker(symbol, session=YF_SESSION).history(
            period=PRICE_PERIOD, interval="1d", auto_adjust=True, actions=False)
    except Exception as e:
        print(f"    ! {symbol}: {e}")
        return {}
    if df is None or df.empty:
        return {}
    out = {}
    for ts, row in df.iterrows():
        c = float(row["Close"])
        if c > 0:
            out[ts.strftime("%Y-%m-%d")] = round(c, 4)
    return out


def compute_portfolio_series(holdings, prices_by_ticker):
    all_dates = set()
    for tk in prices_by_ticker.values():
        all_dates.update(tk.keys())
    if not all_dates:
        return [], []
    dates = sorted(all_dates)
    held = [h for h in holdings if h["ticker"] in prices_by_ticker
            and prices_by_ticker[h["ticker"]]]
    if not held:
        return [], []
    weight_total = sum(h["weight"] for h in held)
    if weight_total <= 0:
        return [], []
    start_idx = None
    for i, d in enumerate(dates):
        priced_weight = sum(h["weight"] for h in held
                            if d in prices_by_ticker[h["ticker"]])
        if priced_weight / weight_total >= 0.6:
            start_idx = i
            break
    if start_idx is None:
        return [], []
    dates = dates[start_idx:]
    anchors = {}
    for h in held:
        tk_prices = prices_by_ticker[h["ticker"]]
        for d in dates:
            if d in tk_prices:
                anchors[h["ticker"]] = tk_prices[d]
                break
    out_dates, out_values = [], []
    for d in dates:
        priced = [(h, prices_by_ticker[h["ticker"]].get(d), anchors.get(h["ticker"]))
                  for h in held]
        priced = [(h, p, a) for (h, p, a) in priced if p and a]
        if not priced:
            continue
        wsum = sum(h["weight"] for (h, _, _) in priced)
        if wsum <= 0:
            continue
        val = 0.0
        for (h, p, a) in priced:
            w = h["weight"] / wsum
            val += w * (p / a)
        out_dates.append(d)
        out_values.append(round(val * 100, 4))
    return out_dates, out_values


def returns_for_periods(dates, values):
    if len(values) < 2:
        return {}
    last = values[-1]
    last_date = dt.date.fromisoformat(dates[-1])
    out = {}
    fixed = {"1D": 2, "1W": 5, "1M": 22, "3M": 65, "1Y": 252, "3Y": 756}
    for tf, n in fixed.items():
        if len(values) < n + 1:
            continue
        start = values[-(n + 1)]
        if start > 0:
            out[tf] = round((last / start - 1) * 100, 2)
    year = last_date.year
    for d, v in zip(dates, values):
        if d.startswith(f"{year}-") and v > 0:
            out["YTD"] = round((last / v - 1) * 100, 2)
            break
    if values[0] > 0:
        out["ALL"] = round((last / values[0] - 1) * 100, 2)
    return out


# -----------------------------------------------------------------------------
# Output writer
# -----------------------------------------------------------------------------

def write_js(funds, out_path):
    with out_path.open("w") as f:
        f.write("// Generated by scripts/load_under_aum_funds.py at "
                f"{dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%SZ')}\n")
        f.write("// Top-20 funds under $100M AUM. Extends global FUNDS dict\n")
        f.write("// and adds FUND_CATEGORIES.top20under for the funds.html tab.\n\n")
        for fund in funds:
            rows_js = ",\n".join(
                f'    {{ ticker:"{h["ticker"]}", shares:{h["shares"]}, usd:{h["usd"]}, weight:{h["weight"]} }}'
                for h in fund["rows"])
            series = list(zip(fund["dates"], fund["values"]))
            series_js  = json.dumps([[d, v] for d, v in series], separators=(",", ":"))
            returns_js = json.dumps(fund["returns"], separators=(",", ":"))
            est = fund.get("estReturn")
            est_js = "null" if est is None else str(est)
            f.write(f'FUNDS["{fund["id"]}"] = {{\n')
            f.write(f'  id: "{fund["id"]}",\n')
            f.write(f'  name: {json.dumps(fund["name"])},\n')
            f.write(f'  estReturn: {est_js},\n')
            f.write(f'  returns: {returns_js},\n')
            f.write(f'  series: {series_js},\n')
            f.write(f'  rows: [\n{rows_js}\n  ]\n')
            f.write("};\n\n")
        ids = [fund["id"] for fund in funds]
        f.write("FUND_CATEGORIES.top20under = {\n")
        f.write('  id: "top20under",\n')
        f.write('  label: "Top 20 Under $100M AUM",\n')
        f.write('  description: "Smaller-AUM institutional funds. Backtest returns computed from current holdings + weights.",\n')
        f.write(f'  fundIds: {json.dumps(ids)},\n')
        f.write("};\n")


# -----------------------------------------------------------------------------

def main():
    if not SRC_DIR.exists():
        sys.exit(f"Source folder missing: {SRC_DIR}")
    rtfs = sorted(SRC_DIR.glob("*.rtf"))
    print(f"Found {len(rtfs)} RTF files")

    funds = []
    tickers = set()
    for path in rtfs:
        name, rows = parse_rtf_file(path)
        if not rows:
            print(f"  ! {path.name}: no holdings parsed")
            continue
        fid = slug(name)
        funds.append({"id": fid, "name": name, "rows": rows})
        tickers.update(h["ticker"] for h in rows)
        print(f"  {path.name}  →  {name}  ({len(rows)} holdings, id={fid})")

    print(f"\nFetching {len(tickers)} unique tickers from yfinance ...")
    prices = {}
    for i, t in enumerate(sorted(tickers), 1):
        prices[t] = fetch_daily_prices(t)
        time.sleep(0.25)
        if i % 20 == 0 or i == len(tickers):
            print(f"  {i}/{len(tickers)}")

    print("\nComputing backtest series + returns")
    for fund in funds:
        ph_subset = {h["ticker"]: prices.get(h["ticker"], {}) for h in fund["rows"]}
        dates, values = compute_portfolio_series(fund["rows"], ph_subset)
        fund["dates"]  = dates
        fund["values"] = values
        fund["returns"] = returns_for_periods(dates, values)
        fund["estReturn"] = (fund["returns"].get("1Y")
                             or fund["returns"].get("ALL"))
        print(f"  {fund['name']}: {len(values)} pts, returns={fund['returns']}")

    write_js(funds, OUT_PATH)
    print(f"\n✓ Wrote {OUT_PATH}  ({OUT_PATH.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
