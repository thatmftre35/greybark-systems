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

## Supabase setup

The site uses Supabase for auth (email/password with verification) and will
host data in tables in a follow-up phase.

### One-time setup

1. **Run the schema**: open the Supabase SQL editor and paste in
   `sql/01_schema.sql`, then `sql/02_rls.sql`. Hit Run on each.
2. **Enable email confirmations**: Auth → Providers → Email →
   *Confirm email* = on.
3. **Add redirect URLs** (Auth → URL Configuration → Redirect URLs):
   - `http://localhost:8000/email-verified`
   - `https://YOUR-VERCEL-DOMAIN.vercel.app/email-verified`
   - (and any custom domain `/email-verified` once configured)
4. **Site URL**: set to your Vercel domain (e.g. `https://greybark-systems.vercel.app`).

### Auth pages

| File | Route | Purpose |
|---|---|---|
| `login.html`         | `/login`           | Email + password sign-in (with `?next=` param) |
| `signup.html`        | `/signup`          | Create account; sends verification email |
| `email-verified.html`| `/email-verified`  | Supabase redirect target after email confirmation |

### What's gated

- `/holdings?etf=...` — full ETF position list requires sign-in
- `/fund?id=...` — backtest chart + headline returns are public; the holdings
  table is gated

The anon (publishable) key is in `config.js` — safe to ship; the actual
access boundary is the RLS policies in `sql/02_rls.sql`.

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
