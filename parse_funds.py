"""
Parse institutional fund holdings from /Users/tre/Downloads/csvs/ + ranking
from /Users/tre/Downloads/top 20.xlsx into funds-data.js.

Source files are a mix of plain CSV and RTF-wrapped CSV. Both are flattened
to (ticker, shares, usd, weight) tuples per fund.
"""

import csv
import io
import re
import json
import time
import datetime as dt
import openpyxl
from pathlib import Path
from curl_cffi import requests as curl_requests
import yfinance as yf

CSV_DIR   = Path("/Users/tre/Downloads/csvs")
XLSX_PATH = Path("/Users/tre/Downloads/top 20.xlsx")
OUT_PATH  = Path("/Users/tre/Desktop/QBridge Site/funds-data.js")

# yfinance with browser-impersonating session (avoids rate limits)
YF_SESSION = curl_requests.Session(impersonate="chrome")
PRICE_PERIOD = "3y"  # daily history depth — drives ALL timeframe

# Maps fund name (as written in the xlsx) to its file in csvs/.
FUND_FILE_MAP = {
    "Anatole Investment Management Ltd":                          "Anatole",
    "Elemental Capital Partners LLC":                             "Elemental",
    "BRC Group Holdings, Inc.":                                   "BRC.rtf",
    "Brooklands Fund Management Ltd":                             "brooklands.rtf",
    "NVIDIA CORP":                                                "NVDA.rtf",
    "Situational Awareness LP":                                   "Situational Awareness.rtf",
    "Maytree Asset Management Ltd":                               "Maytree.rtf",
    "Equinox Partners Investment Management LLC":                 "Equinox.rtf",
    "Foresite Capital Management V, LLC":                         "Foresite.rtf",
    "Maple Rock Capital Partners Inc.":                           "Maple Rock.rtf",
    "Divisar Capital Management LLC":                             "Divisar.rtf",
    "Silver Heights Capital Management Inc":                      "Silver Heights.rtf",
    "M37 Management LP":                                          "M37.rtf",
    "Central Asset Investments & Management Holdings (HK) Ltd":   "Central.rtf",
    "Evergreen Quality Fund GP, Ltd.":                            "evergreen.rtf",
    "ARCH Venture Management, LLC":                               "arch.rtf",
    "AIHC Capital Management Ltd":                                "aich.rtf",
    "Arosa Capital Management LP":                                "arosa.rtf",
    "Amanah Holdings Trust":                                      "amanah.rtf",
    "Nextech Invest, Ltd.":                                       "nextech.rtf",
}


def slug(name: str) -> str:
    """Make a JS-friendly identifier from a fund name."""
    s = re.sub(r"[^a-z0-9]+", "_", name.lower())
    return s.strip("_")[:32]


def strip_rtf(text: str) -> str:
    """Light RTF stripper — removes control words, escapes, and braces."""
    # Remove control words like \rtf1, \fs22, \margl1440 (with optional trailing space)
    text = re.sub(r"\\[a-zA-Z]+-?\d*\s?", " ", text)
    # Remove other escape sequences (\* \{ \} etc.)
    text = re.sub(r"\\.", "", text)
    # Drop braces
    text = text.replace("{", "").replace("}", "")
    # Collapse whitespace except newlines
    lines = []
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def _clean_num(s: str) -> str:
    """Strip whitespace, $, comma, %, trailing RTF backslashes from a value cell."""
    return s.strip().rstrip("\\").replace(",", "").replace("$", "").replace("%", "").strip()


def parse_rows(content: str):
    """Pull (ticker, shares, usd, weight) tuples from a CSV-ish blob.

    Handles:
      - quoted values with internal commas (real CSV)
      - dollar signs and percent signs in numeric columns
      - trailing RTF '\\' line terminators
    """
    # Drop trailing RTF '\\' line terminators before passing to csv.reader.
    cleaned_lines = []
    for raw in content.splitlines():
        line = raw.rstrip().rstrip("\\").rstrip(",").rstrip()
        if line:
            cleaned_lines.append(line)
    blob = "\n".join(cleaned_lines)

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
        rows.append({
            "ticker": ticker,
            "shares": shares,
            "usd":    usd,
            "weight": weight,
        })
    rows.sort(key=lambda r: -r["weight"])
    return rows


