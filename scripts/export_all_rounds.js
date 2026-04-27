#!/usr/bin/env node
/**
 * Export ALL rounds from Cesim: Excels + decisions JSON + market outlook.
 * Usage: node scripts/export_all_rounds.js [--force] [--from N] [--to N]
 *
 * Idempotent: skips rounds whose Excel + decisions JSON already exist
 * unless --force is passed.
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const RESULTS_DIR = path.resolve(__dirname, '..', 'results');
const DECISIONS_DIR = path.resolve(__dirname, '..', 'decisions');
const ERRORS_DIR = path.resolve(__dirname, '.errors');

fs.mkdirSync(RESULTS_DIR, { recursive: true });
fs.mkdirSync(DECISIONS_DIR, { recursive: true });
fs.mkdirSync(ERRORS_DIR, { recursive: true });

const BASE = 'https://sim.cesim.com';
const EMAIL = process.env.CESIM_EMAIL;
const PASSWORD = process.env.CESIM_PASSWORD;

// Parse CLI args
let FORCE = false;
let FROM_ROUND = null;
let TO_ROUND = null;
for (let i = 2; i < process.argv.length; i++) {
  if (process.argv[i] === '--force') FORCE = true;
  if (process.argv[i] === '--from' && process.argv[i + 1]) { FROM_ROUND = parseInt(process.argv[i + 1], 10); i++; }
  if (process.argv[i] === '--to'   && process.argv[i + 1]) { TO_ROUND   = parseInt(process.argv[i + 1], 10); i++; }
}

const DECISION_PANELS = [
  { name: 'demand',           url: `${BASE}/ul/Decisions?panel=demand&sim=gc` },
  { name: 'production',       url: `${BASE}/ul/Decisions?panel=production&sim=gc` },
  { name: 'hr',               url: `${BASE}/ul/Decisions?panel=hr&sim=gc` },
  { name: 'rnd',              url: `${BASE}/ul/Decisions?panel=rnd&sim=gc` },
  { name: 'marketing_usa',    url: `${BASE}/ul/Decisions?panel=marketingusa&sim=gc` },
  { name: 'marketing_asia',   url: `${BASE}/ul/Decisions?panel=marketingasia&sim=gc` },
  { name: 'marketing_europe', url: `${BASE}/ul/Decisions?panel=marketingeurope&sim=gc` },
  { name: 'logistics',        url: `${BASE}/ul/Decisions?panel=logistics&sim=gc` },
  { name: 'tax',              url: `${BASE}/ul/Decisions?panel=tax&sim=gc` },
  { name: 'finance',          url: `${BASE}/ul/Decisions?panel=finance&sim=gc` },
  { name: 'market_outlook',   url: `${BASE}/ul/Decisions?panel=marketconditions&sim=gc` },
];

const RESULTS_EXTRA_PANELS = [
  { name: 'incomestatement', url: `${BASE}/ul/Results?sim=gc&panel=incomestatement` },
  { name: 'balancesheet',    url: `${BASE}/ul/Results?sim=gc&panel=balancesheet` },
  { name: 'cashflow',        url: `${BASE}/ul/Results?sim=gc&panel=cashflow` },
  { name: 'marketshares',    url: `${BASE}/ul/Results?sim=gc&panel=marketshares` },
  { name: 'rndstatus',       url: `${BASE}/ul/Results?sim=gc&panel=rndstatus` },
  { name: 'keyfigures',      url: `${BASE}/ul/Results?sim=gc&panel=keyfigures` },
];

function atomicWrite(finalPath, content) {
  const tmp = `${finalPath}.tmp`;
  fs.writeFileSync(tmp, content, 'utf8');
  fs.renameSync(tmp, finalPath);
}

function roundAlreadyDone(n) {
  const pad = String(n).padStart(2, '0');
  const hasXls =
    fs.existsSync(path.join(RESULTS_DIR, `results-pr${pad}.xls`)) ||
    fs.existsSync(path.join(RESULTS_DIR, `results-pr${pad}.xlsx`)) ||
    fs.existsSync(path.join(RESULTS_DIR, `results-r${pad}.xls`));
  const hasJson = fs.existsSync(path.join(DECISIONS_DIR, `round${n}_current.json`));
  return hasXls && hasJson;
}

async function login(page) {
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.fill('input[name="u"]', EMAIL);
  await page.fill('input[name="p"]', PASSWORD);
  await page.click('input[type="submit"]');
  await page.waitForLoadState('networkidle');
  console.log('Logged in.');
}

/**
 * Detect available rounds from the Results page.
 * Cesim typically shows a round dropdown or a list of past rounds.
 * Returns [{label, value, isCurrent}] sorted ascending.
 */
