"""Parse Direxion CSV holdings into JS object literals for holdings.html."""
import csv
import json
import sys
from pathlib import Path

CSV_DIR = Path("/Users/tre/Desktop/QBridge Site/csvs")

ETFS = [
    ("SPXL", "SPXL.csv"),
    ("SPXS", "SPXS.csv"),
    ("TNA",  "TNA.csv"),
    ("TZA",  "TZA.csv"),
    ("HIBL", "HIBL.csv"),
    ("HIBS", "HIBS.csv"),
    ("YINN", "YINN.csv"),
    ("YANG", "YANG.csv"),
    ("EDC",  "EDC.csv"),
    ("EDZ",  "EDZ.csv"),
    ("LABU", "LABU.csv"),
    ("LABD", "LABD.csv"),
    ("FAS",  "FAS.csv"),
    ("FAZ",  "FAZ.csv"),
    ("WEBL", "WEBL.csv"),
    ("WEBS", "WEBS.csv"),
    ("DRN",  "DRN.csv"),
    ("DRV",  "DRV.csv"),
    ("SOXL", "SOXL.csv"),
    ("SOXS", "SOXS.csv"),
    ("TECL", "TECL.csv"),
    ("TECS", "TECS.csv"),
    ("TYD",  "TYD.csv"),
    ("TYO",  "TYO.csv"),
    ("TMF",  "TMF.csv"),
    ("TMV",  "TMV.csv"),
    ("AIBU", "AIBU.csv"),
    ("AIBD", "AIBD.csv"),
    ("GUSH", "GUSH.csv"),
    ("DRIP", "DRIP.csv"),
    ("JNUG", "JNUG.csv"),
    ("JDST", "JDST.csv"),
    ("NUGT", "NUGT.csv"),
    ("DUST", "DUST.csv"),
    ("TQQQ", "TQQQ Holdings.csv"),
    ("SQQQ", "SQQQ Holdings.csv"),
    ("QLD",  "QLD Holdings.csv"),
    ("QID",  "QID Holdings.csv"),
    ("AGQ",  "AGQ Holdings.csv"),
    ("ZSL",  "ZSL Holdings.csv"),
    ("EZJ",  "EZJ Holdings.csv"),
    ("EWV",  "EWV Holdings.csv"),
    ("UGE",  "UGE Holdings.csv"),
    ("SZK",  "SZK Holdings.csv"),
    ("UBR",  "UBR Holdings.csv"),
    ("BZQ",  "BZQ Holdings.csv"),
    ("UPW",  "UPW Holdings.csv"),
    ("SDP",  "SDP Holdings.csv"),
    ("UPV",  "UPV Holdings.csv"),
    ("EPV",  "EPV Holdings.csv"),
    ("UCC",  "UCC Holdings.csv"),
    ("SCC",  "SCC Holdings.csv"),
    ("YCL",  "YCL Holdings.csv"),
    ("YCS",  "YCS Holdings.csv"),
    ("UYM",  "UYM Holdings.csv"),
    ("SMN",  "SMN Holdings.csv"),
    ("ULE",  "ULE Holdings.csv"),
    ("EUO",  "EUO Holdings.csv"),
    ("UXI",  "UXI Holdings.csv"),
    ("SIJ",  "SIJ Holdings.csv"),
    ("BOIL", "BOIL Holdings.csv"),
    ("KOLD", "KOLD Holdings.csv"),
    ("UJB",  "UJB Holdings.csv"),
    ("SJB",  "SJB Holdings.csv"),
    ("DIG",  "DIG Holdings.csv"),
    ("DUG",  "DUG Holdings.csv"),
    ("RXL",  "RXL Holdings.csv"),
    ("RXD",  "RXD Holdings.csv"),
    ("UGL",  "UGL Holdings.csv"),
    ("GLL",  "GLL Holdings.csv"),
    ("UYG",  "UYG Holdings.csv"),
    ("SKF",  "SKF Holdings.csv"),
    # Single-direction (bull-only) — Direxion 3X / 2X
    ("DPST", "DPST.csv"),
    ("TPOR", "TPOR.csv"),
    ("RETL", "RETL.csv"),
    ("EURL", "EURL.csv"),
    ("MEXX", "MEXX.csv"),
    ("KORU", "KORU.csv"),
    ("DFEN", "DFEN.csv"),
    ("NAIL", "NAIL.csv"),
    ("PILL", "PILL.csv"),
    ("CWEB", "CWEB.csv"),
    ("INDL", "INDL.csv"),
    ("FNGG", "FNGG.csv"),
    ("UBOT", "UBOT.csv"),
    ("URAA", "URAA.csv"),
    ("QQQU", "QQQU.csv"),
    # Single-direction (bull-only) — ProShares 2X
    ("LTL",  "LTL Holdings.csv"),
    ("UCOP", "UCOP Holdings.csv"),
    ("UCYB", "UCYB Holdings.csv"),
    ("UPAL", "UPAL Holdings.csv"),
    ("UPLT", "UPLT Holdings.csv"),
    ("SKYU", "SKYU Holdings.csv"),
    # Single-stock leveraged pairs — Direxion 2X bull / 1X bear
    ("AAPU", "AAPU.csv"),
    ("AAPD", "AAPD.csv"),
    ("AMUU", "AMUU.csv"),
    ("AMDD", "AMDD.csv"),
    ("AMZU", "AMZU.csv"),
    ("AMZD", "AMZD.csv"),
    ("AVL",  "AVL.csv"),
    ("AVS",  "AVS.csv"),
    ("CSCL", "CSCL.csv"),
    ("CSCS", "CSCS.csv"),
    ("GGLL", "GGLL.csv"),
    ("GGLS", "GGLS.csv"),
    ("METU", "METU.csv"),
    ("METD", "METD.csv"),
    ("MSFU", "MSFU.csv"),
    ("MSFD", "MSFD.csv"),
    ("MUU",  "MUU.csv"),
    ("MUD",  "MUD.csv"),
    ("NFXL", "NFXL.csv"),
    ("NFXS", "NFXS.csv"),
    ("NVDU", "NVDU.csv"),
    ("NVDD", "NVDD.csv"),
    ("ORCU", "ORCU.csv"),
    ("ORCS", "ORCS.csv"),
    ("PALU", "PALU.csv"),
    ("PALD", "PALD.csv"),
    ("PLTU", "PLTU.csv"),
    ("PLTD", "PLTD.csv"),
    ("QCMU", "QCMU.csv"),
    ("QCMD", "QCMD.csv"),
    ("TSLL", "TSLL.csv"),
    ("TSLS", "TSLS.csv"),
    ("TSMX", "TSMX.csv"),
    ("TSMZ", "TSMZ.csv"),
]

