#!/usr/bin/env node
/**
 * Submit Round 6 decisions to Cesim.
 * Approved plan: feature expansion via license, competitive pricing, Asia demand correction, LT debt issuance.
 */

const { chromium } = require('playwright');

const EMAIL = process.env.CESIM_EMAIL;
const PASSWORD = process.env.CESIM_PASSWORD;
const BASE = 'https://sim.cesim.com';

const DECISIONS = [
  {
    name: 'demand',
    url: `${BASE}/ul/Decisions?panel=demand&sim=gc`,
    fields: [
      // Asia: reduce from 40% to 35% (market says "over 30%", not 40%)
      { name: 'panel:content:market-growth:r:4:c:3:decision', value: '35' },
    ],
  },
  {
    name: 'rnd',
    url: `${BASE}/ul/Decisions?panel=rnd&sim=gc`,
    fields: [
      // In-house: develop 1 additional Tech 1 feature (available Round 7)
      { name: 'panel:content:product-development:r:8:c:2:decision', value: '1' },
      // License: buy 1 additional Tech 1 feature (available immediately this round)
      { name: 'panel:content:buying-technology:r:3:c:2:decision', value: '1' },
    ],
  },
  {
    name: 'marketing_usa',
    url: `${BASE}/ul/Decisions?panel=marketingusa&sim=gc`,
    fields: [
      { name: 'panel:content:marketing-area1-tech1:r:3:c:2:decision', value: '5' },     // features 4→5
      { name: 'panel:content:marketing-area1-tech1:r:6:c:2:decision', value: '305' },   // price $310→$305
      { name: 'panel:content:marketing-area1-tech1:r:7:c:2:decision', value: '24000' }, // promo $22M→$24M
    ],
  },
  {
    name: 'marketing_asia',
    url: `${BASE}/ul/Decisions?panel=marketingasia&sim=gc`,
    fields: [
      { name: 'panel:content:marketing-area2-tech1:r:3:c:2:decision', value: '5' },     // features 4→5
      { name: 'panel:content:marketing-area2-tech1:r:6:c:2:decision', value: '2150' },  // price 2300→2150 RMB
      { name: 'panel:content:marketing-area2-tech1:r:7:c:2:decision', value: '30000' }, // promo $28M→$30M
    ],
  },
  {
    name: 'marketing_europe',
    url: `${BASE}/ul/Decisions?panel=marketingeurope&sim=gc`,
    fields: [
      { name: 'panel:content:marketing-area3-tech1:r:3:c:2:decision', value: '5' },     // features 4→5
      { name: 'panel:content:marketing-area3-tech1:r:6:c:2:decision', value: '215' },   // price €225→€215
      { name: 'panel:content:marketing-area3-tech1:r:7:c:2:decision', value: '18000' }, // promo $16M→$18M
    ],
  },
  {
    name: 'finance',
    url: `${BASE}/ul/Decisions?panel=finance&sim=gc`,
    fields: [
      // Increase LT debt by $500M to help retire expensive short-term debt
      { name: 'panel:content:financing:r:4:c:2:decision', value: '500000' },
    ],
  },
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
        await page.fill(selector, '');
        await page.fill(selector, field.value);
        console.log(`  SET: ${field.name} = ${field.value}`);
      }
    } catch (e) {
      console.log(`  ERROR on ${field.name}: ${e.message}`);
    }
  }

  await page.click('body', { position: { x: 10, y: 10 } });
  await page.waitForTimeout(1500);
}

async function verifyAndScreenshot(page, panelName, url) {
  await page.goto(url, { waitUntil: 'networkidle', timeout: 20000 });
  const shot = `decision_r6_${panelName}_verify.png`;
  await page.screenshot({ path: shot, fullPage: false });
  console.log(`  Screenshot: ${shot}`);
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

    // Verify key panels
    console.log('\n=== VERIFICATION SCREENSHOTS ===');
    await verifyAndScreenshot(page, 'rnd', `${BASE}/ul/Decisions?panel=rnd&sim=gc`);
    await verifyAndScreenshot(page, 'marketing_usa', `${BASE}/ul/Decisions?panel=marketingusa&sim=gc`);
    await verifyAndScreenshot(page, 'finance', `${BASE}/ul/Decisions?panel=finance&sim=gc`);

    // Checklist
    console.log('\n=== DECISION CHECKLIST ===');
    await page.goto(`${BASE}/ul/Decisions?panel=decisionchecklist&sim=gc`, { waitUntil: 'networkidle' });
    await page.screenshot({ path: 'decision_r6_checklist.png', fullPage: true });
    const checklistInfo = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('table tr')).map(tr => {
        return Array.from(tr.querySelectorAll('td, th')).map(c => c.textContent.trim().replace(/\s+/g, ' '));
      }).filter(r => r.some(c => c)).slice(0, 30);
    });
    checklistInfo.forEach(row => console.log(' ', row.join(' | ')));

    console.log('\nDone. Decisions applied (NOT yet submitted to simulation).');
    console.log('Checklist screenshot: decision_r6_checklist.png');

  } finally {
    await browser.close();
  }
}

main().catch(e => { console.error(e); process.exit(1); });