def fetch_daily_prices(symbol):
    """Returns dict {date_str: close} for ~3y daily history, or {} on failure."""
    try:
        df = yf.Ticker(symbol, session=YF_SESSION).history(
            period=PRICE_PERIOD, interval="1d", auto_adjust=True, actions=False,
        )
    except Exception as e:
        print(f"    ! {symbol}: {e}")
        return {}
    if df is None or df.empty:
        return {}
    out = {}
    for ts, row in df.iterrows():
        close = float(row["Close"])
        if close > 0:
            out[ts.strftime("%Y-%m-%d")] = round(close, 4)
    return out


def compute_portfolio_series(holdings, prices_by_ticker):
    """
    Buy-and-hold weighted backtest with static (current) weights.

    Returns (dates[], values[]) where values are normalized so that the
    first day with a complete-enough basket = 100.

    For each trading day we:
      1. Take all holdings with a price on both that day and the start date.
      2. Re-normalize their weights to sum to 1 (excludes anything missing).
      3. Sum weight_i * price_i[t] / price_i[0].
    """
    # Collect the union of trading dates across all available tickers
    all_dates = set()
    for tk in prices_by_ticker.values():
        all_dates.update(tk.keys())
    if not all_dates:
        return [], []
    dates = sorted(all_dates)

    # Filter to holdings that have any price data
    held = [h for h in holdings if h["ticker"] in prices_by_ticker
            and prices_by_ticker[h["ticker"]]]
    if not held:
        return [], []

    # Find the first date where at least 60% of weight is priced (ignore
    # IPO-effects from early years where many of the holdings didn't exist)
    weight_total = sum(h["weight"] for h in held)
    if weight_total <= 0:
        return [], []

    start_idx = None
    for i, d in enumerate(dates):
        priced_weight = sum(
            h["weight"] for h in held
            if d in prices_by_ticker[h["ticker"]]
        )
        if priced_weight / weight_total >= 0.6:
            start_idx = i
            break
    if start_idx is None:
        return [], []

    dates = dates[start_idx:]

    # Anchor each ticker to its first price ON OR AFTER the start date.
    anchors = {}
    for h in held:
        tk_prices = prices_by_ticker[h["ticker"]]
        for d in dates:
            if d in tk_prices:
                anchors[h["ticker"]] = tk_prices[d]
                break

    out_dates = []
    out_values = []
    for d in dates:
        priced = [(h, prices_by_ticker[h["ticker"]].get(d), anchors.get(h["ticker"]))
                  for h in held]
        priced = [(h, p, a) for (h, p, a) in priced if p and a]
        if not priced:
            continue
        weight_in_basket = sum(h["weight"] for (h, _, _) in priced)
        if weight_in_basket <= 0:
            continue
        val = 0.0
        for (h, p, a) in priced:
            w = h["weight"] / weight_in_basket
            val += w * (p / a)
        out_dates.append(d)
        out_values.append(round(val * 100, 4))
    return out_dates, out_values


def returns_for_periods(dates, values):
    """For a daily series, compute % returns for standard windows."""
    if len(values) < 2:
        return {}
    last = values[-1]
    last_date = dt.date.fromisoformat(dates[-1])
    out = {}

    # Window-by-trading-days for fixed-period returns
    fixed = {"1D": 2, "1W": 5, "1M": 22, "3M": 65, "1Y": 252, "3Y": 756}
    for tf, n in fixed.items():
        if len(values) < n + 1:
            continue
        start = values[-(n + 1)]
        if start > 0:
            out[tf] = round((last / start - 1) * 100, 2)

    # YTD: first trading day of last_date.year
    year = last_date.year
    for d, v in zip(dates, values):
        if d.startswith(f"{year}-") and v > 0:
            out["YTD"] = round((last / v - 1) * 100, 2)
            break

    # ALL: full series
    if values[0] > 0:
        out["ALL"] = round((last / values[0] - 1) * 100, 2)

    return out


