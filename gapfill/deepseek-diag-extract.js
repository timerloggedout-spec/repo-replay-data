const puppeteer = require('puppeteer');
const CHROMIUM_PATH = '/data/data/com.termux/files/usr/bin/chromium-browser';
const INPUT_SEL = 'textarea[placeholder="Message DeepSeek"]';
const SEND_BTN_CLASS = '_52c986b';
const wait = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const prompt = process.argv.slice(2).join(' ') || 'Diagnostic: just reply "OK"';
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: CHROMIUM_PATH,
    userDataDir: './browser-data',
    args: ['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage','--disable-gpu'],
  });
  const page = await browser.newPage();
  try {
    await page.goto('https://chat.deepseek.com/', { waitUntil: 'networkidle2', timeout: 30000 });
    await wait(2000);
    if (page.url().includes('/sign_in')) { console.log('❌ Auth failed.'); return; }
    await page.waitForSelector(INPUT_SEL, { timeout: 10000 });
    console.log('✅ Authenticated.');

    // Expert mode
    const expertRadio = await page.$('div[data-model-type="expert"][role="radio"]');
    if (expertRadio) {
      const checked = await page.evaluate(el => el.getAttribute('aria-checked'), expertRadio);
      if (checked !== 'true') { await expertRadio.click(); await wait(800); }
    }

    // Type prompt
    const input = await page.$(INPUT_SEL);
    await input.click();
    await page.$eval(INPUT_SEL, (el, value) => {
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
      nativeInputValueSetter.call(el, value);
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }, prompt);
    console.log('⌨️ Prompt injected.');

    // Wait for send button to enable and click
    await wait(800);
    await page.waitForFunction(
      (sel) => {
        const btn = document.querySelector(sel);
        return btn && btn.getAttribute('aria-disabled') !== 'true';
      },
      { timeout: 10000 },
      `.${SEND_BTN_CLASS}`
    );
    const sendBtn = await page.$(`.${SEND_BTN_CLASS}`);
    await sendBtn.click();
    console.log('📤 Message sent.');

    // Wait 15 seconds for reply to appear
    await wait(15000);

    // Save full HTML
    const html = await page.content();
    require('fs').writeFileSync('page-after-send.html', html);
    console.log('📄 page-after-send.html saved (first 2000 chars):');
    console.log(html.substring(0, 2000));

    // Also print all elements with data-role="assistant"
    const assistantEls = await page.$$eval('div[data-role="assistant"]', els => els.map(el => ({
      innerHTML: el.innerHTML.substring(0, 300),
      textContent: el.textContent.substring(0, 300),
      className: el.className
    })));
    console.log('\n📦 Assistant message elements:', JSON.stringify(assistantEls, null, 2));

  } catch (e) {
    console.error(e);
  } finally {
    await browser.close();
  }
})();