async function detectAvailableRounds(page) {
  await page.goto(`${BASE}/ul/Results?sim=gc&panel=overview`, { waitUntil: 'networkidle', timeout: 20000 });

  const rounds = await page.evaluate(() => {
    const results = [];

    // Pattern 1: <select> containing round options
    document.querySelectorAll('select').forEach(sel => {
      Array.from(sel.options).forEach(opt => {
        const m = opt.text.match(/(\d+)/) || opt.value.match(/(\d+)/);
        if (m) results.push({ label: opt.text.trim(), value: opt.value, num: parseInt(m[1], 10), selectId: sel.id || sel.name });
      });
    });

    // Pattern 2: links/buttons with round numbers in href or text
    if (results.length === 0) {
      document.querySelectorAll('a[href*="round"], a[href*="period"], .round-link, .period-link').forEach(a => {
        const m = a.textContent.match(/(\d+)/) || (a.href || '').match(/round[=_](\d+)/i);
        if (m) results.push({ label: a.textContent.trim(), value: a.href || '', num: parseInt(m[1], 10) });
      });
    }

    // Pattern 3: breadcrumb / nav items
    if (results.length === 0) {
      document.querySelectorAll('nav li, .breadcrumb li, .round-nav').forEach(li => {
        const m = li.textContent.match(/round\s+(\d+)/i) || li.textContent.match(/period\s+(\d+)/i);
        if (m) results.push({ label: li.textContent.trim(), num: parseInt(m[1], 10) });
      });
    }

    return results;
  });

  if (rounds.length === 0) {
    // Fallback: scan the page text for the current round number
    const pageText = await page.evaluate(() => document.body.innerText);
    const m = pageText.match(/round\s+(\d+)/i) || pageText.match(/period\s+(\d+)/i);
    if (m) {
      const n = parseInt(m[1], 10);
      console.warn(`  Round detection fallback: found round ${n} in page text`);
      return [{ label: `Round ${n}`, num: n, isCurrent: true }];
    }
    return [];
  }

  // Deduplicate and sort
  const seen = new Set();
  const unique = rounds
    .filter(r => r.num > 0 && !seen.has(r.num) && seen.add(r.num))
    .sort((a, b) => a.num - b.num);

  return unique;
}

/**
 * Select a specific past round in the Results dropdown, if possible.
 * Returns true if navigation succeeded.
 */
async function selectRound(page, roundInfo) {
  try {
    if (roundInfo.selectId) {
      await page.goto(`${BASE}/ul/Results?sim=gc&panel=overview`, { waitUntil: 'networkidle', timeout: 20000 });
      await page.selectOption(`#${roundInfo.selectId}`, { value: roundInfo.value });
      await page.waitForLoadState('networkidle');
      return true;
    }
    if (roundInfo.value && roundInfo.value.startsWith('http')) {
      await page.goto(roundInfo.value, { waitUntil: 'networkidle', timeout: 20000 });
      return true;
    }
  } catch (_) {}
  return false;
}

