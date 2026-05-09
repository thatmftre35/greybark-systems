// Vercel Edge function — proxy to Yahoo Finance chart API.
//
// Two modes:
//   GET /api/prices?symbols=SPXL,SPXS,...
//     → { SPXL: { basePrice, dayChange, yearChange }, ... }
//
//   GET /api/prices?symbol=SPXL&kind=detail
//     → { daily: [[YYYY-MM-DD, close], ...],
//         intraday: [[YYYY-MM-DD HH:MM, close], ...] }
//
// Cached at the edge for 24h (stale-while-revalidate). Daily refresh.
//
// Yahoo's "Adj Close" is unreliable for ETFs with many reverse splits
// (e.g. SOXS reports ~$39M closes in 2016) so we apply split adjustment
// manually using the splits series Yahoo returns alongside the prices.

export const config = { runtime: 'edge' };

const YF = 'https://query1.finance.yahoo.com/v8/finance/chart';
const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

async function chart(symbol, range, interval) {
  const url = `${YF}/${encodeURIComponent(symbol)}?range=${range}&interval=${interval}&events=split,div`;
  const r = await fetch(url, {
    headers: { 'User-Agent': UA, 'Accept': 'application/json' },
  });
  if (!r.ok) return null;
  const j = await r.json();
  return j?.chart?.result?.[0] || null;
}

// Each pre-split close is multiplied by the cumulative product of splits
// AFTER its date, so the whole series sits on today's share-count scale.
function splitAdjust(timestamps, closes, splits) {
  const list = Object.values(splits || {})
    .map(s => ({ date: s.date, factor: s.numerator / s.denominator }))
    .sort((a, b) => a.date - b.date);
  const out = [];
  for (let i = 0; i < timestamps.length; i++) {
    const t = timestamps[i];
    const c = closes[i];
    if (c == null || c <= 0) continue;
    let f = 1;
    for (const s of list) if (s.date > t) f *= s.factor;
    out.push([t, c * f]);
  }
  return out;
}

const fmtDate = unix => new Date(unix * 1000).toISOString().slice(0, 10);

function fmtIntraday(unix, tz) {
  const d = new Date(unix * 1000);
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-CA', {
      timeZone: tz || 'America/New_York',
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hour12: false,
    }).formatToParts(d).map(p => [p.type, p.value])
  );
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}`;
}

const round = (n, p = 2) => Math.round(n * 10 ** p) / 10 ** p;

async function summarize(symbol) {
  const r = await chart(symbol, '1y', '1d');
  if (!r) return null;
  const adj = splitAdjust(
    r.timestamp || [],
    r.indicators?.quote?.[0]?.close || [],
    r.events?.splits,
  );
  if (adj.length < 2) return null;
  const last = adj[adj.length - 1][1];
  const prev = adj[adj.length - 2][1];
  const yearAgo = adj[0][1];
  return {
    basePrice:  round(last, 2),
    dayChange:  prev > 0 ? round((last - prev) / prev * 100, 2) : null,
    yearChange: yearAgo > 0 ? round((last - yearAgo) / yearAgo * 100, 2) : null,
  };
}

async function detail(symbol) {
  const [d, m] = await Promise.all([
    chart(symbol, '5y', '1d'),
    chart(symbol, '7d', '1m'),
  ]);
  let daily = [], intraday = [];
  if (d) {
    daily = splitAdjust(
      d.timestamp || [],
      d.indicators?.quote?.[0]?.close || [],
      d.events?.splits,
    ).map(([t, c]) => [fmtDate(t), c < 1 ? round(c, 4) : round(c, 2)]);
  }
  if (m) {
    const tz = m.meta?.exchangeTimezoneName;
    const ts = m.timestamp || [];
    const closes = m.indicators?.quote?.[0]?.close || [];
    intraday = ts
      .map((t, i) => (closes[i] > 0 ? [fmtIntraday(t, tz), round(closes[i], 2)] : null))
      .filter(Boolean);
  }
  return { daily, intraday };
}

export default async function handler(req) {
  const url = new URL(req.url);
  const symbol  = url.searchParams.get('symbol');
  const symbols = url.searchParams.get('symbols');
  const kind    = url.searchParams.get('kind');

  const headers = {
    'Content-Type': 'application/json',
    'Cache-Control': 'public, s-maxage=86400, stale-while-revalidate=86400',
  };

  try {
    if (kind === 'detail' && symbol) {
      const data = await detail(symbol.toUpperCase());
      return new Response(JSON.stringify(data), { status: 200, headers });
    }
    if (symbols) {
      const list = symbols.toUpperCase().split(',').filter(Boolean);
      const results = await Promise.all(
        list.map(async s => [s, await summarize(s).catch(() => null)])
      );
      const out = {};
      for (const [s, v] of results) if (v) out[s] = v;
      return new Response(JSON.stringify(out), { status: 200, headers });
    }
    return new Response(
      JSON.stringify({ error: 'pass ?symbols=A,B,C or ?symbol=X&kind=detail' }),
      { status: 400, headers },
    );
  } catch (e) {
    return new Response(
      JSON.stringify({ error: String(e?.message || e) }),
      { status: 500, headers },
    );
  }
}
