const WebSocket = require('ws');

const WS_URL = 'ws://localhost:9222/devtools/browser';
const DOMAIN = 'chat.deepseek.com';

async function getCookies() {
  // List all open pages
  const pages = await fetch('http://localhost:9222/json').then(r => r.json());
  // Pick the first page (or let user pick)
  const target = pages[0];
  if (!target) {
    console.error('No pages open in Chrome. Open chat.deepseek.com first.');
    process.exit(1);
  }

  const ws = new WebSocket(target.webSocketDebuggerUrl);
  ws.on('open', () => {
    ws.send(JSON.stringify({
      id: 1,
      method: 'Storage.getCookies',
      params: { domain: DOMAIN }
    }));
  });

  ws.on('message', data => {
    const msg = JSON.parse(data);
    if (msg.id === 1 && msg.result) {
      const cookies = msg.result.cookies.map(c => ({
        name: c.name,
        value: c.value,
        domain: c.domain || '.' + DOMAIN,
        path: c.path || '/',
        expires: c.expires,
        httpOnly: c.httpOnly || false,
        secure: c.secure || true,
        sameSite: c.sameSite || 'Lax'
      }));
      fs.writeFileSync('cookies.json', JSON.stringify(cookies, null, 2));
      console.log('cookies.json saved successfully');
      ws.close();
      process.exit(0);
    }
  });

  ws.on('error', err => {
    console.error('WebSocket error:', err);
    process.exit(2);
  });
}

getCookies().catch(console.error);