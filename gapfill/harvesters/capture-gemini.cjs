#!/usr/bin/env node
// Extract Gemini token using existing Google cookies
const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');

const COOKIES_FILE = process.argv[2] || path.join(__dirname, '..', '..', 'deepseek-cli', 'cookies_2.json');
const TOKEN_FILE = process.argv[3] || path.join(__dirname, '..', '..', '.multi-ai-tokens', 'gemini_token.txt');

(async () => {
  const browser = await chromium.launch({ headless: false, args: ['--no-sandbox'] });
  const context = await browser.newContext();
  const page = await context.newPage();

  if (fs.existsSync(COOKIES_FILE)) {
    const cookies = JSON.parse(fs.readFileSync(COOKIES_FILE));
    await context.addCookies(cookies);
  } else {
    console.log('No cookies found at', COOKIES_FILE, '– log in manually.');
  }

  let capturedToken = null;
  page.on('request', req => {
    const auth = req.headers()['authorization'];
    if (auth && auth.startsWith('Bearer ') && !capturedToken) {
      capturedToken = auth.replace('Bearer ', '');
      console.log('🔥 Captured Gemini token!');
    }
  });

  await page.goto('https://gemini.google.com', { waitUntil: 'networkidle' });
  console.log('If not logged in automatically, log in manually, then press Enter...');
  process.stdin.once('data', async () => {
    await page.goto('https://gemini.google.com/app', { waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);

    const cookies = await context.cookies();
    // Save updated cookies (overwrite original if new ones acquired)
    fs.writeFileSync(COOKIES_FILE, JSON.stringify(cookies, null, 2));

    if (capturedToken) {
      fs.writeFileSync(TOKEN_FILE, capturedToken);
      console.log('✅ Token saved to', TOKEN_FILE);
    } else {
      console.log('❌ No token captured. Try sending a prompt in the UI first.');
    }
    await browser.close();
    process.exit(0);
  });
})();