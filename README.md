# GreyBark Systems

Static site for GreyBark Systems — quantitative strategies for leveraged ETFs,
institutional holdings, insider trades, and federal contracts.

## Stack

- Plain HTML / CSS / vanilla JS — no build step
- Static-hosted on Vercel
- Data baked into `*-data.js` files at build time by Python scripts

## Pages

| File | URL | Purpose |
|---|---|---|
| `index.html`         | `/`                  | Home / overview |
| `leveraged-etfs.html`| `/leveraged-etfs`    | Leveraged ETF universe + per-ETF chart modal |
| `holdings.html`      | `/holdings?etf=SYM`  | Per-ETF holdings detail (linked from the ETF modal) |
| `funds.html`         | `/funds`             | Institutional fund holdings (Holdings tab) |
| `fund.html`          | `/fund?id=FUND_ID`   | Per-fund backtest + holdings detail |

## Data files (generated)

| File | Size | Source |
|---|---|---|
| `holdings-data.js` | ~380 KB | `parse_holdings.py` ← `csvs/*.csv` |
| `prices-data.js`   | ~9 MB   | `fetch_prices.py`  ← yfinance |
| `funds-data.js`    | ~380 KB | `parse_funds.py`   ← `csvs/*.rtf` + `top 20.xlsx` + yfinance |
| `stock-info.js`    | ~23 KB  | `fetch_stock_info.py` ← yfinance |

## Refreshing data locally

```bash
# ETF holdings (re-runs after new CSVs in csvs/)
python3 parse_holdings.py

# ETF prices (yfinance, ~5 min for ~80 ETFs)
python3 fetch_prices.py

# Fund holdings + backtests (yfinance for stock prices, ~3 min)
python3 parse_funds.py

# Per-stock company name + domain (yfinance, ~5 min for ~350 tickers)
python3 fetch_stock_info.py
```

After re-running, the `*-data.js` files update; commit and push to redeploy.

## Logo

`generate_logo.py` builds `greybark-logo.png` (1024×1024 pixel-art mark) using
PIL. Edit constants at the top of the script to tweak.

## Deploy

Connected to Vercel — every push to `main` triggers a deploy.

```bash
git push
```

For local preview, just open the HTML files in a browser, or:

```bash
python3 -m http.server 8000
# then http://localhost:8000
```
