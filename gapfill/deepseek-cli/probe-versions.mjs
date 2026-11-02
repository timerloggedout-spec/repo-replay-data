import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const { execSync } = require('child_process');
const token = execSync('python3 -c "import sys; sys.path.insert(0,\'/data/data/com.termux/files/home/deepcli\'); from deepcli.core import get_token; print(get_token())"').toString().trim();

const versions = [
  ['1.3.0-auto-resume', '20241129.1'],
  ['1.4.0', '20250521.1'],
  ['1.5.0', '20250601.1'],
  ['2.0.0', '20260501.1'],
];

async function test(ver, appVer) {
  const createRes = await fetch('https://chat.deepseek.com/api/v0/chat_session/create', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      'X-Client-Version': ver,
      'X-App-Version': appVer,
      'X-Client-Platform': 'web',
      'X-Client-Locale': 'en_US',
      'Origin': 'https://chat.deepseek.com',
      'Referer': 'https://chat.deepseek.com/',
    },
    body: JSON.stringify({ character_id: null, model_type: 'expert' })
  });
  const session = await createRes.json();
  const sid = session?.data?.biz_data?.id;
  if (!sid) return `${ver} ${appVer} -> no session`;
  // Send test prompt
  const res = await fetch('https://chat.deepseek.com/api/v0/chat/completion', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
      'X-Client-Version': ver,
      'X-App-Version': appVer,
      'X-Client-Platform': 'web',
      'X-Client-Locale': 'en_US',
      'Origin': 'https://chat.deepseek.com',
      'Referer': 'https://chat.deepseek.com/',
    },
    body: JSON.stringify({ chat_session_id: sid, prompt: 'hi', stream: true, model_type: 'expert' })
  });
  const reader = res.body.getReader();
  let text = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = new TextDecoder().decode(value);
    const lines = chunk.split('\n');
    for (const line of lines) {
      if (line.startsWith('data:')) {
        try {
          const d = JSON.parse(line.slice(5).trim());
          if (d.v) text += d.v;
        } catch(e) {}
      }
    }
  }
  return `${ver} ${appVer} -> "${text.trim()}"`;
}

for (const [v, a] of versions) {
  console.log(await test(v, a));
}