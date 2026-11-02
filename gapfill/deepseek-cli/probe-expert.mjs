import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const fs = require('fs');

// Use the same token and session as deepcli
import { execSync } from 'child_process';
const token = execSync('python3 -c "import sys; sys.path.insert(0,\'/data/data/com.termux/files/home/deepcli\'); from deepcli.core import get_token; print(get_token())"').toString().trim();

const BASE_URL = 'https://chat.deepseek.com';
const API = `${BASE_URL}/api/v0/chat/completion`;

// Create session
const createRes = await fetch(`${BASE_URL}/api/v0/chat_session/create`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
    'X-Client-Platform': 'web',
    'X-Client-Version': '1.4.0',
    'X-App-Version': '20250521.1',
    'X-Client-Locale': 'en_US',
    'Origin': BASE_URL,
    'Referer': `${BASE_URL}/`,
  },
  body: JSON.stringify({ character_id: null, model_type: 'expert' })
});
const session = await createRes.json();
const sessionId = session.data.biz_data.id;
console.log('Session:', sessionId);

// Send a prompt with Expert model_type
const payload = {
  chat_session_id: sessionId,
  prompt: 'Say "expert works"',
  ref_file_ids: [],
  stream: true,
  model_type: 'expert'
};
const resp = await fetch(API, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
    'Accept': 'text/event-stream',
    'X-Client-Version': '1.4.0',
    'X-App-Version': '20250521.1',
    'X-Client-Platform': 'web',
    'X-Client-Locale': 'en_US',
    'Origin': BASE_URL,
    'Referer': `${BASE_URL}/`,
  },
  body: JSON.stringify(payload)
});

console.log('Status:', resp.status);
for await (const chunk of resp.body) {
  const lines = new TextDecoder().decode(chunk).split('\n');
  for (const line of lines) {
    if (line.startsWith('data:')) {
      try {
        const data = JSON.parse(line.slice(5).trim());
        if (data.v) process.stdout.write(data.v);
        if (data.content) process.stdout.write(data.content);
      } catch(e) {}
    }
  }
}
console.log();