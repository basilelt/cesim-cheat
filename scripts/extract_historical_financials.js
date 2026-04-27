#!/usr/bin/env node
/**
 * Extract per-round financial data from Cesim Results panels via Highcharts JS variables.
 * For panels that render charts (no HTML tables), extracts chart series data.
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const BASE = 'https://sim.cesim.com';
const EMAIL = process.env.CESIM_EMAIL;
const PASSWORD = process.env.CESIM_PASSWORD;
const OUT_DIR = path.resolve(__dirname, '..', 'decisions');

async function login(page) {
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.fill('input[name="u"]', EMAIL);
  await page.fill('input[name="p"]', PASSWORD);
  await page.click('input[type="submit"]');
  await page.waitForLoadState('networkidle');
  console.log('Logged in.');
}

async function extractChartsData(page) {
  return page.evaluate(() => {
    const data = {};

    // Method 1: Highcharts global
    if (typeof Highcharts !== 'undefined' && Highcharts.charts) {
      data.highcharts = Highcharts.charts
        .filter(Boolean)
        .map(chart => ({
          title: chart.title?.textStr || '',
          xAxis: chart.xAxis?.[0]?.categories || [],
          series: (chart.series || []).map(s => ({
            name: s.name,
            data: s.yData || (s.points || []).map(p => p.y),
          })),
        }));
    }

    // Method 2: Look for global JS data variables
    const globalKeys = Object.keys(window).filter(k =>
      k.toLowerCase().includes('chart') ||
      k.toLowerCase().includes('result') ||
      k.toLowerCase().includes('data') ||
      k.toLowerCase().includes('income') ||
      k.toLowerCase().includes('financial')
    );
    data.globalKeys = globalKeys.slice(0, 30);

    // Method 3: Extract from script tags
    const scriptData = [];
    document.querySelectorAll('script').forEach(s => {
      const text = s.textContent;
      // Look for JSON-like financial data arrays
      if (text.includes('series') || text.includes('Net') || text.includes('Sales') || text.includes('EBITDA')) {
        const snippet = text.slice(0, 500).replace(/\s+/g, ' ');
        if (snippet.length > 50) scriptData.push(snippet);
      }
    });
    data.scriptSnippets = scriptData.slice(0, 5);

    // Method 4: Any visible numeric text on page
    const allText = document.body.innerText;
    const numberPatterns = allText.match(/[\d\s,]+(?:kUSD|mUSD|USD|%|k units)?/g);
    data.textSample = allText.replace(/\s+/g, ' ').slice(0, 1000);

    return data;
  });
}

async function selectRound(page, optionValue) {
  return page.evaluate(({ val }) => {
    let sel = document.querySelector('select[name="panel:round-select"]');
    if (!sel) return false;
    sel.value = String(val);
    sel.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  }, { val: optionValue });
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

async function capturePageFull(page) {
  const tables = await captureAllTables(page);
  const charts = await extractChartsData(page);
  const url = page.url();
  return { url, tables, charts };
}

const FINANCIAL_PANELS = [
  'incomestatement',
  'keyfigures',
  'balancesheet',
  'cashflow',
  'marketshares',
  'rndstatus',
];

// Real round options from Cesim (value -> label)
const ROUND_OPTIONS = [
  { value: '3', label: 'Round 1' },
  { value: '4', label: 'Round 2' },
  { value: '5', label: 'Round 3' },
  { value: '6', label: 'Round 4' },
  { value: '7', label: 'Round 5' },
  { value: '8', label: 'Round 6' },
  { value: '9', label: 'Round 7' },
  { value: '10', label: 'Round 8' },
];

async function main() {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
  });
  const page = await ctx.newPage();
  const allResults = {};

  try {
    await login(page);

    for (const panelName of FINANCIAL_PANELS) {
      console.log(`\n=== Panel: ${panelName} ===`);
      allResults[panelName] = {};

      for (const { value, label } of ROUND_OPTIONS) {
        process.stdout.write(`  ${label} (val=${value})... `);
        try {
          await page.goto(`${BASE}/ul/Results?sim=gc&panel=${panelName}`, { waitUntil: 'networkidle', timeout: 20000 });
          await page.waitForTimeout(500);
          const changed = await selectRound(page, value);
          if (!changed) { console.log('no selector'); continue; }
          await page.waitForTimeout(3000);
          try { await page.waitForLoadState('networkidle', { timeout: 6000 }); } catch (_) {}

          const data = await capturePageFull(page);
          allResults[panelName][label] = {
            tables: data.tables,
            highcharts: data.charts.highcharts || [],
            textSample: data.charts.textSample?.slice(0, 800) || '',
            scriptSnippets: data.charts.scriptSnippets || [],
            globalKeys: data.charts.globalKeys || [],
          };

          const tableCount = data.tables.length;
          const chartCount = (data.charts.highcharts || []).length;
          console.log(`${tableCount} tables, ${chartCount} charts`);

          // Take screenshot for visual reference
          const ssPath = path.join(OUT_DIR, `screenshot_${panelName}_${label.replace(/\s+/g,'')}.png`);
          await page.screenshot({ path: ssPath, fullPage: false });
        } catch (e) {
          console.log(`error: ${e.message.slice(0, 60)}`);
          allResults[panelName][label] = { error: e.message };
        }

        // Only process Round 1 first to check if we get data
        if (label === 'Round 1') {
          const d = allResults[panelName]['Round 1'];
          const hasData = (d.tables?.length > 0) || (d.highcharts?.length > 0);
          if (!hasData) {
            console.log(`  No data in ${panelName} for Round 1. Skipping other rounds.`);
            break;
          }
        }
      }
    }

  } finally {
    await browser.close();
    const outPath = path.join(OUT_DIR, 'historical_financials.json');
    fs.writeFileSync(outPath, JSON.stringify(allResults, null, 2), 'utf8');
    console.log(`\nSaved to: ${outPath}`);

    // Also summarize what we found
    console.log('\n=== SUMMARY ===');
    for (const [panel, rounds] of Object.entries(allResults)) {
      for (const [round, data] of Object.entries(rounds)) {
        if (data.error) continue;
        const t = data.tables?.length || 0;
        const c = data.highcharts?.length || 0;
        if (t > 0 || c > 0) {
          console.log(`  ${panel} / ${round}: ${t} tables, ${c} charts`);
        }
      }
    }
  }
}

main().catch(e => { console.error(e); process.exit(1); });
