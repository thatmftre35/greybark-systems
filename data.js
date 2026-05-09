/* ----------------------------------------------------------------------
   data.js — Supabase query helpers used by every page.
   Depends on config.js (window.sb).

   All helpers are async, return plain JSON shapes that mirror the original
   *-data.js objects so the existing render code keeps working with minimal
   changes.

   Includes a small in-memory cache so the same query inside a session
   doesn't hit the network twice.
   ---------------------------------------------------------------------- */

const __cache = new Map();
function cached(key, ttlMs, fn) {
  const hit = __cache.get(key);
  if (hit && Date.now() - hit.at < ttlMs) return hit.value;
  const value = fn();           // value is the promise
  __cache.set(key, { at: Date.now(), value });
  return value;
}
const FIVE_MIN = 5 * 60 * 1000;

/* =========================================================
   ETFs (leveraged ETF universe)
   ========================================================= */

/** Returns ETF_DATA-shaped object: { pairs:[{bull,bear}], single:[], stocks:[{bull,bear}] } */
async function loadETFList() {
  return cached('etfList', FIVE_MIN, async () => {
    const { data, error } = await window.sb
      .from('etfs')
      .select('*')
      .order('symbol');
    if (error) { console.error('loadETFList', error); return { pairs:[], single:[], stocks:[] }; }

    // Map DB columns → camelCase the existing render code expects
    const mapEtf = e => ({
      symbol:     e.symbol,
      name:       e.name,
      sponsor:    e.sponsor,
      leverage:   e.leverage,
      underlying: e.underlying,
      basePrice:  e.base_price,
      dayChange:  e.day_change,
      yearChange: e.year_change,
    });

    const single = [];
    const pairBuckets  = {};
    const stockBuckets = {};
    for (const row of data) {
      if (row.category === 'single') {
        single.push(mapEtf(row));
        continue;
      }
      const bucket = row.category === 'pair' ? pairBuckets : stockBuckets;
      const key = row.pair_underlying || row.symbol;
      bucket[key] = bucket[key] || { underlying: row.pair_underlying };
      if (row.side === 'bull' || row.side === 'bear') {
        bucket[key][row.side] = mapEtf(row);
      }
    }
    const pairs  = Object.values(pairBuckets ).filter(p => p.bull && p.bear).map(p => ({ bull:p.bull, bear:p.bear }));
    const stocks = Object.values(stockBuckets).filter(p => p.bull && p.bear).map(p => ({ bull:p.bull, bear:p.bear }));
    return { pairs, single, stocks };
  });
}

/** Returns { name, sponsor, leverage, underlying } or null. */
async function loadETFMeta(symbol) {
  if (!symbol) return null;
  return cached('etfMeta:' + symbol, FIVE_MIN, async () => {
    const { data, error } = await window.sb
      .from('etfs')
      .select('symbol, name, sponsor, leverage, underlying')
      .eq('symbol', symbol)
      .maybeSingle();
    if (error) { console.error('loadETFMeta', symbol, error); return null; }
    return data;
  });
}

/* =========================================================
   ETF prices — proxied through /api/prices (Yahoo Finance).
   Edge-cached for 24h. Returns:
     loadETFPrices(sym)            → { daily: [[d, close]], intraday: [[ts, close]] }
     loadAllETFRecentReturns(syms) → { SYM: { basePrice, dayChange, yearChange } }
   ========================================================= */

async function loadETFPrices(symbol) {
  if (!symbol) return { daily: [], intraday: [] };
  return cached('etfPrices:' + symbol, FIVE_MIN, async () => {
    const r = await fetch(`/api/prices?symbol=${encodeURIComponent(symbol)}&kind=detail`);
    if (!r.ok) { console.error('loadETFPrices', symbol, r.status); return { daily: [], intraday: [] }; }
    return await r.json();
  });
}

/** Returns { SYM: { basePrice, dayChange, yearChange }, ... } via /api/prices. */
async function loadAllETFRecentReturns(symbols) {
  if (!symbols || !symbols.length) return {};
  const sorted = [...new Set(symbols)].sort().join(',');
  return cached('etfRecentReturns:' + sorted, FIVE_MIN, async () => {
    const r = await fetch(`/api/prices?symbols=${encodeURIComponent(sorted)}`);
    if (!r.ok) { console.error('loadAllETFRecentReturns', r.status); return {}; }
    return await r.json();
  });
}