async function downloadResultsExcel(page, roundNum) {
  const pad = String(roundNum).padStart(2, '0');
  const downloadPromise = page.waitForEvent('download', { timeout: 30000 });
  await page.click('button[title="Download to Excel"]');
  const dl = await downloadPromise;

  const suggested = dl.suggestedFilename();
  const ext = (suggested.match(/\.(xls[x]?)$/i) || ['', 'xls'])[1];
  const saveName = `results-pr${pad}.${ext}`;
  const savePath = path.join(RESULTS_DIR, saveName);
  await dl.saveAs(savePath);
  return savePath;
}

async function extractPage(page, panel) {
  await page.goto(panel.url, { waitUntil: 'networkidle', timeout: 20000 });

  const fields = await page.evaluate(() => {
    const results = [];
    document.querySelectorAll('input:not([type="hidden"]), select, textarea').forEach(el => {
      let label = '';
      if (el.id) {
        const lbl = document.querySelector(`label[for="${el.id}"]`);
        if (lbl) label = lbl.textContent.trim();
      }
      if (!label) {
        const row = el.closest('tr');
        if (row) {
          const cells = row.querySelectorAll('td, th');
          if (cells.length > 0) label = cells[0].textContent.trim();
        }
      }
      if (!label) {
        const fg = el.closest('.form-group, .control-group, .field');
        if (fg) {
          const lbl = fg.querySelector('label');
          if (lbl) label = lbl.textContent.trim();
        }
      }
      let value = el.value;
      if (el.tagName === 'SELECT') {
        const opt = el.options[el.selectedIndex];
        value = opt ? `${opt.value} (${opt.text.trim()})` : el.value;
      }
      results.push({
        id: el.id || '',
        name: el.name || el.id || '',
        type: el.tagName === 'SELECT' ? 'select' : (el.type || 'text'),
        value,
        label: label.replace(/\s+/g, ' ').slice(0, 100),
        disabled: el.disabled || el.readOnly,
      });
    });
    return results;
  });

  const tables = await page.evaluate(() => {
    const tbls = [];
    document.querySelectorAll('table').forEach(tbl => {
      const rows = [];
      tbl.querySelectorAll('tr').forEach(row => {
        const cells = Array.from(row.querySelectorAll('td, th')).map(c => c.textContent.trim().replace(/\s+/g, ' '));
        if (cells.some(c => c)) rows.push(cells);
      });
      if (rows.length > 0) tbls.push({ rows: rows.slice(0, 20) });
    });
    return tbls.slice(0, 10);
  });

  const title = await page.title();
  const headings = await page.$$eval('h1, h2, .panel-title, .section-title', els => els.map(e => e.textContent.trim().replace(/\s+/g, ' ')));

  let prose = null;
  if (panel.name === 'market_outlook') {
    prose = await page.evaluate(() => {
      const blocks = [];
      document.querySelectorAll('p, li, .outlook-text, .market-text, .news-text, .content-block').forEach(el => {
        const text = el.textContent.trim().replace(/\s+/g, ' ');
        if (text.length > 20) blocks.push(text);
      });
      return blocks.slice(0, 60);
    });
  }

  const result = { panel: panel.name, url: panel.url, title, headings, fields: fields.filter(f => f.name || f.id), tables };
  if (prose !== null) result.prose = prose;
  return result;
}

async function extractRoundDecisions(page, roundNum) {
  console.log(`  Extracting decisions for round ${roundNum}...`);
  const allPanels = [];
  const marketData = { round: roundNum, extractedAt: new Date().toISOString() };

  for (const panel of DECISION_PANELS) {
    process.stdout.write(`    ${panel.name}... `);
    try {
      const data = await extractPage(page, panel);
      allPanels.push(data);
      const n = data.fields.filter(f => !f.disabled).length;
      console.log(`${n} editable`);
      if (panel.name === 'market_outlook') {
        marketData.headings = data.headings;
        marketData.prose = data.prose || [];
        marketData.tables = data.tables;
        marketData.fields = data.fields;
      }
    } catch (e) {
      console.log(`skip (${e.message.slice(0, 60)})`);
      allPanels.push({ panel: panel.name, error: e.message, fields: [], tables: [] });
    }
  }

  atomicWrite(path.join(DECISIONS_DIR, `round${roundNum}_current.json`), JSON.stringify(allPanels, null, 2));
  if (marketData.tables) {
    atomicWrite(path.join(DECISIONS_DIR, `round${roundNum}_market.json`), JSON.stringify(marketData, null, 2));
  }
}

