/* ============================================================
   YouTube_Bot dashboard logic
   - sidebar navigation (left menu -> right content)
   - Settings vault: paste keys (masked/encrypted), update anytime
   - Google OAuth connect (YouTube channel)
   - content field: pick Category -> Subcategory ONCE; the AI then
     always creates videos in that niche (no topic writing)
   - per-user request list (localStorage for now)
   ============================================================ */
(function () {
  const user = Auth.currentUser();
  document.getElementById("who").textContent = user;

  document.getElementById("logout").addEventListener("click", () => {
    Auth.logout();
    location.replace("index.html");
  });

  /* ---------- toast + helpers ---------- */
  const toast = document.getElementById("toast");
  let toastTimer;
  function showToast(msg) {
    toast.textContent = msg;
    toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("show"), 3000);
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  /* ---------- sidebar navigation ---------- */
  const TITLES = { dashboard: "Dashboard", create: "Create Video", channel: "My Channel", requests: "Requests", settings: "Settings" };
  const navLinks = document.querySelectorAll("#nav a");
  function switchView(name) {
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    document.getElementById("view-" + name).classList.add("active");
    navLinks.forEach((a) => a.classList.toggle("active", a.dataset.view === name));
    document.getElementById("pageTitle").textContent = TITLES[name] || "Dashboard";
  }
  navLinks.forEach((a) => a.addEventListener("click", () => switchView(a.dataset.view)));

  /* ============================================================
     SETTINGS — keys a user may paste (masked + encrypted vault)
     ============================================================ */
  const FIELDS = [
    {
      id: "google_client_id", label: "Google OAuth Client ID", required: true,
      placeholder: "1234567890-abcd....apps.googleusercontent.com",
      guide: 'Needed to connect your YouTube channel. Get it in ' +
        '<a href="https://console.cloud.google.com/apis/credentials" target="_blank">Google Cloud → Credentials</a> ' +
        '(OAuth client ID, type "Web application"). A Client ID is public — safe to save.',
    },
    {
      id: "gemini_api_key", label: "Gemini API Key", required: false,
      placeholder: "AIza....",
      guide: 'Smarter AI scripts. Free key from ' +
        '<a href="https://aistudio.google.com/apikey" target="_blank">Google AI Studio</a>. Without it the bot uses Wikipedia.',
    },
    {
      id: "pexels_api_key", label: "Pexels API Key", required: false,
      placeholder: "563492ad....",
      guide: 'Better stock video/footage. Free key from ' +
        '<a href="https://www.pexels.com/api/" target="_blank">Pexels API</a>. Optional.',
    },
    {
      id: "yt_api_key", label: "YouTube Data API Key", required: false,
      placeholder: "AIza....",
      guide: 'Powers the growth/analytics feedback loop (reads your videos\' public stats). Optional.',
    },
    {
      id: "github_token", label: "GitHub Token (auto-run)", required: false,
      placeholder: "github_pat_....",
      guide: 'Lets the "Generate" button start the video-build Action for you. Create a ' +
        '<a href="https://github.com/settings/tokens?type=beta" target="_blank">fine-grained token</a> ' +
        'scoped to your repo with <b>Actions: Read and write</b> permission. Without it, requests are just saved.',
    },
  ];

  function renderSettings() {
    const host = document.getElementById("settingsFields");
    host.innerHTML = FIELDS.map((f) => {
      const val = Vault.get(user, f.id);
      const tag = f.required ? '<span class="req">required</span>' : '<span class="opt">optional</span>';
      const saved = val ? '<span class="saved">✓ saved</span>' : '';
      return `
        <div class="field">
          <div class="flabel"><b>${f.label} ${saved}</b>${tag}</div>
          <div class="guide">${f.guide}</div>
          <div class="inwrap">
            <input type="password" id="fld_${f.id}" placeholder="${f.placeholder}" value="${escapeHtml(val)}" />
            <button type="button" class="eye" data-for="fld_${f.id}">show</button>
          </div>
        </div>`;
    }).join("");
    host.querySelectorAll(".eye").forEach((btn) => {
      btn.addEventListener("click", () => {
        const inp = document.getElementById(btn.dataset.for);
        const show = inp.type === "password";
        inp.type = show ? "text" : "password";
        btn.textContent = show ? "hide" : "show";
      });
    });
  }

  document.getElementById("saveSettings").addEventListener("click", () => {
    FIELDS.forEach((f) => Vault.set(user, f.id, document.getElementById("fld_" + f.id).value.trim()));
    renderSettings();
    tokenClient = null;      // rebuild Google client with the new Client ID
    initGoogle();
    showToast("✅ Settings saved (encrypted in your browser).");
  });

  function getClientId() {
    return Vault.get(user, "google_client_id") || CONFIG.GOOGLE_CLIENT_ID || "";
  }

  /* ============================================================
     NICHE TREE — Category -> Subcategory. User sets this ONCE and
     the AI always creates videos in the chosen field. Topics inside
     are just example hints for the AI (not shown to the user).
     ============================================================ */
  const NICHE_TREE = {
    "📚 Education": {
      "Study & Learning": ["Learn 3x faster", "The science of memory"],
      "Words & Language": ["Where words come from", "Hardest languages"],
      "Math & Logic": ["Why zero changed the world", "Fibonacci in nature"],
      "Life Skills": ["Beat procrastination", "How compound interest works"],
      "Exam & Career": ["Study routines that work", "Future-proof skills"],
      "General Knowledge": ["Did-you-know facts", "Things school never taught"],
    },
    "🔬 Science & Space": {
      "Space & Universe": ["Black holes & time", "Why Saturn has rings"],
      "Physics": ["What lightning is", "Why the sky is blue"],
      "Chemistry": ["Everyday reactions", "Why ice floats"],
      "Earth & Weather": ["How volcanoes work", "Why auroras glow"],
      "Biology & Life": ["What DNA is", "How the immune system fights"],
      "Tech Science": ["How lasers work", "The science of magnets"],
    },
    "🧠 Psychology & Mind": {
      "How the Brain Works": ["Your brain edits reality", "The dopamine loop"],
      "Emotions & Behaviour": ["Why we cry", "How habits form"],
      "Sleep & Dreams": ["Why we dream", "Lucid dreaming"],
      "Bias & Persuasion": ["Cognitive biases", "Why ads work"],
      "Relationships": ["Psychology of attraction", "How trust is built"],
      "Self-Improvement": ["Discipline over motivation", "Rewire your mind"],
    },
    "🏛️ History": {
      "Ancient World": ["Truth about the pyramids", "A day in Ancient Rome"],
      "Mysteries": ["Unsolved history", "Ancient tech we can't explain"],
      "Inventions": ["History of the internet", "Who discovered electricity"],
      "Empires & Kingdoms": ["Rise and fall of empires", "Forgotten kingdoms"],
      "Turning Points": ["Events that changed the world", "The Cold War in 60s"],
      "Everyday History": ["Why we shake hands", "Origin of common things"],
    },
    "🌿 Nature & Animals": {
      "Ocean Life": ["Octopus intelligence", "The Mariana Trench"],
      "Wild Animals": ["The unkillable tardigrade", "Sharks older than trees"],
      "Birds & Insects": ["How bees vote", "How birds navigate"],
      "Plants & Forests": ["How trees talk", "Inside the Amazon"],
      "Pets & Domestic": ["Why cats purr", "How dogs read us"],
      "Extreme Survival": ["Animals that survive anything", "Deep-sea creatures"],
    },
    "🌍 Geography & Places": {
      "Natural Wonders": ["Why Everest grows", "Secrets of Antarctica"],
      "Hidden Places": ["Strangest places on Earth", "Islands no one visits"],
      "Cities & Culture": ["Oldest cities alive", "Unusual traditions"],
      "Countries & Flags": ["Why flags look alike", "Tiniest countries"],
      "Maps & Borders": ["Weirdest borders", "Why time zones exist"],
      "Earth Facts": ["How glaciers shape land", "How deserts form"],
    },
    "💰 Money & Business": {
      "Money Basics": ["How money was invented", "Inflation explained"],
      "Brands & Companies": ["Hidden logo meanings", "Billion-dollar ideas"],
      "Economy Simplified": ["Supply & demand", "What a recession is"],
      "Entrepreneurship": ["Small ideas that got big", "Why startups fail"],
      "Investing Basics": ["Power of compounding", "How stocks work"],
      "Success Stories": ["From nothing to empire", "Inventions that sold"],
    },
    "💻 Tech & Internet": {
      "How Things Work": ["How the internet works", "How GPS finds you"],
      "AI & Future": ["What AI really is", "The future of robots"],
      "Digital Safety": ["How passwords get hacked", "Protect your data"],
      "Gadgets": ["How touchscreens work", "Why batteries die"],
      "Internet Culture": ["History of social media", "How search works"],
      "Coding & Computers": ["What code really is", "How computers think"],
    },
    "🍿 Entertainment & Pop Culture": {
      "Movies & Cinema": ["Movie tricks you missed", "How VFX is made"],
      "Music": ["Why songs get stuck", "The science of a hit"],
      "Celebrities & Fame": ["The psychology of fame", "Rise of icons"],
      "Gaming": ["How games hook you", "History of video games"],
      "Anime & Comics": ["Why anime blew up", "Comic universes explained"],
      "Trends & Memes": ["How things go viral", "The life of a meme"],
    },
    "⚽ Sports & Fitness": {
      "Football & Cricket": ["Why offside exists", "Physics of a swing"],
      "Sports Science": ["How athletes get faster", "The science of stamina"],
      "Fitness & Gym": ["Muscle myths busted", "How muscles grow"],
      "Legends & Records": ["Records that stood for decades", "Greatest comebacks"],
      "Olympics & Global": ["Weirdest Olympic sports", "History of the Games"],
      "Mind of Athletes": ["The winner's mindset", "Handling pressure"],
    },
    "🍔 Food & Cooking": {
      "Food Science": ["Why onions make you cry", "The Maillard reaction"],
      "World Cuisines": ["Origins of famous dishes", "Street food worldwide"],
      "Healthy Eating": ["Superfood myths", "What sugar does to you"],
      "Cooking Tricks": ["Kitchen hacks that work", "Why recipes fail"],
      "Drinks": ["The science of coffee", "How tea conquered the world"],
      "Food History": ["How pizza spread", "The story of chocolate"],
    },
    "✈️ Travel & Adventure": {
      "Wonders of the World": ["The 7 wonders", "Man-made marvels"],
      "Extreme Places": ["Hottest & coldest places", "Most remote spots"],
      "Cultures & People": ["Unique tribes", "Traditions that amaze"],
      "Travel Tips": ["Smart travel hacks", "Cheapest ways to travel"],
      "Lost & Abandoned": ["Abandoned cities", "Places frozen in time"],
      "Adventure & Survival": ["Surviving the wild", "Great expeditions"],
    },
    "🎨 Art & Creativity": {
      "Famous Art": ["Secrets in famous paintings", "Why the Mona Lisa is famous"],
      "Design & Colors": ["Psychology of colors", "Why logos are simple"],
      "Architecture": ["How skyscrapers stand", "Ancient building genius"],
      "Photography & Film": ["The rule of thirds", "How photos trick the eye"],
      "DIY & Crafts": ["Oddly satisfying crafts", "Everyday design flaws"],
      "Creativity Science": ["Where ideas come from", "How to be more creative"],
    },
    "🧘 Health & Lifestyle": {
      "Human Body": ["Why the heart never tires", "What the gut really does"],
      "Sleep & Rest": ["Why sleep matters", "The perfect nap"],
      "Mental Wellness": ["How stress affects you", "The science of calm"],
      "Habits & Routines": ["Morning routines that work", "Tiny habits, big change"],
      "Nutrition": ["What your body needs", "Water & your brain"],
      "Longevity": ["Secrets of long life", "How to age slower"],
    },
    "🚗 Automobiles & Machines": {
      "Cars & Engines": ["How engines work", "Why EVs are the future"],
      "Bikes & Speed": ["The physics of speed", "How brakes stop you"],
      "Aircraft & Flight": ["How planes stay up", "Fastest jets ever"],
      "Trains & Ships": ["How giant ships float", "Bullet train secrets"],
      "Machines & Engineering": ["How cranes lift tons", "Everyday machines"],
      "Future Transport": ["Flying cars?", "Hyperloop explained"],
    },
    "🔮 Mysteries & Unexplained": {
      "Unsolved Mysteries": ["Cases with no answer", "Vanished without a trace"],
      "Space Mysteries": ["Strange signals from space", "Could aliens exist?"],
      "Ancient Enigmas": ["Structures we can't explain", "Lost civilizations"],
      "Illusions & Brain Tricks": ["How illusions fool you", "Your senses lie"],
      "Strange Phenomena": ["Nature's weird events", "Science can't fully explain"],
      "Myths & Legends": ["Truth behind legends", "Creatures of folklore"],
    },
  };

  const catSel = document.getElementById("category");
  const subSel = document.getElementById("subcategory");
  const NICHE_KEY = "at_niche_" + user;

  function saveNiche() { localStorage.setItem(NICHE_KEY, JSON.stringify({ cat: catSel.value, sub: subSel.value })); }
  function loadNiche() { try { return JSON.parse(localStorage.getItem(NICHE_KEY)); } catch { return null; } }

  function fillCategories() {
    catSel.innerHTML = Object.keys(NICHE_TREE).map((c) => `<option>${c}</option>`).join("");
  }
  function fillSubcategories() {
    subSel.innerHTML = Object.keys(NICHE_TREE[catSel.value] || {}).map((s) => `<option>${s}</option>`).join("");
  }
  function updateNicheNote() {
    document.getElementById("nicheNote").innerHTML =
      `🎯 The AI will always create <b>${escapeHtml(catSel.value)} › ${escapeHtml(subSel.value)}</b> videos for your channel. Set once — the bot does the rest.`;
  }

  catSel.addEventListener("change", () => { fillSubcategories(); saveNiche(); updateNicheNote(); });
  subSel.addEventListener("change", () => { saveNiche(); updateNicheNote(); });

  // restore the user's saved field (keeps them consistent across sessions)
  fillCategories();
  const savedN = loadNiche();
  if (savedN && NICHE_TREE[savedN.cat]) catSel.value = savedN.cat;
  fillSubcategories();
  if (savedN && (NICHE_TREE[catSel.value] || {})[savedN.sub]) subSel.value = savedN.sub;
  updateNicheNote();

  /* ---------- channel state (per user) ---------- */
  const CHAN_KEY = "at_channel_" + user;
  function getChannel() { try { return JSON.parse(localStorage.getItem(CHAN_KEY)); } catch { return null; } }
  function setChannel(ch) {
    if (ch) localStorage.setItem(CHAN_KEY, JSON.stringify(ch)); else localStorage.removeItem(CHAN_KEY);
    renderChannel();
  }
  function renderChannel() {
    const ch = getChannel();
    const badge = document.getElementById("chanBadge");
    const status = document.getElementById("chanStatus");
    const nameEl = document.getElementById("chanName");
    const stChan = document.getElementById("stChan");
    if (ch) {
      badge.className = "badge on"; badge.textContent = "📺 " + ch.title;
      status.className = "badge on"; status.textContent = "Connected";
      nameEl.textContent = ch.title; stChan.textContent = ch.title;
      document.getElementById("connectBtn").textContent = "Reconnect";
    } else {
      badge.className = "badge off"; badge.textContent = "📺 Not connected";
      status.className = "badge off"; status.textContent = "Not connected";
      nameEl.textContent = ""; stChan.textContent = "—";
    }
  }

  /* ---------- Google OAuth (YouTube) ---------- */
  const SCOPES = "https://www.googleapis.com/auth/youtube.upload " +
                 "https://www.googleapis.com/auth/youtube.readonly";
  let tokenClient = null;

  function showChannelHelp(msg) {
    document.getElementById("gsetup").innerHTML = `
      <div class="steps" style="border-top:1px solid var(--border);padding-top:16px">
        ${msg}<br /><br />
        <b style="color:var(--text)">How to get the Google Client ID:</b><br />
        1. <a href="https://console.cloud.google.com/" target="_blank">Google Cloud Console</a> → create/select a project.<br />
        2. <b>APIs &amp; Services → Library</b> → enable <code>YouTube Data API v3</code>.<br />
        3. <b>OAuth consent screen</b> → External → add your Gmail as a <b>Test user</b>.<br />
        4. <b>Credentials → Create credentials → OAuth client ID</b> → <code>Web application</code>.<br />
        5. <b>Authorized JavaScript origins</b>: add <code>http://localhost</code> and your GitHub Pages URL.<br />
        6. Copy the <b>Client ID</b> → open the <b>Settings</b> tab → paste it → Save.<br />
        7. Come back here and press <b>Connect with Google</b>. ✅
      </div>`;
  }

  function initGoogle() {
    const cid = getClientId();
    if (!cid) { showChannelHelp("⚠️ No Google Client ID yet. Add it in <b>Settings</b> first."); return; }
    if (typeof google === "undefined" || !google.accounts) { setTimeout(initGoogle, 300); return; }
    document.getElementById("gsetup").innerHTML = "";
    tokenClient = google.accounts.oauth2.initTokenClient({
      client_id: cid,
      scope: SCOPES,
      callback: (resp) => {
        if (resp && resp.access_token) fetchChannel(resp.access_token);
        else showToast("Google sign-in was cancelled.");
      },
    });
  }

  function fetchChannel(accessToken) {
    fetch("https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true", {
      headers: { Authorization: "Bearer " + accessToken },
    })
      .then((r) => r.json())
      .then((data) => {
        const item = (data.items || [])[0];
        if (!item) { showToast("No YouTube channel found on this account."); return; }
        setChannel({ id: item.id, title: item.snippet.title, connectedAt: new Date().toLocaleString() });
        showToast("✅ Connected: " + item.snippet.title);
      })
      .catch(() => showToast("Could not read channel info."));
  }

  document.getElementById("connectBtn").addEventListener("click", () => {
    if (!getClientId()) { switchView("settings"); showToast("Add your Google Client ID in Settings first."); return; }
    if (!tokenClient) initGoogle();
    if (tokenClient) tokenClient.requestAccessToken();
  });

  /* ---------- requests ---------- */
  const REQ_KEY = "at_requests_" + user;
  function loadRequests() { try { return JSON.parse(localStorage.getItem(REQ_KEY)) || []; } catch { return []; } }
  function saveRequests(r) { localStorage.setItem(REQ_KEY, JSON.stringify(r)); }
  function renderRequests() {
    const reqs = loadRequests();
    document.getElementById("stReq").textContent = reqs.length;
    const list = document.getElementById("requestList");
    if (!reqs.length) { list.textContent = "No requests yet."; return; }
    list.innerHTML = reqs.slice().reverse().map((r) => `
      <div style="padding:10px 0;border-bottom:1px solid var(--border)">
        <b style="color:var(--text)">${escapeHtml(r.category || "")} › ${escapeHtml(r.subcategory || "")}</b>
        &nbsp;<span class="badge off">${r.status}</span><br />
        <small>${r.format} • ${r.language} • ${r.at}</small>
      </div>`).join("");
  }

  // Trigger the video-build Action via the GitHub API (needs a token in Settings).
  async function triggerWorkflow(req) {
    const token = Vault.get(user, "github_token");
    if (!token) return { ok: false, reason: "no_token" };
    const url = `https://api.github.com/repos/${CONFIG.GITHUB_OWNER}/${CONFIG.GITHUB_REPO}` +
                `/actions/workflows/${CONFIG.WORKFLOW_FILE}/dispatches`;
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: {
          Authorization: "Bearer " + token,
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
        },
        body: JSON.stringify({
          ref: CONFIG.GITHUB_REF,
          inputs: { category: req.category, subcategory: req.subcategory, language: req.language },
        }),
      });
      if (res.status === 204) return { ok: true };
      return { ok: false, reason: "http_" + res.status, detail: await res.text() };
    } catch (e) {
      return { ok: false, reason: "network", detail: String(e) };
    }
  }

  document.getElementById("generateBtn").addEventListener("click", async () => {
    if (!catSel.value) { showToast("Pick a category first."); return; }
    saveNiche();
    const req = {
      category: catSel.value,
      subcategory: subSel.value,
      language: document.getElementById("language").value,
      format: document.getElementById("format").value,
      status: "queued",
      at: new Date().toLocaleString(),
    };
    const reqs = loadRequests();
    reqs.push(req);
    saveRequests(reqs);
    renderRequests();
    switchView("requests");

    const btn = document.getElementById("generateBtn");
    btn.disabled = true;
    const r = await triggerWorkflow(req);
    btn.disabled = false;

    if (r.ok) {
      req.status = "building 🚀"; saveRequests(reqs); renderRequests();
      showToast("🚀 Sent to GitHub Actions — your video is building!");
    } else if (r.reason === "no_token") {
      showToast("Saved. Add a GitHub Token in Settings to auto-build videos.");
    } else {
      showToast("Saved, but auto-trigger failed (" + r.reason + "). Check the token & repo.");
      console.error("dispatch failed:", r.detail);
    }
  });

  /* ---------- init ---------- */
  renderSettings();
  renderChannel();
  renderRequests();
  initGoogle();
})();
