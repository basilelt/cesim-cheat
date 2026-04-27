#!/usr/bin/env node
/**
 * Extract complete per-round historical data from all valid Cesim Results panels.
 * Panels: ranking, ratios, financialstatementsglobal, areareportglobal,
 *         hrresults, productionoverview, costsoverview, sustainability
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const BASE = 'https://sim.cesim.com';
const EMAIL = process.env.CESIM_EMAIL;
const PASSWORD = process.env.CESIM_PASSWORD;
const OUT = path.resolve(__dirname, '..', 'decisions');

async function login(page) {
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.fill('input[name="u"]', EMAIL);
  await page.fill('input[name="p"]', PASSWORD);
  await page.click('input[type="submit"]');
  await page.waitForLoadState('networkidle');
  console.log('Logged in.');
}

async function selectRound(page, val) {
  return page.evaluate(({ v }) => {
    const sel = document.querySelector('select[name="panel:round-select"]');
    if (!sel) return false;
    sel.value = String(v);
    sel.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  }, { v: val });
}

async function captureAllTables(page) {
  return page.evaluate(() => {
    const tbls = [];
    document.querySelectorAll('table').forEach(tbl => {
      const rows = [];
      tbl.querySelectorAll('tr').forEach(row => {
        const cells = Array.from(row.querySelectorAll('td, th')).map(c => c.textContent.trim().replace(/\s+/g, ' '));
        if (cells.some(c => c)) rows.push(cells);
      });
      if (rows.length > 0) tbls.push(rows);
    });
    return tbls;
  });
}

async function capturePageText(page) {
  return page.evaluate(() => document.body.innerText.replace(/\s+/g, ' ').slice(0, 3000));
}

async function captureRoundData(page, panel, roundVal) {
  await page.goto(`${BASE}/ul/Results?panel=${panel}&sim=gc`, { waitUntil: 'networkidle', timeout: 20000 });
  await page.waitForTimeout(400);
  const changed = await selectRound(page, roundVal);
  if (!changed) return null;
  await page.waitForTimeout(3500);
  try { await page.waitForLoadState('networkidle', { timeout: 6000 }); } catch (_) {}
  const tables = await captureAllTables(page);
  const text = await capturePageText(page);
  return { tables, text };
}

const ROUNDS = [
  { val: '0', label: 'IR0' },
  { val: '1', label: 'PR1' },
  { val: '2', label: 'PR2' },
  { val: '3', label: 'R1' },
  { val: '4', label: 'R2' },
  { val: '5', label: 'R3' },
  { val: '6', label: 'R4' },
  { val: '7', label: 'R5' },
  { val: '8', label: 'R6' },
  { val: '9', label: 'R7' },
  { val: '10', label: 'R8' },
];

// Panels to probe (from discovered nav links)
const PANELS = [
  'ranking',
  'ratios',
  'financialstatementsglobal',
  'areareportglobal',
  'hrresults',
  'productionoverview',
  'costsoverview',
  'sustainability',
  'overview',
];

async function main() {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36' });
  const page = await ctx.newPage();
  const results = {};

  try {
    await login(page);

    for (const panel of PANELS) {
      console.log(`\n=== Panel: ${panel} ===`);
      results[panel] = {};

      for (const { val, label } of ROUNDS) {
        process.stdout.write(`  ${label}... `);
        try {
          const data = await captureRoundData(page, panel, val);
          if (!data) { console.log('no selector'); continue; }
          const isError = data.text.includes('could not locate panel');
          if (isError) { console.log('invalid panel'); break; }
          results[panel][label] = { tables: data.tables, textSnippet: data.text.slice(0, 400) };
          console.log(`${data.tables.length} tables`);
        } catch (e) {
          console.log(`err: ${e.message.slice(0, 50)}`);
          results[panel][label] = { error: e.message };
        }
      }

      // Save after each panel
      fs.writeFileSync(path.join(OUT, 'all_historical_raw.json'), JSON.stringify(results, null, 2));
    }

  } finally {
    await browser.close();
    console.log('\nDone. Saved to decisions/all_historical_raw.json');
  }
}

main().catch(e => { console.error(e); process.exit(1); });
