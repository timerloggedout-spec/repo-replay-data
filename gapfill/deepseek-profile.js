const puppeteer = require('puppeteer');
const fs = require('fs');
const CHROMIUM_PATH = '/data/data/com.termux/files/usr/bin/chromium-browser';
const DEEPSEEK_BASE = 'https://chat.deepseek.com/';
const INPUT_SEL = 'textarea[placeholder="Message DeepSeek"]';
const EXPERT_RADIO_SEL = 'div[data-model-type="expert"][role="radio"]';
const STOP_BUTTON_SEL = 'button[aria-label="Stop generating"]';
const MSG_SEL = 'div.ds-message[data-role="assistant"] .ds-markdown';
const wait = ms => new Promise(r => setTimeout(r, ms));

function parseArgs(argv) {
  const args = { prompt: '', newChat: false, session: null };
  const filtered = [];
  for (let i = 2; i < argv.length; i++) {
    if (argv[i] === '--new-chat') args.newChat = true;
    else if (argv[i] === '--session' && argv[i + 1]) {
      args.session = argv[i + 1];
      i++;
    } else filtered.push(argv[i]);
  }
  args.prompt = filtered.join(' ').trim();
  return args;
}

(async () => {
  const { prompt, newChat, session } = parseArgs(process.argv);
  if (!prompt) {
    console.error('Usage: node deepseek-profile.js [--new-chat] [--session <ID>] "Your prompt"');
    process.exit(1);
  }

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: CHROMIUM_PATH,
    userDataDir: './browser-data',   // use the manually authenticated profile
    args: ['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage','--disable-gpu'],
  });

  const page = await browser.newPage();
  try {
    const targetUrl = session ? `${DEEPSEEK_BASE}a/chat/s/${session}` : DEEPSEEK_BASE;
    await page.goto(targetUrl, { waitUntil: 'networkidle2', timeout: 30000 });
    await wait(2000);

    if (page.url().includes('/sign_in')) {
      console.error('❌ Not authenticated. Run manual login again.');
      process.exit(1);
    }

    await page.waitForSelector(INPUT_SEL, { timeout: 10000 });
    console.log('✅ Authenticated.');

    // Expert mode
    const expertRadio = await page.$(EXPERT_RADIO_SEL);
    if (expertRadio) {
      const checked = await page.evaluate(el => el.getAttribute('aria-checked'), expertRadio);
      if (checked !== 'true') {
        await expertRadio.click();
        await wait(800);
      }
    }

    if (newChat && !session) {
      const btn = await page.$('button[aria-label="New chat"]');
      if (btn) { await btn.click(); await wait(1500); }
    }

    const input = await page.$(INPUT_SEL);
    await input.click();
    await page.type(INPUT_SEL, prompt, { delay: 20 });
    await page.keyboard.press('Enter');

    await page.waitForSelector(STOP_BUTTON_SEL, { timeout: 15000 });
    await page.waitForFunction((sel) => !document.querySelector(sel), { timeout: 300000 }, STOP_BUTTON_SEL);

    const reply = await page.evaluate((sel) => {
      const msgs = document.querySelectorAll(sel);
      return msgs.length ? msgs[msgs.length - 1].innerText : '';
    }, MSG_SEL);
    console.log(reply || '⚠️ No reply.');
  } finally {
    await browser.close();
  }
})();