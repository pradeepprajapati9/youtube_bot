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
  const TITLES = { dashboard: "Dashboard", create: "Create Video", channel: "My Channel", requests: "Requests" };
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
          renderChannel();
        }
      } catch (e) { /* channel may already be stored from before */ }
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
  function updateNicheNote() {
    document.getElementById("nicheNote").innerHTML =
      `🎯 The AI will always create <b>${escapeHtml(catSel.value)} › ${escapeHtml(subSel.value)}</b> videos for your channel. Set once — the bot does the rest.`;
  }
  async function saveNiche() {
    await sb.from("settings").upsert({
      user_id: user.id, category: catSel.value, subcategory: subSel.value,
      language: langSel.value, format: fmtSel.value, updated_at: new Date().toISOString(),
    });
  }

  catSel.addEventListener("change", () => { fillSubcategories(); updateNicheNote(); saveNiche(); });
  subSel.addEventListener("change", () => { updateNicheNote(); saveNiche(); });
  langSel.addEventListener("change", saveNiche);
  fmtSel.addEventListener("change", saveNiche);

  async function loadNiche() {
    fillCategories();
    const { data } = await sb.from("settings").select("*").eq("user_id", user.id).maybeSingle();
    if (data && NICHE_TREE[data.category]) catSel.value = data.category;
    fillSubcategories();
    if (data && (NICHE_TREE[catSel.value] || {})[data.subcategory]) subSel.value = data.subcategory;
    if (data && data.language) langSel.value = data.language;
    if (data && data.format) fmtSel.value = data.format;
    updateNicheNote();
  }

  /* ---------- jobs ---------- */
  async function renderRequests() {
    const { data } = await sb.from("jobs").select("*").eq("user_id", user.id).order("created_at", { ascending: false });
    document.getElementById("stReq").textContent = (data || []).length;
    const list = document.getElementById("requestList");
    if (!data || !data.length) { list.textContent = "No requests yet."; return; }
    list.innerHTML = data.map((r) => `
      <div style="padding:10px 0;border-bottom:1px solid var(--border)">
        <b style="color:var(--text)">${escapeHtml(r.category)} › ${escapeHtml(r.subcategory)}</b>
        &nbsp;<span class="badge ${r.status === "done" ? "on" : "off"}">${escapeHtml(r.status)}</span>
        ${r.video_url ? ` &nbsp;<a href="${escapeHtml(r.video_url)}" target="_blank">watch</a>` : ""}<br />
        <small>${escapeHtml(r.format)} • ${escapeHtml(r.language)} • ${new Date(r.created_at).toLocaleString()}</small>
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

  /* ---------- init ---------- */
  await captureFromSession(session);
  await renderChannel();
  await loadNiche();
  await renderRequests();
})();
