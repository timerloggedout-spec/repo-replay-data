const puppeteer = require('puppeteer');
const CHROMIUM_PATH = '/data/data/com.termux/files/usr/bin/chromium-browser';

(async () => {
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: CHROMIUM_PATH,
    userDataDir: './browser-data',
    args: ['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage','--disable-gpu'],
  });
  const page = await browser.newPage();
  await page.goto('https://chat.deepseek.com/', { waitUntil: 'domcontentloaded', timeout: 30000 });

  // Try localStorage first
  let token = await page.evaluate(() => {
    return localStorage.getItem('userToken') || localStorage.getItem('chat_token') || '';
  });

  if (!token) {
    // Intercept network requests for the Authorization header
    console.log('localStorage token not found, capturing from network...');
    let authHeader = null;
    page.on('request', req => {
      if (req.url().includes('/api/v0/') && req.headers()['authorization']) {
        authHeader = req.headers()['authorization'];
      }
    });
    // Reload to trigger API calls
    await page.reload({ waitUntil: 'networkidle2', timeout: 30000 });
    await page.waitForTimeout(1000);
    token = authHeader;
  }

  console.log(token || 'Token not found. Inspect localStorage manually.');
  await browser.close();
})();