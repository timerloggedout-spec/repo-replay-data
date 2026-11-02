#!/usr/bin/env node
const { chromium } = require('playwright-core');  // lighter than puppeteer
const fs = require('fs');
const path = require('path');

const COOKIES_FILE = process.argv[2] || path.join(__dirname, '..', '..', '.multi-ai-tokens', 'mistral_cookies.json');
const TOKEN_FILE = process.argv[2] ? process.argv[3] : path.join(__dirname, '..', '..', '.multi-ai-tokens', 'mistral_token.txt');

(async () => {
  const browser = await chromium.launch({ headless: false, args: ['--no-sandbox'] });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Load saved cookies if available
  if (fs.existsSync(COOKIES_FILE)) {
    const cookies = JSON.parse(fs.readFileSync(COOKIES_FILE));
    await context.addCookies(cookies);
  }

  let capturedToken = null;
  page.on('request', req => {
    const auth = req.headers()['authorization'];
    if (auth && auth.startsWith('Bearer ') && !capturedToken) {
      capturedToken = auth.replace('Bearer ', '');
      console.log('🔥 Captured Mistral token!');
    }
  });

  await page.goto('https://chat.mistral.ai', { waitUntil: 'networkidle' });
  console.log('👉 Please log in manually, then press Enter in this terminal...');
  process.stdin.once('data', async () => {
    // Navigate to trigger API calls
    await page.goto('https://chat.mistral.ai', { waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);

    // Save cookies
    const cookies = await context.cookies();
    fs.writeFileSync(COOKIES_FILE, JSON.stringify(cookies, null, 2));
    console.log('🍪 Cookies saved.');

    if (capturedToken) {
      fs.writeFileSync(TOKEN_FILE, capturedToken);
      console.log('✅ Token saved to', TOKEN_FILE);
    } else {
      console.log('❌ No token captured. Run again and try interacting with the page.');
    }
    await browser.close();
    process.exit(0);
  });
})();