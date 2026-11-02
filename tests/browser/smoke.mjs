/* Browser smoke test for the static UI.
 *
 * Serves this repo on a random port, drives Chromium, and checks that the page
 * renders what audit.js computes. Node and Playwright are test-only: the site
 * itself has no build step and no dependencies.
 *
 * Run: npm ci && npx playwright install chromium && npm run test:ui
 */
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { extname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const require = createRequire(import.meta.url);
const here = fileURLToPath(new URL(".", import.meta.url));
const ROOT = resolve(here, "..", "..");
const SpendAudit = require(join(ROOT, "audit.js"));

const read = (name) => readFile(join(ROOT, name), "utf8");
const pricesDoc = JSON.parse(await read("data/prices.json"));
const presets = JSON.parse(await read("data/presets.json"));
const rows = pricesDoc.rows.map((row) =>
  Object.fromEntries(pricesDoc.cols.map((col, i) => [col, row[i]])));

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".md": "text/markdown; charset=utf-8",
  ".svg": "image/svg+xml"
};

const server = createServer(async (req, res) => {
  const path = decodeURIComponent(new URL(req.url, "http://localhost").pathname);
  const file = normalize(join(ROOT, path === "/" ? "index.html" : path));
  if (!file.startsWith(ROOT + "/")) {
    res.writeHead(403).end("forbidden");
    return;
  }
  try {
    const body = await readFile(file);
    res.writeHead(200, { "content-type": MIME[extname(file)] || "application/octet-stream" });
    res.end(body);
  } catch {
    res.writeHead(404).end("not found");
  }
});
await new Promise((done) => server.listen(0, "127.0.0.1", done));
const BASE = `http://127.0.0.1:${server.address().port}/`;

const failures = [];
const check = (ok, message) => {
  if (!ok) failures.push(message);
};
const money = (text) => Number(String(text).replace(/,/g, "").replace(/[^0-9.-]/g, ""));
const closeTo = (a, b, tolerance = 0.011) => Math.abs(a - b) <= tolerance;

const browser = await chromium.launch();

function watch(page, errors, label) {
  page.on("pageerror", (err) => errors.push(label + " pageerror: " + err));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(label + " console: " + msg.text());
  });
}

async function open(options = {}) {
  const page = await browser.newPage(Object.assign({ viewport: { width: 1280, height: 1000 } }, options));
  const errors = [];
  watch(page, errors, options.label || "page");
  await page.goto(BASE + (options.hash || ""), { waitUntil: "load" });
  await page.waitForSelector(".cards");
  return { page, errors };
}

async function table(page) {
  return page.evaluate(() => [...document.querySelectorAll("tbody tr")].map((tr) => {
    const sub = tr.querySelector(".td-sub");
    return {
      model: tr.querySelector("td.model").childNodes[0].textContent.trim(),
      provider: sub ? sub.textContent.trim() : "",
      cells: [...tr.children].map((td) => td.textContent.trim()),
      delta: (tr.querySelector(".delta") || {}).textContent || "",
      verdict: (tr.querySelector(".verdict") || {}).textContent || ""
    };
  }));
}

