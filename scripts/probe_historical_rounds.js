#!/usr/bin/env node
/**
 * Probe Cesim Results page to extract historical per-round data via in-page round selector.
 * Strategy: Stay on the overview page, change round selector in-place, wait for AJAX update.
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const BASE = 'https://sim.cesim.com';
const EMAIL = process.env.CESIM_EMAIL;
const PASSWORD = process.env.CESIM_PASSWORD;

async function login(page) {
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.fill('input[name="u"]', EMAIL);
  await page.fill('input[name="p"]', PASSWORD);
  await page.click('input[type="submit"]');
  await page.waitForLoadState('networkidle');
  console.log('Logged in.');
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
      if (rows.length > 1) tbls.push(rows); // skip single-row tables
    });
    return tbls;
  });
}

async function capturePageText(page, maxChars = 4000) {
  return page.evaluate((max) => document.body.innerText.replace(/\s+/g, ' ').slice(0, max), maxChars);
}

async function navigateToResultsPanel(page, panelName) {
  const url = `${BASE}/ul/Results?sim=gc&panel=${panelName}`;
  await page.goto(url, { waitUntil: 'networkidle', timeout: 20000 });
  await page.waitForTimeout(500);
}

async function selectRoundAndCapture(page, roundValue, roundLabel) {
  // Change the round select value and trigger change event
  const changed = await page.evaluate(({ val }) => {
    // Try by name first (most reliable)
    let sel = document.querySelector('select[name="panel:round-select"]');
    if (!sel) sel = document.getElementById('id8');
    if (!sel) {
      // Fallback: find any select with option value matching
      document.querySelectorAll('select').forEach(s => {
        if (Array.from(s.options).some(o => o.value === String(val))) sel = s;
      });
    }
    if (!sel) return { found: false };
    const prevVal = sel.value;
    sel.value = String(val);
    sel.dispatchEvent(new Event('change', { bubbles: true }));
    sel.dispatchEvent(new Event('input', { bubbles: true }));
    return { found: true, prevVal, newVal: sel.value, id: sel.id, name: sel.name };
  }, { val: roundValue });

  console.log(`    Select change: ${JSON.stringify(changed)}`);

  if (!changed.found) return null;

  // Wait for the page to update (AJAX)
  await page.waitForTimeout(3000);
  try { await page.waitForLoadState('networkidle', { timeout: 8000 }); } catch (_) {}

  const tables = await captureAllTables(page);
  const text = await capturePageText(page, 2000);
  return { roundValue, roundLabel, tables, text };
}

const PANELS_TO_TRY = [
  'overview',
  'incomestatement',
  'keyfigures',
  'balancesheet',
  'cashflow',
  'marketshares',
];

async function main() {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
  });
  const page = await ctx.newPage();
  const results = { panels: {} };

  try {
    await login(page);

    for (const panelName of PANELS_TO_TRY) {
      console.log(`\n=== Panel: ${panelName} ===`);
      await navigateToResultsPanel(page, panelName);

      // Check for round select on this panel
      const selInfo = await page.evaluate(() => {
        let sel = document.querySelector('select[name="panel:round-select"]');
        if (!sel) sel = document.getElementById('id8');
        if (!sel) return null;
        return {
          id: sel.id, name: sel.name, currentValue: sel.value,
          options: Array.from(sel.options).map(o => ({ value: o.value, text: o.text.trim() })),
        };
      });

      if (!selInfo) {
        console.log('  No round select found on this panel.');
        const tables = await captureAllTables(page);
        results.panels[panelName] = { roundSelectFound: false, tables };
        continue;
      }

      console.log(`  Round select found: ${selInfo.options.length} options, current=${selInfo.currentValue}`);
      results.panels[panelName] = { roundSelectFound: true, currentValue: selInfo.currentValue, rounds: {} };

      // Capture each round
      for (const opt of selInfo.options) {
        const numMatch = opt.text.match(/\d+/);
        if (!numMatch) continue;
        const roundNum = parseInt(numMatch[0], 10);
        if (roundNum < 1 || roundNum > 8) continue;

        process.stdout.write(`  Round ${roundNum} (val=${opt.value}, "${opt.text}")... `);
        const data = await selectRoundAndCapture(page, opt.value, opt.text);
        if (data) {
          results.panels[panelName].rounds[roundNum] = {
            label: opt.text,
            tableCount: data.tables.length,
            tables: data.tables.slice(0, 5),
            textSnippet: data.text.slice(0, 600),
          };
          console.log(`${data.tables.length} tables`);
        } else {
          console.log('select not found');
          results.panels[panelName].rounds[roundNum] = { label: opt.text, error: 'select not found' };
        }

        // Re-navigate to reset round selector for next iteration
        await navigateToResultsPanel(page, panelName);
      }

      // Continue to next panel
    }

  } finally {
    await browser.close();
    const outPath = path.resolve(__dirname, '..', 'decisions', 'historical_probe.json');
    fs.writeFileSync(outPath, JSON.stringify(results, null, 2), 'utf8');
    console.log(`\nSaved to: ${outPath}`);
  }
}

main().catch(e => { console.error(e); process.exit(1); });
