#!/usr/bin/env node
/**
 * Cesim round automation script.
 * Usage: CESIM_* env vars set → node scripts/cesim_round.js <round_number>
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const ROUND = parseInt(process.argv[2] || '5', 10);
const EMAIL = process.env.CESIM_EMAIL;
const PASSWORD = process.env.CESIM_PASSWORD;

const RESULTS_DIR = path.resolve(__dirname, '..', 'results');
const DECISIONS_DIR = path.resolve(__dirname, '..', 'decisions');
fs.mkdirSync(RESULTS_DIR, { recursive: true });
fs.mkdirSync(DECISIONS_DIR, { recursive: true });

const BASE = 'https://sim.cesim.com';

// All decision panels (Marketing has sub-panels per region)
const DECISION_PANELS = [
  { name: 'demand',          url: `${BASE}/ul/Decisions?panel=demand&sim=gc` },
  { name: 'production',      url: `${BASE}/ul/Decisions?panel=production&sim=gc` },
  { name: 'hr',              url: `${BASE}/ul/Decisions?panel=hr&sim=gc` },
  { name: 'rnd',             url: `${BASE}/ul/Decisions?panel=rnd&sim=gc` },
  { name: 'marketing_usa',   url: `${BASE}/ul/Decisions?panel=marketingusa&sim=gc` },
  { name: 'marketing_asia',  url: `${BASE}/ul/Decisions?panel=marketingasia&sim=gc` },
  { name: 'marketing_europe',url: `${BASE}/ul/Decisions?panel=marketingeurope&sim=gc` },
  { name: 'logistics',       url: `${BASE}/ul/Decisions?panel=logistics&sim=gc` },
  { name: 'tax',             url: `${BASE}/ul/Decisions?panel=tax&sim=gc` },
  { name: 'finance',         url: `${BASE}/ul/Decisions?panel=finance&sim=gc` },
  { name: 'market_outlook',  url: `${BASE}/ul/Decisions?panel=marketconditions&sim=gc` },
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

async function downloadResults(page) {
  console.log('\nDownloading results...');
  await page.goto(`${BASE}/ul/Results?sim=gc&panel=overview`, { waitUntil: 'networkidle', timeout: 20000 });

  const downloadPromise = page.waitForEvent('download', { timeout: 30000 });
  await page.click('button[title="Download to Excel"]');
  const download = await downloadPromise;

  const filename = download.suggestedFilename();
  const savePath = path.join(RESULTS_DIR, filename);
  await download.saveAs(savePath);
  console.log('Downloaded:', savePath);
  return savePath;
}

async function extractPage(page, panel) {
  await page.goto(panel.url, { waitUntil: 'networkidle', timeout: 20000 });

  const fields = await page.evaluate(() => {
    const results = [];
    document.querySelectorAll('input:not([type="hidden"]), select, textarea').forEach(el => {
      // Find label
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

  // Extract reference tables
  const tables = await page.evaluate(() => {
    const tbls = [];
    document.querySelectorAll('table').forEach((tbl) => {
      const rows = [];
      tbl.querySelectorAll('tr').forEach(row => {
        const cells = Array.from(row.querySelectorAll('td, th')).map(c => c.textContent.trim().replace(/\s+/g, ' '));
        if (cells.some(c => c)) rows.push(cells);
      });
      if (rows.length > 0) tbls.push({ rows: rows.slice(0, 15) });
    });
    return tbls.slice(0, 8);
  });

  const title = await page.title();
  const h1s = await page.$$eval('h1, h2, .panel-title, .section-title', els => els.map(e => e.textContent.trim().replace(/\s+/g, ' ')));

  return {
    panel: panel.name,
    url: panel.url,
    title,
    headings: h1s,
    fields: fields.filter(f => f.name || f.id),
    tables,
  };
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

    // Download results
    const resultFile = await downloadResults(page);

    // Extract all decision pages
    console.log('\nExtracting decision pages...');
    const allPanels = [];
    for (const panel of DECISION_PANELS) {
      process.stdout.write(`  ${panel.name}... `);
      try {
        const data = await extractPage(page, panel);
        allPanels.push(data);
        const editableCount = data.fields.filter(f => !f.disabled).length;
        console.log(`${editableCount} editable fields`);
      } catch (e) {
        console.log(`ERROR: ${e.message}`);
        allPanels.push({ panel: panel.name, error: e.message, fields: [], tables: [] });
      }
    }

    // Save JSON
    const outPath = path.join(DECISIONS_DIR, `round${ROUND}_current.json`);
    fs.writeFileSync(outPath, JSON.stringify(allPanels, null, 2));
    console.log('\nDecision data saved to:', outPath);

    // Print summary
    console.log('\n=== CURRENT DECISION VALUES ===');
    for (const dp of allPanels) {
      console.log(`\n--- ${dp.panel.toUpperCase()} ---`);
      if (dp.error) {
        console.log('  ERROR:', dp.error);
        continue;
      }
      const editable = dp.fields.filter(f => !f.disabled);
      editable.forEach(f => {
        console.log(`  ${f.label || f.name || f.id}: ${f.value}`);
      });
      // Also print tables for market outlook
      if (dp.panel === 'market_outlook' && dp.tables.length > 0) {
        dp.tables.forEach(t => {
          t.rows.forEach(r => console.log(' ', r.join(' | ')));
        });
      }
    }

    console.log('\nResults file:', resultFile);

  } finally {
    await browser.close();
  }
}

main().catch(e => { console.error(e); process.exit(1); });