try {
  const { page, errors } = await open({ label: "desktop" });

  const freshness = await page.innerText("#freshness");
  check(/Dataset last updated \d{4}-\d{2}-\d{2}/.test(freshness), "freshness: " + freshness);
  check(/LiteLLM price snapshot of \d{4}-\d{2}-\d{2}/.test(freshness), "price date: " + freshness);
  check(!/undefined/.test(freshness), "freshness has undefined: " + freshness);
  const coverage = await page.innerText("#coverage");
  check(/verified/.test(coverage) && /paid models/.test(coverage), "coverage: " + coverage);

  for (const preset of presets) {
    await page.selectOption("#preset", preset.id);
    await page.waitForTimeout(120);
    const expected = SpendAudit.audit(preset, rows, 500);
    const cells = await table(page);
    const shown = Math.min(3, expected.alternatives.length);
    check(cells.length === 1 + shown, `${preset.id}: ${cells.length} rows, expected ${1 + shown}`);
    check(cells[0].model === preset.current_model, `${preset.id}: current model ${cells[0].model}`);
    check(closeTo(money(cells[0].cells[3]), expected.current_cost), `${preset.id}: current cost ${cells[0].cells[3]}`);
    check(String(expected.current_score) === cells[0].cells[5], `${preset.id}: current score ${cells[0].cells[5]}`);
    expected.alternatives.slice(0, shown).forEach((alt, i) => {
      const row = cells[i + 1];
      check(row.model === alt.model_id, `${preset.id} alt${i}: model ${row.model}`);
      check(row.provider === alt.provider, `${preset.id} alt${i}: provider ${row.provider}`);
      check(closeTo(money(row.cells[3]), alt.monthly_cost), `${preset.id} alt${i}: cost ${row.cells[3]}`);
      check(closeTo(money(row.cells[4]), alt.savings_pct, 0.06), `${preset.id} alt${i}: savings ${row.cells[4]}`);
      check(Number(row.cells[5]) === alt.score, `${preset.id} alt${i}: score ${row.cells[5]}`);
      const delta = (alt.score_delta > 0 ? "+" : "") + alt.score_delta + " pts";
      check(row.delta === delta, `${preset.id} alt${i}: delta ${row.delta} vs ${delta}`);
      check((row.verdict === "same or better") === (alt.score_delta >= 0), `${preset.id} alt${i}: verdict ${row.verdict}`);
    });
    const hash = await page.evaluate(() => location.hash);
    check(hash.includes("model=" + encodeURIComponent(preset.current_model)) || hash.includes("model=" + preset.current_model),
      `${preset.id}: hash ${hash}`);
  }

  // Full list toggle: gpt-6-astra has more than three cheaper scored options.
  const big = { current_model: "gpt-6-astra", monthly_input_m: 200,
                monthly_output_m: 40, needs: [] };
  const bigExpected = SpendAudit.audit(big, rows, 500);
  check(bigExpected.alternatives.length > 3, "toggle fixture has too few options");
  await page.fill("#model", big.current_model);
  await page.fill("#tokens-in", String(big.monthly_input_m));
  await page.fill("#tokens-out", String(big.monthly_output_m));
  await page.waitForTimeout(200);
  check((await table(page)).length === 4, "toggle: collapsed rows before click");
  const toggle = page.locator('[data-action="toggle-all"]');
  check((await toggle.innerText()).includes(String(bigExpected.alternatives.length)),
    "toggle: count missing from " + (await toggle.innerText()));
  await toggle.click();
  await page.waitForTimeout(150);
  check((await table(page)).length === 1 + bigExpected.alternatives.length, "toggle: all rows");
  check((await page.innerText('[data-action="toggle-all"]')).includes("Show fewer"), "toggle: label");
  await page.click('[data-action="toggle-all"]');
  await page.waitForTimeout(150);
  check((await table(page)).length === 4, "toggle: collapsed rows after second click");

  // Unscored model: spend only, no recommendation and no table.
  await page.fill("#model", "gpt-4o");
  await page.waitForTimeout(150);
  const unscored = await page.innerText("#results");
  check(unscored.includes("no Artificial Analysis score"), "unscored notice: " + unscored.slice(0, 120));
  check((await page.locator("tbody").count()) === 0, "unscored must not render a table");

  await page.fill("#model", "definitely-not-a-model");
  await page.waitForTimeout(150);
  check((await page.innerText("#results")).includes("No paid price rows"), "unknown model notice");

  await page.fill("#model", "claude-sonnet-5-5");
  await page.fill("#tokens-in", "0");
  await page.fill("#tokens-out", "0");
  await page.waitForTimeout(150);
  check((await page.innerText("#results")).includes("Enter your monthly tokens"), "zero tokens notice");

  const share = await page.inputValue("#share-url");
  check(share.includes("#model=") && share.includes("input=0"), "share url: " + share);

  check(await page.locator('meta[property="og:title"]').count() === 1, "og:title missing");

  check(errors.length === 0, "desktop errors: " + errors.join(" | "));
  await page.close();

  // Hash restore on a fresh page.
  const shared = await open({ label: "hash", hash: "#model=minimax-m3&input=50&output=55&needs=" });
  check(await shared.page.inputValue("#model") === "minimax-m3", "hash: model");
  check(await shared.page.inputValue("#preset") === "translation", "hash: preset");
  const sharedRows = await table(shared.page);
  check(sharedRows.length === 2 && sharedRows[1].delta === "+17 pts",
    "hash: translation alternative " + JSON.stringify(sharedRows[1]));
  check(shared.errors.length === 0, "hash errors: " + shared.errors.join(" | "));
  await shared.page.close();

  // Mobile: no page overflow, quality delta must stay visible.
  const mobile = await open({ label: "mobile", viewport: { width: 390, height: 844 } });
  const overflow = await mobile.page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth);
  check(overflow === 0, "mobile overflow: " + overflow);
  check(await mobile.page.locator("td.model").first().isVisible(), "mobile model cell hidden");
  check(await mobile.page.locator(".delta").first().isVisible(), "mobile quality delta hidden");
  check(await mobile.page.locator(".cta a.button").first().isVisible(), "mobile CTA hidden");
  check(mobile.errors.length === 0, "mobile errors: " + mobile.errors.join(" | "));
  await mobile.page.close();

  // Dark mode applies the dark palette.
  const dark = await open({ label: "dark", colorScheme: "dark" });
  const bg = await dark.page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  const channels = bg.match(/\d+/g).map(Number);
  check(channels[0] + channels[1] + channels[2] < 200, "dark background: " + bg);
  check(dark.errors.length === 0, "dark errors: " + dark.errors.join(" | "));
  await dark.page.close();

  // The request CTA carries the current workload, not just a template link.
  const cta = await open({ label: "cta" });
  await cta.page.fill("#model", "claude-sonnet-5-5");
  await cta.page.fill("#tokens-in", "60");
  await cta.page.fill("#tokens-out", "6");
  await cta.page.waitForTimeout(150);
  const href = await cta.page.getAttribute("#cta-request", "href");
  check(href.startsWith("https://github.com/ons96/llm-spend-auditor/issues/new?"), "cta base: " + href);
  check(href.includes("body=") && href.includes("claude-sonnet-5-5"), "cta prefill missing");
  check(href.includes(encodeURIComponent("60")), "cta input missing");
  check(cta.errors.length === 0, "cta errors: " + cta.errors.join(" | "));
  await cta.page.close();
} finally {
  await browser.close();
  server.close();
}

if (failures.length) {
  console.error("FAIL (" + failures.length + ")");
  for (const failure of failures) console.error(" - " + failure);
  process.exit(1);
}
console.log(`UI smoke ok: ${presets.length} presets, toggle, error paths, hash, mobile, dark, CTA`);