/* =========================================================
   ETF holdings — auth-gated by RLS server side.
   Returns { asOf: 'M/D/YYYY' or null, rows: [{...}] }
   ========================================================= */

async function loadETFHoldings(symbol) {
  if (!symbol) return null;
  return cached('etfHoldings:' + symbol, FIVE_MIN, async () => {
    const { data, error } = await window.sb
      .from('etf_holdings')
      .select('rank, ticker, name, shares, value, weight, position_type, as_of')
      .eq('etf_symbol', symbol)
      .order('rank');
    if (error) { console.error('loadETFHoldings', symbol, error); return null; }
    if (!data || !data.length) return null;
    const asOfIso = data[0].as_of;
    let asOf = null;
    if (asOfIso) {
      const [y, m, d] = asOfIso.split('-').map(Number);
      asOf = `${m}/${d}/${y}`;
    }
    return {
      asOf,
      rows: data.map(r => ({
        ticker: r.ticker || '—',
        name:   r.name,
        shares: Number(r.shares),
        value:  Number(r.value),
        weight: Number(r.weight),
        type:   r.position_type,
      })),
    };
  });
}

/* =========================================================
   Funds (institutional)
   ========================================================= */

async function loadFundCategory(catId) {
  return cached('fundCat:' + catId, FIVE_MIN, async () => {
    const { data, error } = await window.sb
      .from('fund_categories')
      .select('*')
      .eq('id', catId)
      .maybeSingle();
    if (error) { console.error('loadFundCategory', error); return null; }
    return data;
  });
}

async function loadFundsForCategory(catId) {
  return cached('fundsForCat:' + catId, FIVE_MIN, async () => {
    const cat = await loadFundCategory(catId);
    if (!cat) return [];
    const ids = cat.fund_ids || [];
    if (!ids.length) return [];
    const { data, error } = await window.sb
      .from('funds')
      .select('id, name, est_return, returns')   // skip the heavy series for the list view
      .in('id', ids);
    if (error) { console.error('loadFundsForCategory', error); return []; }
    // Keep order from category
    const byId = Object.fromEntries(data.map(f => [f.id, f]));
    return ids.map(id => byId[id]).filter(Boolean).map(f => ({
      id:        f.id,
      name:      f.name,
      estReturn: f.est_return,
      returns:   f.returns || {},
    }));
  });
}

/** Fund detail with full series + returns. Holdings are fetched separately. */
async function loadFundDetail(fundId) {
  if (!fundId) return null;
  return cached('fund:' + fundId, FIVE_MIN, async () => {
    const { data, error } = await window.sb
      .from('funds')
      .select('id, name, est_return, returns, series')
      .eq('id', fundId)
      .maybeSingle();
    if (error) { console.error('loadFundDetail', fundId, error); return null; }
    if (!data) return null;
    return {
      id:        data.id,
      name:      data.name,
      estReturn: data.est_return,
      returns:   data.returns || {},
      series:    data.series  || [],
    };
  });
}

async function loadFundHoldings(fundId) {
  if (!fundId) return [];
  return cached('fundHoldings:' + fundId, FIVE_MIN, async () => {
    const { data, error } = await window.sb
      .from('fund_holdings')
      .select('rank, ticker, shares, usd, weight')
      .eq('fund_id', fundId)
      .order('rank');
    if (error) { console.error('loadFundHoldings', fundId, error); return []; }
    return data.map(r => ({
      ticker: r.ticker,
      shares: r.shares,
      usd:    r.usd,
      weight: Number(r.weight),
    }));
  });
}

/* =========================================================
   Stock info — bulk lookup keyed by ticker
   ========================================================= */

async function loadStockInfo(tickers) {
  if (!tickers || !tickers.length) return {};
  const list = Array.from(new Set(tickers.filter(Boolean)));
  const cacheKey = 'stockInfo:' + list.sort().join(',');
  return cached(cacheKey, FIVE_MIN, async () => {
    const { data, error } = await window.sb
      .from('stock_info')
      .select('ticker, name, domain')
      .in('ticker', list);
    if (error) { console.error('loadStockInfo', error); return {}; }
    const out = {};
    for (const r of data) out[r.ticker] = { name: r.name, domain: r.domain };
    return out;
  });
}

window.GBSData = {
  loadETFList, loadETFMeta, loadETFPrices, loadAllETFRecentReturns,
  loadETFHoldings,
  loadFundCategory, loadFundsForCategory, loadFundDetail, loadFundHoldings,
  loadStockInfo,
};
