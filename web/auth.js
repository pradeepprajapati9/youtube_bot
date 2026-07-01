/* ============================================================
   Auth (client-side MVP for GitHub Pages — no backend yet)

   NOTE: This is a UX gate, not real security. Accounts + session
   live in the browser's localStorage. It stops the dashboard from
   opening without a login, and lets us build the full flow now.
   In a later step this gets replaced by real "Sign in with Google"
   (which also gives us the YouTube upload permission we need).
   ============================================================ */
const Auth = (() => {
  const ACCOUNTS_KEY = "at_accounts";   // { email: passHash }
  const SESSION_KEY = "at_session";     // current logged-in email

  // Tiny non-cryptographic hash — just so we don't store the raw password.
  function hash(str) {
    let h = 5381;
    for (let i = 0; i < str.length; i++) h = (h * 33) ^ str.charCodeAt(i);
    return (h >>> 0).toString(16);
  }

  function loadAccounts() {
    try { return JSON.parse(localStorage.getItem(ACCOUNTS_KEY)) || {}; }
    catch { return {}; }
  }
  function saveAccounts(a) { localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(a)); }

  function validEmail(e) { return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e); }

  return {
    signup(email, pass) {
      if (!validEmail(email)) return { ok: false, error: "Enter a valid email." };
      if (!pass || pass.length < 4) return { ok: false, error: "Password must be 4+ characters." };
      const accts = loadAccounts();
      if (accts[email]) return { ok: false, error: "Account exists — just sign in." };
      accts[email] = hash(pass);
      saveAccounts(accts);
      localStorage.setItem(SESSION_KEY, email);
      return { ok: true };
    },

    login(email, pass) {
      if (!validEmail(email)) return { ok: false, error: "Enter a valid email." };
      const accts = loadAccounts();
      if (!accts[email]) return { ok: false, error: "No account found. Create one first." };
      if (accts[email] !== hash(pass)) return { ok: false, error: "Wrong password." };
      localStorage.setItem(SESSION_KEY, email);
      return { ok: true };
    },

    currentUser() { return localStorage.getItem(SESSION_KEY); },

    logout() { localStorage.removeItem(SESSION_KEY); },

    // Call at the top of any protected page — redirects to login if not signed in.
    requireLogin() {
      if (!localStorage.getItem(SESSION_KEY)) {
        location.replace("index.html");
        return false;
      }
      return true;
    },
  };
})();