def main():
    if not XLSX_PATH.exists():
        raise SystemExit(f"missing {XLSX_PATH}")

    wb = openpyxl.load_workbook(XLSX_PATH)
    ws = wb.active
    fund_list = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        name, est_return = (row[0], row[1]) if len(row) >= 2 else (None, None)
        if name:
            fund_list.append({
                "name": str(name).strip(),
                "estReturn": float(est_return) if est_return is not None else None,
            })

    # ---- Phase 1: parse all fund holdings ----
    funds = {}
    fund_id_order = []
    all_tickers = set()
    for entry in fund_list:
        fname = entry["name"]
        filename = FUND_FILE_MAP.get(fname)
        if not filename:
            print(f"WARN: no file mapping for {fname!r}")
            continue
        path = CSV_DIR / filename
        if not path.exists():
            print(f"WARN: missing file {path}")
            continue
        raw = path.read_text(errors="replace")
        content = strip_rtf(raw) if filename.lower().endswith(".rtf") else raw
        rows = parse_rows(content)
        fund_id = slug(fname)
        fund_id_order.append(fund_id)
        funds[fund_id] = {
            "name": fname,
            "estReturn": entry["estReturn"],
            "rows": rows,
        }
        for r in rows:
            all_tickers.add(r["ticker"])
        print(f"  {fname:<60} {len(rows):>3} holdings")

    # ---- Phase 2: fetch stock prices ----
    print(f"\nFetching daily prices for {len(all_tickers)} tickers ...")
    prices = {}
    failures = []
    for i, tk in enumerate(sorted(all_tickers), 1):
        if i % 25 == 0:
            print(f"  ... {i}/{len(all_tickers)}")
        ph = fetch_daily_prices(tk)
        if ph:
            prices[tk] = ph
        else:
            failures.append(tk)
    if failures:
        print(f"  no data for {len(failures)} tickers: {', '.join(failures)}")

    # ---- Phase 3: backtest each fund ----
    print(f"\nComputing backtests ...")
    for fid, f in funds.items():
        ph_subset = {tk: prices[tk] for tk in {h["ticker"] for h in f["rows"]} if tk in prices}
        dates, values = compute_portfolio_series(f["rows"], ph_subset)
        f["series"] = list(zip(dates, values))
        f["returns"] = returns_for_periods(dates, values)
        miss = [h["ticker"] for h in f["rows"] if h["ticker"] not in prices]
        print(f"  {f['name']:<60} {len(values):>4} pts · 1Y={f['returns'].get('1Y','—')}% · missing={len(miss)}")

    # ---- Phase 4: write funds-data.js ----
    out_lines = [
        f"// Generated by parse_funds.py at {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "// Institutional fund holdings + buy-and-hold backtest series.",
        "// Re-run after updating /Users/tre/Downloads/csvs/ or top 20.xlsx.",
        "",
        "const FUNDS = {};",
        "",
    ]

    for fid in fund_id_order:
        f = funds[fid]
        out_lines.append(f"// ----- {f['name']} ({len(f['rows'])} holdings) -----")
        out_lines.append(f'FUNDS["{fid}"] = {{')
        out_lines.append(f"  id: \"{fid}\",")
        out_lines.append(f"  name: {json.dumps(f['name'])},")
        out_lines.append(f"  estReturn: {f['estReturn']},")
        out_lines.append(f"  returns: {json.dumps(f['returns'])},")
        out_lines.append(f"  series: " + json.dumps(f["series"], separators=(",", ":")) + ",")
        out_lines.append(f"  rows: [")
        for r in f["rows"]:
            out_lines.append(
                f'    {{ ticker:{json.dumps(r["ticker"])}, '
                f'shares:{r["shares"]}, usd:{r["usd"]}, weight:{r["weight"]} }},'
            )
        out_lines.append(f"  ]")
        out_lines.append("};")
        out_lines.append("")

    out_lines.append("")
    out_lines.append("const FUND_CATEGORIES = {")
    out_lines.append("  top20: {")
    out_lines.append("    id: \"top20\",")
    out_lines.append("    label: \"Top 20 Performing Funds (over $100M AUM)\",")
    out_lines.append("    description: \"Institutional funds ranked by trailing performance. Backtest returns computed from current holdings + weights.\",")
    out_lines.append(f"    fundIds: {json.dumps(fund_id_order)},")
    out_lines.append("  },")
    out_lines.append("};")
    out_lines.append("")

    OUT_PATH.write_text("\n".join(out_lines))
    print(f"\nWrote {OUT_PATH} ({OUT_PATH.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
