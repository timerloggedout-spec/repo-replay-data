// Extract Bearer token by loading cookies from a JSON file into headless Chromium
// Usage: node extract_token_from_cookies.js <cookies.json>
const puppeteer = require('puppeteer');
const fs = require('fs');
const COOKIES_FILE = process.argv[2] || 'cookies.json';

(async () => {
  const raw = fs.readFileSync(COOKIES_FILE, 'utf8');
  const data = JSON.parse(raw);
  const cookies = Array.isArray(data) ? data : (data.cookies || []);
  const deepseekCookies = cookies.filter(c => c.domain && c.domain.includes('deepseek.com'));

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/data/data/com.termux/files/usr/bin/chromium-browser',
    args: ['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage','--disable-gpu']
  });
  const page = await browser.newPage();

  // Set cookies before navigation
  await page.setCookie(...deepseekCookies.map(c => ({
    name: c.name,
    value: c.value,
    domain: c.domain,
    path: c.path || '/',
    httpOnly: c.httpOnly || false,
    secure: c.secure || true,
  })));

  let token = null;
  page.on('request', req => {
    if (req.url().includes('/api/v0/')) {
      const auth = req.headers()['authorization'];
      if (auth && auth.startsWith('Bearer ')) {
        token = auth.replace('Bearer ', '');
      }
    }
  });

  await page.goto('https://chat.deepseek.com/', { waitUntil: 'networkidle2', timeout: 30000 });

  if (!token) {
    await page.evaluate(() => fetch('/api/v0/chat_session/fetch_page'));
    await page.waitForTimeout(3000);
  }
  if (!token) {
    token = await page.evaluate(() => localStorage.getItem('userToken'));
  }

  await browser.close();
  if (token) {
    console.log(token);
  } else {
    console.error('No token found');
    process.exit(1);
  }
})();