import os
import datetime as dt


def detect_format(path):
    """Sniff the holdings CSV format from its first non-empty line."""
    with open(path, encoding="utf-8-sig") as f:
        first = f.readline().strip()
    if first.lower().startswith("exposure weight"):
        return "proshares"
    return "direxion"


def parse(path):
    """Dispatch to the right parser based on file format."""
    fmt = detect_format(path)
    if fmt == "proshares":
        return parse_proshares(path)
    return parse_direxion(path)


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


def parse_proshares(path):
    """Returns (asOf, rows[]) for a ProShares-format holdings CSV.

    Columns: Exposure Weight, Ticker, Description, Exposure Value(Notional + GL),
             Market Value, Shares/Contracts. No TradeDate column, so we use
             the file mtime as the as-of date.
    """
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
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
                "ticker": ticker or "—",
                "name":   name,
                "shares": shares,
                "value":  value,
                "weight": weight,
                "type":   ptype,
            })

    mtime = os.path.getmtime(path)
    as_of = dt.datetime.fromtimestamp(mtime).strftime("%-m/%-d/%Y")
    rows.sort(key=lambda x: -abs(x["weight"]))
    return as_of, rows


def parse_direxion(path):
    """Returns (asOf, rows[]) for a Direxion-format CSV."""
    # Direxion exports start with: fund name, ticker, "Shares Outstanding:N",
    # then 1-2 blank lines, then the column header row that starts with
    # "TradeDate". Scan forward until we hit it, then hand the rest to DictReader.
    with open(path, encoding="utf-8-sig") as f:
        while True:
            pos = f.tell()
            line = f.readline()
            if not line:
                return None, []
            if line.lstrip().startswith('"TradeDate"') or line.startswith("TradeDate"):
                f.seek(pos)
                break
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
            # Classify positions: equity tickers, ETFs, index swaps, cash.
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
                as_of = (r.get("TradeDate") or "").split(" ")[0]
            rows.append({
                "ticker": ticker or "—",
                "name":   name,
                "shares": shares,
                "value":  value,
                "weight": pct,
                "type":   ptype,
            })
    # Sort: real equity holdings descending, then cash/swap by absolute weight
    rows.sort(key=lambda x: (-abs(x["weight"]),))
    return as_of, rows


def js_literal(rows):
    """Render rows as a JS array of object literals, compact."""
    parts = []
    for r in rows:
        shares = int(r["shares"]) if r["shares"].is_integer() else r["shares"]
        value  = round(r["value"], 2)
        weight = round(r["weight"], 4)
        name = r["name"].replace('\\', '\\\\').replace('"', '\\"')
        ticker = r["ticker"].replace('"', '\\"')
        parts.append(
            f'    {{ ticker:"{ticker}", name:"{name}", shares:{shares}, '
            f'value:{value}, weight:{weight}, type:"{r["type"]}" }}'
        )
    return ",\n".join(parts)


for sym, fname in ETFS:
    as_of, rows = parse(CSV_DIR / fname)
    print(f"// ----- {sym} ({len(rows)} holdings, as of {as_of}) -----")
    print(f'HOLDINGS["{sym}"] = {{')
    print(f'  asOf: "{as_of}",')
    print(f'  rows: [')
    print(js_literal(rows))
    print(f'  ]')
    print(f'}};')
    print()
