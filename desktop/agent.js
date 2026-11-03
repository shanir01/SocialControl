// Full Control agent — works ONLY inside the app's own embedded browser view.
// • In-memory session (no "persist:" partition): nothing is written to disk, and on end/Stop we wipe it anyway.
// • The user types their own login on Google's page; the app never reads or stores the password.
// • Every click is shown with a visible animated cursor; every change asks permission in the chat panel first.
const http = require("http");

const CURSOR_JS = `(() => {
  if (window.__sc) return true;
  const c = document.createElement("div");
  c.id = "__sc_cursor";
  c.innerHTML = '<svg width="28" height="28" viewBox="0 0 24 24"><path d="M3 2l7.5 19 2.6-7.6L21 10.8z" fill="#fff" stroke="#ff2e88" stroke-width="1.6" stroke-linejoin="round"/></svg>';
  Object.assign(c.style, { position: "fixed", left: "0", top: "0", zIndex: 2147483647, pointerEvents: "none", transition: "transform .85s cubic-bezier(.5,.1,.2,1)", transform: "translate(40px,40px)", filter: "drop-shadow(0 4px 8px rgba(0,0,0,.5))" });
  const st = document.createElement("style");
  st.textContent = "@keyframes __scr{from{transform:scale(.3);opacity:1}to{transform:scale(1.8);opacity:0}} .__scr{position:fixed;width:30px;height:30px;margin:-15px 0 0 -15px;border-radius:50%;border:3px solid #ff7a18;pointer-events:none;z-index:2147483647;animation:__scr .5s ease-out forwards} #__sc_shield{position:fixed;inset:0;z-index:2147483646;cursor:not-allowed} #__sc_badge{position:fixed;left:50%;top:10px;transform:translateX(-50%);z-index:2147483647;background:#111;color:#fff;font:600 13px Segoe UI,system-ui;padding:8px 14px;border-radius:99px;border:1px solid #ff2e88}";
  document.documentElement.append(st, c);
  window.__sc = {
    move(x, y) { c.style.transform = "translate(" + x + "px," + y + "px)"; },
    ripple(x, y) { const r = document.createElement("div"); r.className = "__scr"; r.style.left = x + "px"; r.style.top = y + "px"; document.documentElement.append(r); setTimeout(() => r.remove(), 600); },
    shield(on) { let s = document.getElementById("__sc_shield"), b = document.getElementById("__sc_badge");
      if (on && !s) { s = document.createElement("div"); s.id = "__sc_shield"; b = document.createElement("div"); b.id = "__sc_badge"; b.textContent = "🤖 AI chala raha hai — app me Stop dabao control wapas lene ke liye"; document.documentElement.append(s, b); }
      if (!on) { s && s.remove(); b && b.remove(); } },
  };
  return true;
})()`;

const STEPS = ["YouTube khula", "Aapne login kiya", "Control AI ko diya", "YouTube Studio khula", "Saari videos analyse", "Topic list bani", "Videos ban rahi hain", "Session deleted ✅"];

