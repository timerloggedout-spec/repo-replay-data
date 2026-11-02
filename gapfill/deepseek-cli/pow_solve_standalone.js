import { solvePow } from './deepseek-cli/deepterm/deepterm-core.js';
// usage: node pow_solve_standalone.js <challenge> <salt> <expire_at> <difficulty>
const args = process.argv.slice(2);
const [challenge, salt, expire_at, difficulty] = args;
solvePow(challenge, salt, expire_at, parseInt(difficulty))
  .then(answer => process.stdout.write(String(answer)))
  .catch(e => { process.stderr.write(e.message); process.exit(1); });