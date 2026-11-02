#!/usr/bin/env node
const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');

const COOKIES_FILE = process.argv[2] || path.join(__dirname, '..', '..', '.multi-ai-tokens', 'claude_cookies.json');
const TOKEN_FILE = process.argv[3] || path.join(__dirname, '..', '..', '.multi-ai-tokens', 'claude_token.txt');

(async () => {
  const browser = await chromium.launch({ headless: false, args: ['--no-sandbox'] });
  const context = await browser.newContext();
  const page = await context.newPage();

  if (fs.existsSync(COOKIES_FILE)) {
    const cookies = JSON.parse(fs.readFileSync(COOKIES_FILE));
    await context.addCookies(cookies);
  }

  let capturedToken = null;
  let orgId = null;
  page.on('request', req => {
    const headers = req.headers();
    const auth = headers['authorization'] || headers['x-api-key'];
    if (auth && auth.startsWith('Bearer ') && !capturedToken) {
      capturedToken = auth.replace('Bearer ', '');
      orgId = headers['anthropic-organization-id'] || null;
      console.log('🔥 Captured Claude token!');
    }
  });

  await page.goto('https://claude.ai/login', { waitUntil: 'networkidle' });
  console.log('👉 Log in manually, then press Enter...');
  process.stdin.once('data', async () => {
    await page.goto('https://claude.ai', { waitUntil: 'networkidle' });
    await page.waitForTimeout(5000);

    const cookies = await context.cookies();
    fs.writeFileSync(COOKIES_FILE, JSON.stringify(cookies, null, 2));

    if (capturedToken) {
      let tokenData = { token: capturedToken };
      if (orgId) tokenData.org_id = orgId;
      fs.writeFileSync(TOKEN_FILE, JSON.stringify(tokenData));
      console.log('✅ Token saved to', TOKEN_FILE);
    } else {
      console.log('❌ No token captured.');
    }
    await browser.close();
    process.exit(0);
  });
})();