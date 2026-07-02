/* ============================================================
   YouTube_Bot dashboard — Supabase backed (multi-user)
   - session via Supabase Auth (Google sign-in)
   - on login: save the user's refresh token + channel to the DB
   - niche picker -> settings table
   - "generate" -> insert a row into the jobs queue
   - the GitHub Actions worker (M4) builds + uploads per user
   ============================================================ */
(async function () {
  // ---- require login ----
  const { data: { session } } = await sb.auth.getSession();
  if (!session) { location.replace("index.html"); return; }
  const user = session.user;
  document.getElementById("who").textContent = user.email;

  /* ---------- helpers ---------- */
  const toast = document.getElementById("toast");
  let toastTimer;
  function showToast(msg) {
    toast.textContent = msg;
    toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("show"), 3200);
  }
  function escapeHtml(s) {
    return String(s || "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  /* ---------- logout ---------- */
  document.getElementById("logout").addEventListener("click", async () => {
    await sb.auth.signOut();
    location.replace("index.html");
  });

  /* ---------- sidebar nav ---------- */
  const TITLES = { dashboard: "Dashboard", create: "Create Video", channel: "My Channel", requests: "Requests", guide: "Guide", users: "Users" };
  const navLinks = document.querySelectorAll("#nav a");
  function switchView(name) {
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    document.getElementById("view-" + name).classList.add("active");
    navLinks.forEach((a) => a.classList.toggle("active", a.dataset.view === name));
    document.getElementById("pageTitle").textContent = TITLES[name] || "Dashboard";
  }
  navLinks.forEach((a) => a.addEventListener("click", () => switchView(a.dataset.view)));

  /* ---------- YouTube connect / token capture ---------- */
  const SCOPES = "https://www.googleapis.com/auth/youtube.upload " +
                 "https://www.googleapis.com/auth/youtube.readonly";

  // Store the refresh token + channel whenever a fresh Google session appears.
  async function captureFromSession(sess) {
    if (!sess) return;
    if (sess.provider_refresh_token) {
      const { error } = await sb.from("channel_tokens").upsert(
        { user_id: sess.user.id, refresh_token: sess.provider_refresh_token,
          updated_at: new Date().toISOString() });
      showToast(error ? ("⚠️ Token save failed: " + error.message)
                      : "✅ Auto-upload enabled — the bot can now post to your channel.");
    } else if (sess.provider_token) {
      // We have an access token but Google gave no refresh token this time.
      console.warn("No provider_refresh_token in session — click 'Enable auto-upload' to grant offline access.");
    }
    await refreshAutoStatus();
    if (sess.provider_token) {
      try {
        const r = await fetch(
          "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
          { headers: { Authorization: "Bearer " + sess.provider_token } });
        const d = await r.json();
        const item = (d.items || [])[0];
        if (item) {
          await sb.from("channels").upsert(
            { user_id: sess.user.id, channel_id: item.id, title: item.snippet.title });
          if (sess.provider_refresh_token) {
            await sb.from("channels").update({ upload_ready: true }).eq("user_id", sess.user.id);
          }
          renderChannel();
        }
      } catch (e) { /* channel may already be stored from before */ }
    }
  }

  // Persistent on-page status: is auto-upload (token) actually stored?
  async function refreshAutoStatus() {
    const hint = document.getElementById("chanHint");
    const btn = document.getElementById("reconnectBtn");
    const { data } = await sb.from("channel_tokens").select("user_id").eq("user_id", user.id).maybeSingle();
    if (data) {
      hint.innerHTML = "✅ <b style='color:#7ee2a0'>Auto-upload ENABLED</b> — the bot can post to your channel.";
      btn.textContent = "Re-grant access";
    } else {
      hint.innerHTML = "⚠️ <b style='color:#ff8f8f'>Auto-upload NOT enabled.</b> Click the button above, pick your account, and press <b>Allow</b>.";
      btn.textContent = "🔑 Enable auto-upload (grant access)";
    }
  }

  // Fresh Google consent (offline) -> guarantees a refresh token comes back.
  async function connectYouTube() {
    const redirectTo = new URL("dashboard.html", window.location.href).href;
    const { error } = await sb.auth.signInWithOAuth({
      provider: "google",
      options: { scopes: SCOPES, queryParams: { access_type: "offline", prompt: "consent" }, redirectTo },
    });
    if (error) showToast(error.message);
  }
  document.getElementById("reconnectBtn").addEventListener("click", connectYouTube);

  // Connect a DIFFERENT Google account as another channel/user.
  document.getElementById("addChannelBtn").addEventListener("click", async () => {
    const redirectTo = new URL("dashboard.html", window.location.href).href;
    await sb.auth.signInWithOAuth({
      provider: "google",
      options: { scopes: SCOPES, queryParams: { access_type: "offline", prompt: "consent select_account" }, redirectTo },
    });
  });

  // ---------- admin: list all connected users ----------
  let adminTotals = null;
  async function renderUsers() {
    const [chansR, setsR, jobsR] = await Promise.all([
      sb.from("channels").select("user_id,title,created_at,upload_ready"),
      sb.from("settings").select("user_id,category,subcategory,auto_daily,language"),
      sb.from("jobs").select("user_id,status"),
    ]);
    const chans = chansR.data || [];
    const sets = {}; (setsR.data || []).forEach((s) => { sets[s.user_id] = s; });
    const jc = {}; (jobsR.data || []).forEach((j) => {
      jc[j.user_id] = jc[j.user_id] || { t: 0, d: 0 };
      jc[j.user_id].t++; if (j.status === "done") jc[j.user_id].d++;
    });
    let done = 0, total = 0; Object.values(jc).forEach((v) => { done += v.d; total += v.t; });
    adminTotals = { users: chans.length, done, total };
    document.getElementById("usersCount").textContent = chans.length;
    const host = document.getElementById("usersList");
    if (!chans.length) { host.textContent = "No connected users yet."; return; }
    const cats = Object.keys(NICHE_TREE);
    const rows = chans.map((c) => {
      const s = sets[c.user_id] || {}, j = jc[c.user_id] || { t: 0, d: 0 };
      const field = (s.category || s.subcategory)
        ? `${s.category || ""} › ${s.subcategory || "—"}` : "❌ Not set";
      const catOpts = cats.map((cat) => `<option${cat === s.category ? " selected" : ""}>${cat}</option>`).join("");
      const subs = Object.keys(NICHE_TREE[s.category] || NICHE_TREE[cats[0]] || {});
      const subOpts = subs.map((sub) => `<option${sub === s.subcategory ? " selected" : ""}>${sub}</option>`).join("");
      return `<tr data-uid="${c.user_id}" data-lang="${escapeHtml(s.language || "en")}" data-fmt="${escapeHtml(s.format || "short")}">
        <td><b>${escapeHtml(c.title || "—")}</b></td>
        <td>${escapeHtml(field)}</td>
        <td>${escapeHtml(s.language || "en")}</td>
        <td>${c.upload_ready ? "✅ Yes" : "❌ No"}</td>
        <td><select class="admAuto">
          <option value="on"${s.auto_daily !== false ? " selected" : ""}>on</option>
          <option value="off"${s.auto_daily === false ? " selected" : ""}>off</option>
        </select></td>
        <td>${j.d}/${j.t}</td>
        <td>${c.created_at ? new Date(c.created_at).toLocaleDateString() : "—"}</td>
        <td class="editcell">
          <div class="actions">
            <select class="admCat">${catOpts}</select>
            <select class="admSub">${subOpts}</select>
          </div>
          <div class="actions" style="margin-top:8px">
            <button class="btn auto admSave">💾 Save field</button>
          </div>
        </td>
      </tr>`;
    }).join("");
    host.innerHTML = `<div style="overflow-x:auto"><table class="utable">
      <thead><tr>
        <th>Channel</th><th>Current field</th><th>Lang</th><th>Enabled</th><th>Auto</th>
        <th>Videos</th><th>Joined</th><th>Change field</th>
      </tr></thead><tbody>${rows}</tbody></table></div>`;

    // wire per-row admin edit
    host.querySelectorAll("tbody tr").forEach((tr) => {
      const uid = tr.dataset.uid;
      const catS = tr.querySelector(".admCat"), subS = tr.querySelector(".admSub");
      catS.addEventListener("change", () => {
        subS.innerHTML = Object.keys(NICHE_TREE[catS.value] || {}).map((sub) => `<option>${sub}</option>`).join("");
      });
      tr.querySelector(".admSave").addEventListener("click", async () => {
        const { error } = await sb.from("settings").upsert({
          user_id: uid, category: catS.value, subcategory: subS.value, updated_at: new Date().toISOString(),
        });
        if (error) showToast("Save failed: " + error.message);
        else { showToast("✅ Updated field for this user."); renderUsers(); }
      });
      tr.querySelector(".admAuto").addEventListener("change", async (e) => {
        const { error } = await sb.from("settings").upsert({
          user_id: uid, auto_daily: e.target.value === "on", updated_at: new Date().toISOString(),
        });
        showToast(error ? ("Failed: " + error.message) : "✅ Auto-daily " + e.target.value + " for this user.");
      });
    });
  }

  // Catch the token on the post-login redirect too (belt and braces).
  sb.auth.onAuthStateChange((_event, sess) => { if (sess) captureFromSession(sess); });

  async function renderChannel() {
    const { data } = await sb.from("channels").select("title,channel_id").eq("user_id", user.id).maybeSingle();
    const badge = document.getElementById("chanBadge");
    const status = document.getElementById("chanStatus");
    const nameEl = document.getElementById("chanName");
    const stChan = document.getElementById("stChan");
    if (data && data.title) {
      badge.className = "badge on"; badge.textContent = "📺 " + data.title;
      status.className = "badge on"; status.textContent = "Connected";
      nameEl.textContent = data.title; stChan.textContent = data.title;
    } else {
      badge.className = "badge off"; badge.textContent = "📺 Not connected";
      status.className = "badge off"; status.textContent = "Not connected";
      nameEl.textContent = ""; stChan.textContent = "—";
    }
  }

  /* ============================================================
     NICHE TREE — Category -> Subcategory (set once, AI reuses it)
     ============================================================ */
  const NICHE_TREE = {
    "📚 Education": { "Study & Learning": 1, "Words & Language": 1, "Math & Logic": 1, "Life Skills": 1, "Exam & Career": 1, "General Knowledge": 1 },
    "🔬 Science & Space": { "Space & Universe": 1, "Physics": 1, "Chemistry": 1, "Earth & Weather": 1, "Biology & Life": 1, "Tech Science": 1 },
    "🧠 Psychology & Mind": { "How the Brain Works": 1, "Emotions & Behaviour": 1, "Sleep & Dreams": 1, "Bias & Persuasion": 1, "Relationships": 1, "Self-Improvement": 1 },
    "🏛️ History": { "Ancient World": 1, "Mysteries": 1, "Inventions": 1, "Empires & Kingdoms": 1, "Turning Points": 1, "Everyday History": 1 },
    "🌿 Nature & Animals": { "Ocean Life": 1, "Wild Animals": 1, "Birds & Insects": 1, "Plants & Forests": 1, "Pets & Domestic": 1, "Extreme Survival": 1 },
    "🌍 Geography & Places": { "Natural Wonders": 1, "Hidden Places": 1, "Cities & Culture": 1, "Countries & Flags": 1, "Maps & Borders": 1, "Earth Facts": 1 },
    "💰 Money & Business": { "Money Basics": 1, "Brands & Companies": 1, "Economy Simplified": 1, "Entrepreneurship": 1, "Investing Basics": 1, "Success Stories": 1 },
    "💻 Tech & Internet": { "How Things Work": 1, "AI & Future": 1, "Digital Safety": 1, "Gadgets": 1, "Internet Culture": 1, "Coding & Computers": 1 },
    "🍿 Entertainment": { "Movies & Cinema": 1, "Music": 1, "Celebrities & Fame": 1, "Gaming": 1, "Anime & Comics": 1, "Trends & Memes": 1 },
    "⚽ Sports & Fitness": { "Football & Cricket": 1, "Sports Science": 1, "Fitness & Gym": 1, "Legends & Records": 1, "Olympics & Global": 1, "Mind of Athletes": 1 },
    "🍔 Food & Cooking": { "Food Science": 1, "World Cuisines": 1, "Healthy Eating": 1, "Cooking Tricks": 1, "Drinks": 1, "Food History": 1 },
    "✈️ Travel & Adventure": { "Wonders of the World": 1, "Extreme Places": 1, "Cultures & People": 1, "Travel Tips": 1, "Lost & Abandoned": 1, "Adventure & Survival": 1 },
    "🎨 Art & Creativity": { "Famous Art": 1, "Design & Colors": 1, "Architecture": 1, "Photography & Film": 1, "DIY & Crafts": 1, "Creativity Science": 1 },
    "🧘 Health & Lifestyle": { "Human Body": 1, "Sleep & Rest": 1, "Mental Wellness": 1, "Habits & Routines": 1, "Nutrition": 1, "Longevity": 1 },
    "🚗 Automobiles & Machines": { "Cars & Engines": 1, "Bikes & Speed": 1, "Aircraft & Flight": 1, "Trains & Ships": 1, "Machines & Engineering": 1, "Future Transport": 1 },
    "🔮 Mysteries & Unexplained": { "Unsolved Mysteries": 1, "Space Mysteries": 1, "Ancient Enigmas": 1, "Illusions & Brain Tricks": 1, "Strange Phenomena": 1, "Myths & Legends": 1 },
  };

  const catSel = document.getElementById("category");
  const subSel = document.getElementById("subcategory");
  const langSel = document.getElementById("language");
  const fmtSel = document.getElementById("format");

  function fillCategories() { catSel.innerHTML = Object.keys(NICHE_TREE).map((c) => `<option>${c}</option>`).join(""); }
  function fillSubcategories() { subSel.innerHTML = Object.keys(NICHE_TREE[catSel.value] || {}).map((s) => `<option>${s}</option>`).join(""); }
  let fieldSaved = false;
  function fieldLabel() { return `${catSel.value} › ${subSel.value}`; }
  function updateFieldDisplays() {
    document.getElementById("nicheNote").innerHTML =
      `🎯 The AI will always create <b>${escapeHtml(fieldLabel())}</b> videos for your channel.`;
    const df = document.getElementById("dashField");
    if (df) df.innerHTML = fieldSaved
      ? `<span class="badge on">✅ Active</span> &nbsp;<b>${escapeHtml(fieldLabel())}</b>` +
        `<br /><small style="color:var(--muted)">The bot posts videos in this field automatically.</small>`
      : `<span class="badge off">Not set</span> &nbsp;<small style="color:var(--muted)">Go to Create Video and pick your field.</small>`;
  }
  async function saveNiche() {
    await sb.from("settings").upsert({
      user_id: user.id, category: catSel.value, subcategory: subSel.value,
      language: langSel.value, format: fmtSel.value, updated_at: new Date().toISOString(),
    });
    fieldSaved = true;
    updateFieldDisplays();
  }

  catSel.addEventListener("change", () => { fillSubcategories(); saveNiche(); });
  subSel.addEventListener("change", () => saveNiche());
  langSel.addEventListener("change", () => saveNiche());
  fmtSel.addEventListener("change", () => saveNiche());

  document.getElementById("saveFieldBtn").addEventListener("click", async () => {
    if (!catSel.value) { showToast("Pick a category first."); return; }
    await saveNiche();
    showToast("✅ Field saved: " + fieldLabel() + " — the bot will post these automatically.");
  });
  document.getElementById("editFieldBtn").addEventListener("click", () => switchView("create"));

  async function loadNiche() {
    fillCategories();
    const { data } = await sb.from("settings").select("*").eq("user_id", user.id).maybeSingle();
    if (data && NICHE_TREE[data.category]) catSel.value = data.category;
    fillSubcategories();
    if (data && (NICHE_TREE[catSel.value] || {})[data.subcategory]) subSel.value = data.subcategory;
    if (data && data.language) langSel.value = data.language;
    if (data && data.format) fmtSel.value = data.format;
    fieldSaved = !!(data && data.category);
    updateFieldDisplays();
  }

  /* ---------- jobs ---------- */
  async function renderRequests() {
    const { data } = await sb.from("jobs").select("*").eq("user_id", user.id).order("created_at", { ascending: false });
    document.getElementById("stReq").textContent = (data || []).length;
    const list = document.getElementById("requestList");
    if (!data || !data.length) { list.textContent = "No requests yet."; return; }
    list.innerHTML = data.map((r) => `
      <div style="padding:10px 0;border-bottom:1px solid var(--border)">
        <b style="color:var(--text)">${escapeHtml(r.title || (r.category + " › " + r.subcategory))}</b>
        &nbsp;<span class="badge ${r.status === "done" ? "on" : "off"}">${escapeHtml(r.status)}</span>
        ${r.video_url ? ` &nbsp;<a href="${escapeHtml(r.video_url)}" target="_blank">watch</a>` : ""}<br />
        <small>${escapeHtml(r.category)} › ${escapeHtml(r.subcategory)} • ${escapeHtml(r.format)} • ${escapeHtml(r.language)} • ${new Date(r.created_at).toLocaleString()}</small>
      </div>`).join("");
  }

  document.getElementById("generateBtn").addEventListener("click", async () => {
    if (!catSel.value) { showToast("Pick a category first."); return; }
    const btn = document.getElementById("generateBtn");
    btn.disabled = true;
    await saveNiche();
    const { error } = await sb.from("jobs").insert({
      user_id: user.id, category: catSel.value, subcategory: subSel.value,
      language: langSel.value, format: fmtSel.value, status: "queued",
    });
    btn.disabled = false;
    if (error) { showToast("Could not queue: " + error.message); return; }
    await renderRequests();
    switchView("requests");
    showToast("✅ Queued! The bot will build & upload this to your channel.");
  });

  /* ---------- admin detection ---------- */
  const { data: adminRow } = await sb.from("admins").select("user_id").eq("user_id", user.id).maybeSingle();
  const isAdmin = !!adminRow;

  /* ---------- init ---------- */
  await captureFromSession(session);
  await refreshAutoStatus();
  await renderChannel();
  await loadNiche();
  await renderRequests();

  if (isAdmin) {
    document.getElementById("navUsers").style.display = "flex";
    await renderUsers();
    // admin gets FULL access — keep all tabs; just add all-users totals up top.
    if (adminTotals) {
      document.getElementById("stReq").textContent = adminTotals.done;
      document.getElementById("stReqL").textContent = "Videos made (all users)";
      document.getElementById("stChan").textContent = adminTotals.users;
      document.getElementById("stChanL").textContent = "Connected users";
    }
    document.getElementById("dashField").innerHTML =
      "🛡️ <b>Admin</b> — you can manage every user (edit field, auto on/off, generate) in the <b>Users</b> tab.";
  }
})();
