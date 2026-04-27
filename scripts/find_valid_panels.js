#!/usr/bin/env node
/**
 * Find valid Results panel names and extract per-round financial data.
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

async function extractAll(page) {
  const tables = await page.evaluate(() => {
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

  const charts = await page.evaluate(() => {
    if (typeof Chart !== 'undefined') {
      return Array.from(Chart.instances || Object.values(Chart.instances || {})).map(c => ({
        type: c.config?.type,
        labels: c.data?.labels,
        datasets: (c.data?.datasets || []).map(d => ({ label: d.label, data: d.data })),
      }));
    }
    if (typeof Highcharts !== 'undefined') {
      return (Highcharts.charts || []).filter(Boolean).map(c => ({
        title: c.title?.textStr,
        series: (c.series || []).map(s => ({ name: s.name, data: s.yData })),
      }));
    }
    return [];
  });

  const text = await page.evaluate(() => document.body.innerText.replace(/\s+/g, ' ').slice(0, 2000));
  const links = await page.evaluate(() =>
    Array.from(document.querySelectorAll('a')).map(a => ({ text: a.textContent.trim(), href: a.href })).filter(a => a.text && a.href.includes('cesim'))
  );

  return { tables, charts, text, links };
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ userAgent: 'Mozilla/5.0' });
  const page = await ctx.newPage();

  try {
    await login(page);

    // Step 1: From overview, find nav links to other result panels
    console.log('=== Discovering panel URLs from overview navigation ===');
    await page.goto(`${BASE}/ul/Results?sim=gc&panel=overview`, { waitUntil: 'networkidle', timeout: 20000 });
    const navLinks = await page.evaluate(() =>
      Array.from(document.querySelectorAll('a, button')).map(el => ({
        text: el.textContent.trim().replace(/\s+/g, ' '),
        href: el.href || '',
        onclick: el.getAttribute('onclick') || '',
      })).filter(el => el.text.length > 2 && el.text.length < 60)
    );
    console.log('Nav elements:', navLinks.slice(0, 40).map(l => `"${l.text}": ${l.href || l.onclick}`).join('\n'));

    // Step 2: Try guessed panel names
    const panelCandidates = [
      'financialstatements', 'financial', 'statements',
      'ratios', 'keyratio', 'keyratios',
      'marketreports', 'market', 'hr',
      'sustainability', 'esg',
      'production', 'cost', 'costs',
      'rnd', 'rndstatus',
      'ranking', 'results',
    ];

    const validPanels = [];
    for (const p of panelCandidates) {
      await page.goto(`${BASE}/ul/Results?sim=gc&panel=${p}`, { waitUntil: 'networkidle', timeout: 15000 });
      const isValid = await page.evaluate(() => !document.body.innerText.includes('could not locate panel'));
      const tableCount = await page.evaluate(() => document.querySelectorAll('table').length);
      if (isValid) {
        console.log(`VALID: ${p} (${tableCount} tables)`);
        validPanels.push({ panel: p, tableCount });
      }
    }

    console.log('\n=== Valid panels:', validPanels.map(p => p.panel).join(', '));

    // Step 3: For each valid panel with tables, capture per-round data
    const results = {};
    const ROUNDS = [
      { val: '3', label: 'R1' }, { val: '4', label: 'R2' }, { val: '5', label: 'R3' },
      { val: '6', label: 'R4' }, { val: '7', label: 'R5' }, { val: '8', label: 'R6' },
      { val: '9', label: 'R7' }, { val: '10', label: 'R8' },
    ];

    for (const { panel } of validPanels.filter(p => p.tableCount > 0)) {
      console.log(`\n--- Extracting: ${panel} ---`);
      results[panel] = {};

      for (const { val, label } of ROUNDS) {
        process.stdout.write(`  ${label}... `);
        await page.goto(`${BASE}/ul/Results?sim=gc&panel=${panel}`, { waitUntil: 'networkidle', timeout: 15000 });
        await page.waitForTimeout(400);
        await selectRound(page, val);
        await page.waitForTimeout(3000);
        try { await page.waitForLoadState('networkidle', { timeout: 5000 }); } catch (_) {}

        const data = await extractAll(page);
        results[panel][label] = { tables: data.tables, charts: data.charts };
        console.log(`${data.tables.length}t ${data.charts.length}c`);
      }
    }

    const outPath = path.resolve(__dirname, '..', 'decisions', 'panel_discovery.json');
    fs.writeFileSync(outPath, JSON.stringify({ navLinks: navLinks.slice(0, 50), validPanels, results }, null, 2));
    console.log(`\nSaved: ${outPath}`);

  } finally {
    await browser.close();
  }
}

main().catch(e => { console.error(e); process.exit(1); });