function api(base, method, path, body) {
  return new Promise((resolve, reject) => {
    const data = body === undefined ? null : Buffer.isBuffer(body) ? body : Buffer.from(JSON.stringify(body));
    const req = http.request(base + path, { method, headers: data ? { "Content-Type": Buffer.isBuffer(body) ? "image/jpeg" : "application/json", "Content-Length": data.length } : {} }, res => {
      let out = ""; res.on("data", d => out += d); res.on("end", () => { try { resolve(JSON.parse(out || "null")); } catch { resolve(out); } });
    });
    req.on("error", reject); if (data) req.write(data); req.end();
  });
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
class Stopped extends Error {}

class FullControl {
  constructor({ win, base, WebContentsView, session }) {
    Object.assign(this, { win, base, WebContentsView, sessionMod: session });
    this.s = { active: false, shared: false, stepIndex: -1, log: [], topics: [], url: "" };
    this.view = null; this.visible = true; this.rect = null;
  }
  state() { return this.s; }
  log(msg) { const e = { t: new Date().toTimeString().slice(0, 8), msg }; this.s.log.push(e); this.push({ log: msg }); }
  step(i) { this.s.stepIndex = i; this.push({}); }
  async push(extra) {
    try { const r = await api(this.base, "POST", "/api/fc/state", { active: this.s.active, shared: this.s.shared, stepIndex: this.s.stepIndex, url: this.s.url, topics: this.s.topics, ...extra });
      if (r && r.stop && this.s.active) this.stop("phone"); } catch {}
  }
  check() { if (!this.s.active) throw new Stopped(); }

  async start(rect) {
    if (this.s.active) return this.s;
    this.s = { active: true, shared: false, stepIndex: -1, log: [], topics: [], url: "youtube.com" };
    await api(this.base, "POST", "/api/fc/state", { reset: true, active: true });
    // In-memory partition: a name WITHOUT "persist:" is never written to disk.
    this.partition = "sc-fc-" + Date.now();
    this.ses = this.sessionMod.fromPartition(this.partition, { cache: false });
    const ua = this.ses.getUserAgent().replace(/\s?Electron\/\S+/, "").replace(/\s?socialcontrol\/\S+/i, "");
    this.ses.setUserAgent(ua);                                   // look like normal Chrome so Google's login page loads
    this.ses.setPermissionRequestHandler((_wc, _perm, cb) => cb(false)); // no camera/mic/notifications/etc.
    this.view = new this.WebContentsView({ webPreferences: { partition: this.partition, sandbox: true, contextIsolation: true, nodeIntegration: false } });
    this.win.contentView.addChildView(this.view);
    this.setBounds(rect);
    const wc = this.view.webContents;
    wc.setWindowOpenHandler(({ url }) => { wc.loadURL(url); return { action: "deny" }; });  // popups stay inside the view
    wc.on("did-navigate", (_e, url) => { this.s.url = url.replace(/^https?:\/\//, "").slice(0, 80); this.push({}); });
    wc.on("dom-ready", () => wc.executeJavaScript(CURSOR_JS).then(() => this.s.shared && wc.executeJavaScript("window.__sc.shield(true)")).catch(() => {}));
    this.frameTimer = setInterval(() => this.sendFrame(), 1000);
    this.run().catch(e => { if (!(e instanceof Stopped)) this.log("Error: " + e.message); this.stop("finished"); });
    return this.s;
  }

  setBounds(rect) {
    if (rect) this.rect = rect;
    if (!this.view || !this.rect) return;
    const r = this.rect;
    this.view.setBounds(this.visible ? { x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.width), height: Math.round(r.height) } : { x: 0, y: 0, width: 0, height: 0 });
  }
  setVisible(on) { this.visible = !!on; this.setBounds(); }

  async sendFrame() {
    if (!this.view) return;
    try { const img = await this.view.webContents.capturePage(); await api(this.base, "POST", "/api/fc/frame", img.resize({ width: 960 }).toJPEG(60)); } catch {}
  }

  // ---- visible cursor helpers (all inside the view) ----
  js(code) { this.check(); return this.view.webContents.executeJavaScript(code); }
  async point(selector) {
    const p = await this.js(`(() => { const e = document.querySelector(${JSON.stringify(selector)}); if (!e) return null; e.scrollIntoView({block:"center"}); const r = e.getBoundingClientRect(); return {x: r.x + r.width/2, y: r.y + r.height/2}; })()`);
    if (p) { await this.js(`window.__sc && window.__sc.move(${p.x}, ${p.y})`); await sleep(950); }
    return p;
  }
  async click(selector, label) {
    const p = await this.point(selector); if (!p) return false;
    this.log("Click: " + (label || selector));
    await this.js(`(() => { window.__sc && window.__sc.ripple(${p.x}, ${p.y}); const e = document.querySelector(${JSON.stringify(selector)}); e && e.click(); })()`);
    await sleep(700); return true;
  }
  async typeInto(selector, text, label) {
    const p = await this.point(selector); if (!p) return false;
    this.log("Likh raha hoon: " + label);
    await this.js(`(() => { const e = document.querySelector(${JSON.stringify(selector)}); e.focus(); document.execCommand("selectAll"); })()`);
    await this.view.webContents.insertText(text); await sleep(400); return true;
  }
  async waitFor(fn, timeoutMs, every = 1000) {
    const end = Date.now() + timeoutMs;
    while (Date.now() < end) { this.check(); try { if (await fn()) return true; } catch {} await sleep(every); }
    return false;
  }
  async ask(kind, title, details) {
    const a = await api(this.base, "POST", "/api/approvals", { kind, title, details, source: "fullcontrol" });
    this.log("Permission maangi (chat panel): " + title);
    let status = "pending";
    await this.waitFor(async () => { status = (await api(this.base, "GET", "/api/approvals/" + a.id)).status; return status !== "pending"; }, 6 * 3600e3, 1500);
    this.log(status === "accepted" ? "✅ Accept — kaam shuru" : "❌ Cancel — kuch nahi badla");
    return status === "accepted";
  }

  share() {
    if (!this.s.active || this.s.stepIndex < 1) return this.s;
    this.s.shared = true; this.step(2); this.log("Share Control — control AI ke paas");
    this.view.webContents.executeJavaScript("window.__sc && window.__sc.shield(true)").catch(() => {});
    return this.s;
  }

  // ---- the flow ----
  async run() {
    const wc = this.view.webContents;
    this.log("Private session bana (memory only)");
    await wc.loadURL("https://www.youtube.com/");
    this.step(0);
    await sleep(1500);
    const signIn = 'a[href*="ServiceLogin"], ytd-button-renderer a[aria-label*="Sign in"], tp-yt-paper-button[aria-label*="Sign in"]';
    if (await this.click(signIn, "Sign in")) this.log("Ab aap khud Google pe email + password daalo (app password nahi padhta)");
    else this.log("Already logged in ya Sign in button nahi mila");
    // wait until logged in (avatar visible on youtube.com) — the user types; we only watch the URL / avatar
    const ok = await this.waitFor(async () => /(^|\.)youtube\.com/.test(new URL(wc.getURL()).hostname)
      && await this.js(`!!document.querySelector("#avatar-btn, button#avatar-btn, ytd-topbar-menu-button-renderer img")`), 15 * 60e3, 1500);
    if (!ok) { this.log("Login nahi hua (15 min) — band kar raha hoon"); return; }
    this.step(1); this.log("Login ho gaya ✓ — ab 'Share Control' dabao");
    await this.waitFor(async () => this.s.shared, 30 * 60e3, 500);

    await wc.loadURL("https://studio.youtube.com/");
    await this.waitFor(async () => /studio\.youtube\.com\/channel\/UC/.test(wc.getURL()), 60e3);
    const channelId = (wc.getURL().match(/channel\/(UC[\w-]+)/) || [])[1];
    this.step(3); this.log("YouTube Studio khula — channel " + (channelId || "?"));
    await this.click('#menu-paper-icon-item-1, a[href*="/videos"]', "Content");
    await sleep(2500);

    // Analyse: rows are read on screen (with the cursor), full numbers come from the server (API if connected, else public list)
    const rows = await this.js(`[...document.querySelectorAll("ytcp-video-row")].slice(0, 30).map((r, i) => (r.setAttribute("data-sc", i), (r.querySelector("#video-title") || {}).textContent || "").trim())`).catch(() => []);
    for (let i = 0; i < Math.min(rows.length, 12); i++) { await this.point(`ytcp-video-row[data-sc="${i}"]`); this.log("Analyse: " + rows[i].slice(0, 60)); }
    const scan = await api(this.base, "GET", "/api/scan?channel=" + encodeURIComponent(channelId || ""));
    if (!scan || !scan.top_topics) { this.log("Channel data nahi mila: " + JSON.stringify(scan).slice(0, 120)); return; }
    this.step(4);
    const b = scan.buckets.cumulative;
    this.log(`${scan.total_videos} videos, ${scan.total_views} views · 100+: ${b["100+"]}, 500+: ${b["500+"]}, 1K+: ${b["1K+"]}, 10K+: ${b["10K+"]}`);
    this.s.topics = scan.top_topics.map(t => ({ keyword: t.keyword, views: t.views, example: t.examples[0] }));
    this.step(5); this.log("Topic list bani: " + this.s.topics.slice(0, 6).map(t => t.keyword).join(", "));

    // Optional: improve old videos' title/description/tags (Settings → Full Control). Each change asks first.
    const settings = await api(this.base, "GET", "/api/settings");
    if (settings.fc_update_metadata) {
      const status = await api(this.base, "GET", "/api/status");
      for (const v of scan.top_videos.slice(0, 3)) {
        this.check();
        const meta = await api(this.base, "POST", "/api/ai/metadata", { title: v.title, views: v.views });
        if (!meta || !meta.title) { this.log("AI metadata nahi mila (Gemini key?)"); break; }
        const yes = await this.ask("edit", `Is video ka title/description/tags badlun?`, [`Abhi: ${v.title}`, `Naya: ${meta.title}`, `Tags: ${(meta.tags || []).slice(0, 8).join(", ")}`, `Kyun: ${meta.reason || ""}`]);
        if (!yes) continue;
        if (status.youtube_connected) { await api(this.base, "POST", "/api/youtube/update", { id: v.id, title: meta.title, description: meta.description, tags: meta.tags }); this.log("Update ho gaya (YouTube API) ✓"); }
        else {
          await wc.loadURL(`https://studio.youtube.com/video/${v.id}/edit`); await sleep(3500);
          await this.typeInto("#title-textarea #textbox", meta.title, "title");
          await this.typeInto("#description-textarea #textbox", meta.description, "description");
          await this.click("#save", "Save"); this.log("Studio me save ✓ (tags ke liye Settings me YouTube connect karo)");
        }
      }
    }

    const n = Number(settings.fc_videos_per_session || 2);
    const go = await this.ask("fullcontrol", `Topic list se ${n} video banaun? (post Settings ke hisaab se)`, this.s.topics.slice(0, n).map(t => `${t.keyword} — jaise “${(t.example || "").slice(0, 50)}”`));
    if (go) { await api(this.base, "POST", "/api/fc/topics", { topics: this.s.topics }); this.step(6); this.log(`${n} videos queue me — Create Video me progress dekho`); }
  }

  async stop(why) {
    if (!this.view && !this.s.active) return this.s;
    this.s.active = false; this.s.shared = false;
    clearInterval(this.frameTimer);
    this.log(why === "user" || why === "phone" ? "STOP — control wapas aapke paas" : "Full Control khatam");
    try {
      // Trust rule: wipe EVERYTHING this session had — cookies, local storage, cache, auth.
      await this.ses.clearStorageData(); await this.ses.clearCache(); await this.ses.clearAuthCache(); await this.ses.clearHostResolverCache();
      this.view.webContents.close?.(); this.win.contentView.removeChildView(this.view);
    } catch (e) { this.log("Cleanup note: " + e.message); }
    this.view = null;
    this.s.stepIndex = 7; this.log("Session deleted ✅ (login, cookies, storage, cache)");
    await this.push({ session_deleted: new Date().toISOString() });
    return this.s;
  }
}
module.exports = { FullControl, STEPS };
