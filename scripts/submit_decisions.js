#!/usr/bin/env node
/**
 * Submit round 5 decisions to Cesim.
 */

const { chromium } = require('playwright');

const EMAIL = process.env.CESIM_EMAIL;
const PASSWORD = process.env.CESIM_PASSWORD;
const BASE = 'https://sim.cesim.com';

// Decisions to apply: { panel_url, fields: [ { name, value } ] }
const DECISIONS = [
  {
    name: 'demand',
    url: `${BASE}/ul/Decisions?panel=demand&sim=gc`,
    fields: [
      // Market growth estimates (align with market outlook)
      { name: 'panel:content:market-growth:r:3:c:3:decision', value: '20' },   // USA +20%
      { name: 'panel:content:market-growth:r:4:c:3:decision', value: '40' },   // Asia +40%
      { name: 'panel:content:market-growth:r:5:c:3:decision', value: '15' },   // Europe +15%
      // Product/warranty settings: keep as-is
    ],
  },
  {
    name: 'production',
    url: `${BASE}/ul/Decisions?panel=production&sim=gc`,
    fields: [
      // Contract manufacturing: SET TO ZERO (save ~$220M, inventory covers demand)
      { name: 'panel:content:contract-manufacturing:r:4:c:2:decision', value: '0' },  // USA Tech 1
      { name: 'panel:content:contract-manufacturing:r:4:c:3:decision', value: '0' },  // USA Tech 2
      { name: 'panel:content:contract-manufacturing:r:4:c:4:decision', value: '0' },  // Asia Tech 1
      { name: 'panel:content:contract-manufacturing:r:4:c:5:decision', value: '0' },  // Asia Tech 2
      // Keep in-house at 100% Tech 1 allocation (no change needed)
      // Keep 100% renewable energy (no change needed)
      // Keep sustainability investments checked (no change needed)
    ],
  },
  {
    name: 'hr',
    url: `${BASE}/ul/Decisions?panel=hr&sim=gc`,
    fields: [
      // Training: increase to improve R&D efficiency
      { name: 'panel:content:human-resources:r:9:c:2:decision', value: '1000' },  // Training $500→$1000
      // Keep 400 engineers, $4500 wage
    ],
  },
  {
    name: 'marketing_usa',
    url: `${BASE}/ul/Decisions?panel=marketingusa&sim=gc`,
    fields: [
      { name: 'panel:content:marketing-area1-tech1:r:6:c:2:decision', value: '310' },    // Price $320→$310
      { name: 'panel:content:marketing-area1-tech1:r:7:c:2:decision', value: '22000' },   // Promotion $18M→$22M
    ],
  },
  {
    name: 'marketing_asia',
    url: `${BASE}/ul/Decisions?panel=marketingasia&sim=gc`,
    fields: [
      { name: 'panel:content:marketing-area2-tech1:r:6:c:2:decision', value: '2300' },   // Price 2450→2300 RMB
      { name: 'panel:content:marketing-area2-tech1:r:7:c:2:decision', value: '28000' },   // Promotion $22M→$28M
    ],
  },
  {
    name: 'marketing_europe',
    url: `${BASE}/ul/Decisions?panel=marketingeurope&sim=gc`,
    fields: [
      { name: 'panel:content:marketing-area3-tech1:r:6:c:2:decision', value: '225' },    // Price €235→€225
      { name: 'panel:content:marketing-area3-tech1:r:7:c:2:decision', value: '16000' },   // Promotion $12M→$16M
    ],
  },
  // Logistics, Tax, Finance, R&D: NO CHANGES
];

async function login(page) {
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.fill('input[name="u"]', EMAIL);
  await page.fill('input[name="p"]', PASSWORD);
  await page.click('input[type="submit"]');
  await page.waitForLoadState('networkidle');
  console.log('Logged in:', page.url());
}

async function applyDecisions(page, decision) {
  console.log(`\n=== ${decision.name.toUpperCase()} ===`);
  await page.goto(decision.url, { waitUntil: 'networkidle', timeout: 20000 });

  for (const field of decision.fields) {
    const selector = `[name="${field.name}"]`;
    try {
      const el = await page.$(selector);
      if (!el) {
        console.log(`  SKIP: ${field.name} not found`);
        continue;
      }
      const tagName = await el.evaluate(e => e.tagName);

      if (tagName === 'SELECT') {
        await page.selectOption(selector, field.value);
        console.log(`  SET (select): ${field.name} = ${field.value}`);
      } else {
        // Clear and fill for text inputs
        await page.fill(selector, '');
        await page.fill(selector, field.value);
        console.log(`  SET: ${field.name} = ${field.value}`);
      }
    } catch (e) {
      console.log(`  ERROR on ${field.name}: ${e.message}`);
    }
  }

  // Trigger blur/change events by clicking elsewhere, then wait for any AJAX
  await page.click('body', { position: { x: 10, y: 10 } });
  await page.waitForTimeout(1000);

  // Take screenshot of final state
  await page.screenshot({ path: `decision_${decision.name}_after.png`, fullPage: false });
  console.log(`  Screenshot saved: decision_${decision.name}_after.png`);
}

async function readProjection(page) {
  // Read the "This round" projection from the income statement sidebar
  const projection = await page.evaluate(() => {
    const rows = [];
    document.querySelectorAll('table tr').forEach(tr => {
      const cells = Array.from(tr.querySelectorAll('td, th')).map(c => c.textContent.trim());
      if (cells.length >= 2 && cells[1]) {
        rows.push(cells);
      }
    });
    return rows.slice(0, 15);
  });
  return projection;
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  });
  const page = await ctx.newPage();

  try {
    await login(page);

    for (const decision of DECISIONS) {
      await applyDecisions(page, decision);
    }

    // Read final projection from the last page visited
    console.log('\n=== FINAL PROJECTION (from last page) ===');
    const proj = await readProjection(page);
    proj.forEach(row => console.log(' ', row.join(' | ')));

    // Navigate to decision checklist to verify
    console.log('\n=== DECISION CHECKLIST ===');
    await page.goto(`${BASE}/ul/Decisions?panel=decisionchecklist&sim=gc`, { waitUntil: 'networkidle' });
    await page.screenshot({ path: 'decision_checklist.png', fullPage: true });
    console.log('Checklist screenshot saved: decision_checklist.png');

    // Print key info from checklist
    const checklistInfo = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('table tr')).map(tr => {
        const cells = Array.from(tr.querySelectorAll('td, th')).map(c => c.textContent.trim().replace(/\s+/g, ' '));
        return cells;
      }).filter(r => r.some(c => c)).slice(0, 30);
    });
    checklistInfo.forEach(row => console.log(' ', row.join(' | ')));

    console.log('\nDone. Decisions applied (NOT submitted to simulation).');
    console.log('Please verify the checklist screenshot and confirm before final submission.');

  } finally {
    await browser.close();
  }
}

main().catch(e => { console.error(e); process.exit(1); });