async function extractResultsExtras(page, roundNum) {
  console.log(`  Extracting Results sub-panels for round ${roundNum}...`);
  const extras = [];
  for (const panel of RESULTS_EXTRA_PANELS) {
    process.stdout.write(`    ${panel.name}... `);
    try {
      const data = await extractPage(page, panel);
      extras.push(data);
      console.log(`${data.tables.length} tables`);
    } catch (e) {
      console.log(`skip`);
      extras.push({ panel: panel.name, error: e.message, fields: [], tables: [] });
    }
  }
  atomicWrite(path.join(DECISIONS_DIR, `round${roundNum}_results_extras.json`), JSON.stringify(extras, null, 2));
}

async function saveError(roundNum, err) {
  const errPath = path.join(ERRORS_DIR, `round${roundNum}.txt`);
  fs.writeFileSync(errPath, `${err.stack || err.message}\n`);
  console.error(`  Error saved: ${errPath}`);
}

async function main() {
  if (!EMAIL || !PASSWORD) {
    console.error('CESIM_EMAIL and CESIM_PASSWORD env vars required. Load from .env first.');
    process.exit(1);
  }

  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    acceptDownloads: true,
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  });
  const page = await ctx.newPage();

  try {
    await login(page);

    console.log('\nDetecting available rounds...');
    const availableRounds = await detectAvailableRounds(page);
    console.log(`Found ${availableRounds.length} round(s):`, availableRounds.map(r => r.num).join(', '));

    // If no rounds detected, process at least round 1 to current
    const rounds = availableRounds.length > 0
      ? availableRounds
      : Array.from({ length: 6 }, (_, i) => ({ num: i + 1 }));

    const toProcess = rounds.filter(r => {
      if (FROM_ROUND !== null && r.num < FROM_ROUND) return false;
      if (TO_ROUND   !== null && r.num > TO_ROUND)   return false;
      if (!FORCE && roundAlreadyDone(r.num)) {
        console.log(`  Round ${r.num}: skip (already done, use --force to re-export)`);
        return false;
      }
      return true;
    });

    if (toProcess.length === 0) {
      console.log('\nAll rounds already exported. Use --force to re-export.');
      return;
    }

    console.log(`\nWill process rounds: ${toProcess.map(r => r.num).join(', ')}`);

    // Determine which round is "current" (last in list = current active round)
    const currentRound = rounds[rounds.length - 1];

    for (const roundInfo of toProcess) {
      console.log(`\n===== ROUND ${roundInfo.num} =====`);
      try {
        // Navigate to this round's Results
        const navigated = await selectRound(page, roundInfo);
        if (!navigated) {
          // Fallback: navigate to overview directly
          await page.goto(`${BASE}/ul/Results?sim=gc&panel=overview`, { waitUntil: 'networkidle', timeout: 20000 });
        }

        // Download Excel
        console.log(`  Downloading Excel...`);
        const excelPath = await downloadResultsExcel(page, roundInfo.num);
        console.log(`  Saved: ${excelPath}`);

        // Extract Results sub-panels (while still on this round's view)
        await extractResultsExtras(page, roundInfo.num);

        // Extract decisions (always attempt; past rounds may return current-round data — accepted)
        await extractRoundDecisions(page, roundInfo.num);

        console.log(`  Round ${roundInfo.num}: done`);
      } catch (e) {
        console.error(`  Round ${roundInfo.num}: FAILED — ${e.message}`);
        await saveError(roundInfo.num, e);
      }
    }

    console.log('\n=== EXPORT COMPLETE ===');
    console.log('Results:', fs.readdirSync(RESULTS_DIR).join(', '));

  } finally {
    await browser.close();
  }
}

main().catch(e => { console.error(e); process.exit(1); });
