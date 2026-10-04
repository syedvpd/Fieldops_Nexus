const { chromium } = require("playwright-core");
const path = require("path");
const seed = require("./vid/e2e_seed.json");
const BASE = process.env.BASE || "http://localhost:8010";
const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const vid = (n) => path.join(__dirname, "vid", n + ".mjpeg");
const results = [];
const log = (name, ok, detail) => { results.push({ name, ok }); console.log((ok ? "PASS " : "FAIL ") + name + " :: " + detail); };

async function launch(video, { fakeUi = true, fakeDevice = true, native = true, noDevice = false } = {}) {
  const args = ["--no-sandbox"];
  if (fakeDevice) { args.push("--use-fake-device-for-media-stream"); if (video) args.push("--use-file-for-fake-video-capture=" + vid(video)); }
  if (fakeUi) args.push("--use-fake-ui-for-media-stream"); else args.push("--deny-permission-prompts");
  const browser = await chromium.launch({ executablePath: CHROME, headless: true, args });
  const ctx = await browser.newContext({ viewport: { width: 412, height: 860 } });
  if (noDevice) await ctx.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException("Requested device not found", "NotFoundError"));
  });
  if (!native) await ctx.addInitScript(() => { delete window.BarcodeDetector; });
  return { browser, ctx };
}
async function login(page, email) {
  await page.goto(BASE + "/accounts/login/");
  await page.fill("input[name=username], input[name=email]", email);
  await page.fill("input[name=password]", seed.pw);
  await Promise.all([page.waitForNavigation(), page.click("button[type=submit], form button")]);
}
async function scan(video, email, opts = {}, wait = 25000) {
  const { browser, ctx } = await launch(video, opts);
  const page = await ctx.newPage();
  const navs = [];
  let engineSeen = null;
  const resolveRequests = [];
  page.on("request", (q) => { if (/\/app\/s\//.test(q.url()) && q.resourceType() === "document") resolveRequests.push(q.url()); });
  page.on("console", (m) => { const t = m.text(); if (t.startsWith("[fx-scanner] decoder:")) engineSeen = t.split(": ")[1]; });
  page.on("framenavigated", (f) => { if (f === page.mainFrame()) navs.push(f.url()); });
  await login(page, email);
  await page.goto(BASE + "/app/identification/scan/");
  let url = null;
  try { await page.waitForURL((u) => !u.pathname.endsWith("/identification/scan/"), { timeout: wait }); url = page.url(); } catch (e) {}
  const engine = await page.evaluate(() => (document.getElementById("scan-camera") || {}).dataset?.engine).catch(() => null);
  const status = await page.evaluate(() => (document.getElementById("scan-status") || {}).textContent).catch(() => "");
  const err = await page.evaluate(() => { const e = document.getElementById("scan-error"); return e && !e.hidden ? e.textContent : ""; }).catch(() => "");
  const body = await page.evaluate(() => document.body.innerText.slice(0, 300)).catch(() => "");
  const title = await page.title().catch(() => "");
  return { browser, page, navs, resolveRequests, url, engine: engineSeen || engine, status, err, body, title };
}

(async () => {
  const assetUrl = new RegExp("/app/assets/" + seed.a.asset + "/");
  // A. valid QR, native decoder allowed (whatever this Chrome supports) and bundled ZXing forced
  for (const native of [true, false]) {
    const r = await scan("valid_alpha", "tech@alpha.test", { native });
    const resolved = r.url && assetUrl.test(r.url);
    log(`valid FieldOps QR -> asset detail (decoder=${r.engine}, nativeAllowed=${native})`, !!resolved, r.url + " | title: " + r.title);
    log(`exactly one resolve request while detection keeps seeing the QR (decoder=${r.engine})`, r.resolveRequests.length === 1, "requests to /app/s/: " + r.resolveRequests.length);
    await r.browser.close();
  }
  // E. invalid QR (not a FieldOps label): stays on the page, says so
  let r = await scan("invalid_text", "tech@alpha.test", { native: false }, 9000);
  log("invalid QR rejected on the page, no navigation", !r.url && /not a FieldOps asset label/i.test(r.status), r.status);
  await r.browser.close();
  // well-shaped but unknown token -> server 404 page
  r = await scan("unknown_token", "tech@alpha.test", { native: false }, 20000);
  log("unknown label -> not-found page (server decides)", r.url && /\/app\/s\//.test(r.url) && /not recogni|not found|no asset|Not found/i.test(r.body + r.title), r.url + " | " + r.body.slice(0, 80).replace(/\n/g, " "));
  await r.browser.close();
  // H. cross-tenant: Alpha user scans Beta's label
  r = await scan("cross_tenant_beta", "tech@alpha.test", { native: false }, 20000);
  log("cross-tenant label -> not found, no asset opened", r.url && /\/app\/s\//.test(r.url) && !/\/app\/assets\//.test(r.url) && !/Boiler feed pump B/.test(r.body), r.url + " | " + r.body.slice(0, 80).replace(/\n/g, " "));
  await r.browser.close();
  // I. unauthorized: scoped user (site S2 only) scans a site-S1 asset label
  r = await scan("valid_alpha", "scoped@alpha.test", { native: false }, 20000);
  log("unauthorized (no access to that site) -> denied as not found", r.url && /\/app\/s\//.test(r.url) && !/\/app\/assets\//.test(r.url), r.url + " | " + r.body.slice(0, 80).replace(/\n/g, " "));
  await r.browser.close();
  // authorised scoped user on an asset of their own site works
  r = await scan("valid_other_site", "scoped@alpha.test", { native: false }, 25000);
  log("scoped user scans an asset of their own site -> asset detail", r.url && /\/app\/assets\//.test(r.url), r.url);
  await r.browser.close();
  // D. permission denied
  r = await scan("valid_alpha", "tech@alpha.test", { fakeUi: false }, 5000);
  const retryVisible = await r.page.isVisible("#scan-retry");
  log("camera permission denied -> clear message + Retry button, no navigation", !r.url && /permission was denied|blocked/i.test(r.err) && retryVisible, r.err.slice(0, 90));
  await r.page.fill("#scan-token", seed.a.token);
  await Promise.all([r.page.waitForNavigation(), r.page.click("#scan-form button")]);
  log("manual code fallback after denial -> resolves the asset", /\/app\/s\//.test(r.page.url()) || /\/app\/assets\//.test(r.page.url()), r.page.url());
  await r.browser.close();
  // C. permission allowed handled above. No camera device at all:
  // (this Chrome always offers a virtual camera, so the browser's "no device" error is raised on the API itself)
  r = await scan(null, "tech@alpha.test", { fakeDevice: false, fakeUi: true, noDevice: true }, 5000);
  log("no camera on the device -> 'No camera' message + manual entry", /No camera|could not be started/i.test(r.err), r.err.slice(0, 90));
  await r.browser.close();
  // J. manual code (full link)
  {
    const { browser, ctx } = await launch(null, { fakeDevice: false });
    const page = await ctx.newPage();
    await login(page, "tech@alpha.test");
    await page.goto(BASE + "/app/identification/scan/");
    await page.fill("#scan-token", BASE + "/app/s/" + seed.a.token + "/");
    await Promise.all([page.waitForNavigation(), page.click("#scan-form button")]);
    log("manual code (pasted link) -> resolved asset page", /Boiler feed pump A/.test(await page.content()), page.url());
    await browser.close();
  }
  const failed = results.filter((x) => !x.ok).length;
  console.log(`\n${results.length - failed}/${results.length} passed`);
  process.exit(failed ? 1 : 0);
})();
