#!/usr/bin/env node
/**
 * Cesim round data extractor.
 * Usage: node scripts/cesim_round.js [--round N] [--skip-download]
 * Defaults to current round (auto-detected from page).
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

// Parse args: support both positional (legacy) and --round N
let ROUND = null;
let SKIP_DOWNLOAD = false;
for (let i = 2; i < process.argv.length; i++) {
  if (process.argv[i] === '--round' && process.argv[i + 1]) {
    ROUND = parseInt(process.argv[i + 1], 10);
    i++;
  } else if (process.argv[i] === '--skip-download') {
    SKIP_DOWNLOAD = true;
  } else if (/^\d+$/.test(process.argv[i])) {
    ROUND = parseInt(process.argv[i], 10); // legacy positional
  }
}

const EMAIL = process.env.CESIM_EMAIL;
const PASSWORD = process.env.CESIM_PASSWORD;

const RESULTS_DIR = path.resolve(__dirname, '..', 'results');
const DECISIONS_DIR = path.resolve(__dirname, '..', 'decisions');
fs.mkdirSync(RESULTS_DIR, { recursive: true });
fs.mkdirSync(DECISIONS_DIR, { recursive: true });

const BASE = 'https://sim.cesim.com';

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

// Results sub-panels that may expose data beyond the Excel overview
const RESULTS_EXTRA_PANELS = [
  { name: 'incomestatement',  url: `${BASE}/ul/Results?sim=gc&panel=incomestatement` },
  { name: 'balancesheet',     url: `${BASE}/ul/Results?sim=gc&panel=balancesheet` },
  { name: 'cashflow',         url: `${BASE}/ul/Results?sim=gc&panel=cashflow` },
  { name: 'marketshares',     url: `${BASE}/ul/Results?sim=gc&panel=marketshares` },
  { name: 'rndstatus',        url: `${BASE}/ul/Results?sim=gc&panel=rndstatus` },
  { name: 'keyfigures',       url: `${BASE}/ul/Results?sim=gc&panel=keyfigures` },
];

async function login(page) {
  console.log('Logging in...');
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.fill('input[name="u"]', EMAIL);
  await page.fill('input[name="p"]', PASSWORD);
  await page.click('input[type="submit"]');
  await page.waitForLoadState('networkidle');
  console.log('Logged in. URL:', page.url());
}

async function detectCurrentRound(page) {
  try {
    await page.goto(`${BASE}/ul/Results?sim=gc&panel=overview`, { waitUntil: 'networkidle', timeout: 20000 });
    const roundNum = await page.evaluate(() => {
      // Common Cesim patterns for current round indicator
      const selectors = [
        '.current-round', '[data-round]', '.round-number',
        'h1', 'h2', '.panel-title',
      ];
      for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el) {
          const m = el.textContent.match(/round\s*[:\-]?\s*(\d+)/i) ||
                    el.textContent.match(/r[eé]tour\s+(\d+)/i) ||
                    el.textContent.match(/period\s+(\d+)/i);
          if (m) return parseInt(m[1], 10);
        }
      }
      // Fallback: look for any visible round number in the page
      const body = document.body.textContent;
      const m = body.match(/current\s+round[:\s]+(\d+)/i) ||
                body.match(/round\s+(\d+)\s+results/i);
      if (m) return parseInt(m[1], 10);
      return null;
    });
    return roundNum;
  } catch (e) {
    return null;
  }
}

async function downloadResults(page, roundNum) {
  console.log('\nDownloading results Excel...');
  await page.goto(`${BASE}/ul/Results?sim=gc&panel=overview`, { waitUntil: 'networkidle', timeout: 20000 });

  const downloadPromise = page.waitForEvent('download', { timeout: 30000 });
  await page.click('button[title="Download to Excel"]');
  const download = await downloadPromise;

  const suggested = download.suggestedFilename();
  // Normalise filename: prefer results-pr0N.xls pattern
  const paddedRound = String(roundNum).padStart(2, '0');
  const saveName = suggested.match(/\.(xls[x]?)$/i)
    ? `results-pr${paddedRound}.${suggested.match(/\.(xls[x]?)$/i)[1]}`
    : suggested;
  const savePath = path.join(RESULTS_DIR, saveName);

  await download.saveAs(savePath);
  console.log('Downloaded:', savePath);
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
    document.querySelectorAll('table').forEach((tbl) => {
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
  const h1s = await page.$$eval('h1, h2, .panel-title, .section-title', els => els.map(e => e.textContent.trim().replace(/\s+/g, ' ')));

  // Extra: capture prose text for market_outlook panel
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

  const result = {
    panel: panel.name,
    url: panel.url,
    title,
    headings: h1s,
    fields: fields.filter(f => f.name || f.id),
    tables,
  };
  if (prose !== null) result.prose = prose;
  return result;
}

async function extractResultsExtras(page, roundNum) {
  console.log('\nExtracting Results sub-panels...');
  const extras = [];
  for (const panel of RESULTS_EXTRA_PANELS) {
    process.stdout.write(`  ${panel.name}... `);
    try {
      const data = await extractPage(page, panel);
      extras.push(data);
      console.log(`${data.tables.length} tables`);
    } catch (e) {
      console.log(`SKIP: ${e.message}`);
      extras.push({ panel: panel.name, error: e.message, fields: [], tables: [] });
    }
  }

  const outPath = path.join(DECISIONS_DIR, `round${roundNum}_results_extras.json`);
  atomicWrite(outPath, JSON.stringify(extras, null, 2));
  console.log('Results extras saved:', outPath);
  return extras;
}

function atomicWrite(finalPath, content) {
  const tmpPath = `${finalPath}.tmp`;
  fs.writeFileSync(tmpPath, content, 'utf8');
  fs.renameSync(tmpPath, finalPath);
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    acceptDownloads: true,
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  });
  const page = await ctx.newPage();

  try {
    await login(page);

    // Detect current round if not specified
    if (ROUND === null) {
      const detected = await detectCurrentRound(page);
      ROUND = detected || 1;
      console.log(`Auto-detected round: ${ROUND}`);
    } else {
      console.log(`Using round: ${ROUND}`);
    }

    // Download results Excel
    let resultFile;
    if (!SKIP_DOWNLOAD) {
      resultFile = await downloadResults(page, ROUND);
    }

    // Extract all decision pages
    console.log('\nExtracting decision pages...');
    const allPanels = [];
    const marketData = {};

    for (const panel of DECISION_PANELS) {
      process.stdout.write(`  ${panel.name}... `);
      try {
        const data = await extractPage(page, panel);
        allPanels.push(data);
        const editableCount = data.fields.filter(f => !f.disabled).length;
        console.log(`${editableCount} editable fields`);

        // Separate market outlook into dedicated file
        if (panel.name === 'market_outlook') {
          marketData.headings = data.headings;
          marketData.prose = data.prose || [];
          marketData.tables = data.tables;
          marketData.fields = data.fields;
          marketData.round = ROUND;
          marketData.extractedAt = new Date().toISOString();
        }
      } catch (e) {
        console.log(`ERROR: ${e.message}`);
        allPanels.push({ panel: panel.name, error: e.message, fields: [], tables: [] });
      }
    }

    // Save decision JSON (atomic)
    const decisionsPath = path.join(DECISIONS_DIR, `round${ROUND}_current.json`);
    atomicWrite(decisionsPath, JSON.stringify(allPanels, null, 2));
    console.log('\nDecision data saved:', decisionsPath);

    // Save market outlook JSON (atomic)
    if (Object.keys(marketData).length > 0) {
      const marketPath = path.join(DECISIONS_DIR, `round${ROUND}_market.json`);
      atomicWrite(marketPath, JSON.stringify(marketData, null, 2));
      console.log('Market outlook saved:', marketPath);
    }

    // Extract Results sub-panels
    await extractResultsExtras(page, ROUND);

    // Summary
    console.log('\n=== CURRENT DECISION VALUES ===');
    for (const dp of allPanels) {
      console.log(`\n--- ${dp.panel.toUpperCase()} ---`);
      if (dp.error) { console.log('  ERROR:', dp.error); continue; }
      dp.fields.filter(f => !f.disabled).forEach(f => {
        console.log(`  ${f.label || f.name || f.id}: ${f.value}`);
      });
      if (dp.panel === 'market_outlook' && dp.tables.length > 0) {
        dp.tables[0].rows.forEach(r => console.log(' ', r.join(' | ')));
      }
    }

    if (resultFile) console.log('\nResults file:', resultFile);

  } finally {
    await browser.close();
  }
}

main().catch(e => { console.error(e); process.exit(1); });
