/* ============================================================
   Vault — stores the user's keys/credentials, obfuscated at rest.

   Values are XOR-ciphered with a per-user key then base64-encoded, so
   they are NOT sitting in localStorage as readable plain text, and the
   UI shows them masked. User can update any value any time.

   HONEST NOTE: pure front-end "encryption" is obfuscation, not real
   security (the key is derivable in the browser). For production the
   real secrets belong in GitHub Secrets, which the Actions worker uses.
   This vault is for convenience + hiding values on screen/disk.
   ============================================================ */
const Vault = (() => {
  const keyFor = (u) => "at_vault_" + u;
  const cipherKey = (u) => "ytb::" + u + "::v1::s9f3q7";

  function xor(str, k) {
    let out = "";
    for (let i = 0; i < str.length; i++)
      out += String.fromCharCode(str.charCodeAt(i) ^ k.charCodeAt(i % k.length));
    return out;
  }
  function enc(u, plain) {
    if (!plain) return "";
    return btoa(unescape(encodeURIComponent(xor(plain, cipherKey(u)))));
  }
  function dec(u, b64) {
    if (!b64) return "";
    try { return xor(decodeURIComponent(escape(atob(b64))), cipherKey(u)); }
    catch { return ""; }
  }
  function loadRaw(u) {
    try { return JSON.parse(localStorage.getItem(keyFor(u))) || {}; }
    catch { return {}; }
  }

  return {
    get(u, field) { return dec(u, loadRaw(u)[field] || ""); },
    set(u, field, value) {
      const raw = loadRaw(u);
      if (value) raw[field] = enc(u, value); else delete raw[field];
      localStorage.setItem(keyFor(u), JSON.stringify(raw));
    },
    has(u, field) { return !!loadRaw(u)[field]; },
  };
})();
