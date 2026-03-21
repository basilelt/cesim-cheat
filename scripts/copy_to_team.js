const { chromium } = require('playwright');
const BASE = 'https://sim.cesim.com';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
  });
  const page = await ctx.newPage();

  page.on('dialog', async dialog => {
    console.log(`DIALOG: ${dialog.message()}`);
    await dialog.accept();
  });

  // Login
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.fill('input[name="u"]', process.env.CESIM_EMAIL);
  await page.fill('input[name="p"]', process.env.CESIM_PASSWORD);
  await page.click('input[type="submit"]');
  await page.waitForLoadState('networkidle');
  console.log('Logged in.');

  // Go to checklist and click "Go" for the TEAM area (first column)
  await page.goto(`${BASE}/ul/Decisions?panel=decisionchecklist&sim=gc`, { waitUntil: 'networkidle' });

  // Find the "Go" buttons in the "Go to decision area" row
  const goButtons = await page.evaluate(() => {
    const rows = Array.from(document.querySelectorAll('table tr'));
    for (const row of rows) {
      const cells = Array.from(row.querySelectorAll('td, th'));
      const cellTexts = cells.map(c => c.textContent.trim());
      if (cellTexts[0] === 'Go to decision area') {
        // Return info about buttons in each cell
        return cells.map((cell, i) => {
          const btn = cell.querySelector('button, a, input[type="submit"]');
          return {
            index: i,
            text: cellTexts[i],
            btnId: btn ? btn.id : null,
            btnTag: btn ? btn.tagName : null,
            btnHTML: btn ? btn.outerHTML.slice(0, 200) : null,
          };
        });
      }
    }
    return null;
  });
  console.log('Go buttons:', JSON.stringify(goButtons, null, 2));

  // Click the first "Go" button (team area)
  if (goButtons) {
    const teamBtn = goButtons.find(b => b.btnId && b.index === 1);
    if (teamBtn) {
      console.log(`Clicking team Go button: ${teamBtn.btnId}`);
      await page.click(`#${teamBtn.btnId}`);
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);
      console.log('Navigated to team area. URL:', page.url());

      // Now we should be in the team decision area
      // Navigate to each decision page and set the values

      const DECISIONS = [
        {
          name: 'demand',
          url: `${BASE}/ul/Decisions?panel=demand&sim=gc`,
          fields: [
            { name: 'panel:content:market-growth:r:3:c:3:decision', value: '20' },
            { name: 'panel:content:market-growth:r:4:c:3:decision', value: '40' },
            { name: 'panel:content:market-growth:r:5:c:3:decision', value: '15' },
          ],
        },
        {
          name: 'production',
          url: `${BASE}/ul/Decisions?panel=production&sim=gc`,
          fields: [
            { name: 'panel:content:contract-manufacturing:r:4:c:2:decision', value: '0' },
            { name: 'panel:content:contract-manufacturing:r:4:c:3:decision', value: '0' },
            { name: 'panel:content:contract-manufacturing:r:4:c:4:decision', value: '0' },
            { name: 'panel:content:contract-manufacturing:r:4:c:5:decision', value: '0' },
          ],
        },
        {
          name: 'hr',
          url: `${BASE}/ul/Decisions?panel=hr&sim=gc`,
          fields: [
            { name: 'panel:content:human-resources:r:9:c:2:decision', value: '1000' },
          ],
        },
        {
          name: 'marketing_usa',
          url: `${BASE}/ul/Decisions?panel=marketingusa&sim=gc`,
          fields: [
            { name: 'panel:content:marketing-area1-tech1:r:6:c:2:decision', value: '310' },
            { name: 'panel:content:marketing-area1-tech1:r:7:c:2:decision', value: '22000' },
          ],
        },
        {
          name: 'marketing_asia',
          url: `${BASE}/ul/Decisions?panel=marketingasia&sim=gc`,
          fields: [
            { name: 'panel:content:marketing-area2-tech1:r:6:c:2:decision', value: '2300' },
            { name: 'panel:content:marketing-area2-tech1:r:7:c:2:decision', value: '28000' },
          ],
        },
        {
          name: 'marketing_europe',
          url: `${BASE}/ul/Decisions?panel=marketingeurope&sim=gc`,
          fields: [
            { name: 'panel:content:marketing-area3-tech1:r:6:c:2:decision', value: '225' },
            { name: 'panel:content:marketing-area3-tech1:r:7:c:2:decision', value: '16000' },
          ],
        },
      ];

      for (const decision of DECISIONS) {
        console.log(`\n--- ${decision.name} ---`);
        await page.goto(decision.url, { waitUntil: 'networkidle', timeout: 20000 });

        // Verify we're in team area by checking page header/indicator
        const areaIndicator = await page.evaluate(() => {
          // Look for any indicator of which area we're editing
          const els = document.querySelectorAll('.decision-area-label, .area-name, h1, h2');
          return Array.from(els).map(e => e.textContent.trim()).slice(0, 5);
        });
        console.log('  Area:', areaIndicator.join(', '));

        for (const field of decision.fields) {
          try {
            await page.fill(`[name="${field.name}"]`, '');
            await page.fill(`[name="${field.name}"]`, field.value);
            console.log(`  SET: ${field.name} = ${field.value}`);
          } catch (e) {
            console.log(`  ERROR: ${field.name}: ${e.message}`);
          }
        }
        // Trigger blur
        await page.click('body', { position: { x: 10, y: 10 } });
        await page.waitForTimeout(1000);
      }

      // Go back to checklist to verify
      await page.goto(`${BASE}/ul/Decisions?panel=decisionchecklist&sim=gc`, { waitUntil: 'networkidle' });
      const profit = await page.evaluate(() => {
        for (const row of document.querySelectorAll('table tr')) {
          const cells = Array.from(row.querySelectorAll('td, th')).map(c => c.textContent.trim());
          if (cells[0] === 'Profit, k USD') return cells;
          if (cells[0] === 'Change in sales, %') return cells;
        }
        return null;
      });
      console.log('\nVerification - Profit:', profit?.join(' | '));

      // Also check contract mfg
      const contract = await page.evaluate(() => {
        let found = false;
        const results = [];
        for (const row of document.querySelectorAll('table tr')) {
          const cells = Array.from(row.querySelectorAll('td, th')).map(c => c.textContent.trim());
          if (cells[0] === 'Contract manufactured amount, k units') { found = true; continue; }
          if (found && cells[0]?.includes('product')) {
            results.push(cells);
            if (results.length >= 4) break;
          }
        }
        return results;
      });
      console.log('Contract mfg:', contract.map(r => r.join(' | ')).join('\n'));
    }
  }

  await page.screenshot({ path: 'after_copy_to_team.png', fullPage: false });
  await browser.close();
})();
