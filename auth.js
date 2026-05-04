/* ----------------------------------------------------------------------
   Shared auth utilities — depends on config.js (window.sb).
   Loaded on every page so the nav reflects the session and
   protected pages can call requireAuth().
   ---------------------------------------------------------------------- */

async function getSession() {
  const { data } = await window.sb.auth.getSession();
  return data.session || null;
}

async function getUser() {
  const session = await getSession();
  return session ? session.user : null;
}

/** Redirects to login.html?next=<current> if not signed in. */
async function requireAuth() {
  const session = await getSession();
  if (!session) {
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.replace('login.html?next=' + next);
    return null;
  }
  return session;
}

async function signOut() {
  await window.sb.auth.signOut();
  window.location.reload();
}

/* ----------------------------------------------------------------------
   Render / refresh the nav-auth widget injected into <nav ul>.
   The widget shows "Sign in" when logged out, the user email + Sign out
   when logged in.
   ---------------------------------------------------------------------- */

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
}

function renderNavAuth(user) {
  const slot = document.getElementById('nav-auth');
  if (!slot) return;
  if (user) {
    const email = user.email || 'account';
    slot.innerHTML = `
      <span class="nav-user" title="${escapeHtml(email)}">${escapeHtml(email)}</span>
      <a href="#" class="nav-signout" id="nav-signout">Sign out</a>`;
    const btn = document.getElementById('nav-signout');
    if (btn) btn.addEventListener('click', e => { e.preventDefault(); signOut(); });
  } else {
    slot.innerHTML = `<a href="login.html" class="nav-signin">Sign in</a>`;
  }
}

async function refreshNavAuth() {
  renderNavAuth(await getUser());
}

// Initial render + react to auth state changes (login, logout, token refresh)
document.addEventListener('DOMContentLoaded', () => {
  refreshNavAuth();
  window.sb.auth.onAuthStateChange(() => refreshNavAuth());
});

// Expose for pages
window.GBSAuth = { getSession, getUser, requireAuth, signOut, refreshNavAuth };
