// Supabase project keys — anon/publishable key is safe to ship in the browser.
// Row-Level Security policies in sql/02_rls.sql are the actual access boundary.
const SUPABASE_URL = 'https://vkwojgwvpigtytuclhlm.supabase.co';
const SUPABASE_KEY = 'sb_publishable_-aNQZV8MZRnhHG3eNJ4CFw_OWTWTm2A';

// `window.supabase` is the SDK loaded from CDN; the client we use is on `window.sb`.
window.sb = window.supabase.createClient(SUPABASE_URL, SUPABASE_KEY, {
  auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
});
