const crypto = require('crypto');
const challenge = process.argv[2]; // 64 hex chars
const salt = process.argv[3];      // hex
const expectedAnswer = parseInt(process.argv[4]);
const signature = process.argv[5]; // hex

function testHash() {
  for (let nonce = 0; nonce <= expectedAnswer + 10; nonce++) {
    const input = challenge + salt + nonce;
    const hash = crypto.createHash('sha256').update(input, 'hex').digest('hex');
    if (nonce === expectedAnswer) {
      console.log(`Nonce ${nonce} -> ${hash}`);
      console.log(`Matches signature? ${hash === signature}`);
    }
  }
}
testHash();