// Read-only browser checks: preview composes local context and never calls AI.
import { mkdtempSync, readFileSync, existsSync, writeFileSync, rmSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const base = process.env.E2E_BASE_URL || 'http://127.0.0.1:8000';
const chromePath = [process.env.CHROME_PATH, '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome', '/usr/bin/chromium'].filter(Boolean).find(existsSync);
if (!chromePath) throw new Error('Chrome was not found; set CHROME_PATH.');
const projects = await (await fetch(`${base}/api/projects`)).json();
const project = projects.find(item => item.project_id === process.env.E2E_PROJECT_ID) || projects[0];
if (!project) throw new Error('Register a project before running this read-only UI test.');
const profile = mkdtempSync(join(tmpdir(), 'agent-prompt-browser-'));
const chrome = spawn(chromePath, ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--remote-debugging-port=0', `--user-data-dir=${profile}`, '--window-size=1440,1200', 'about:blank'], { stdio: 'ignore' });
let socket;
let sessionId;
let nextId = 0;
const pending = new Map();
const errors = [];
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

async function until(fn, message, timeout = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    if (await fn()) return;
    await delay(100);
  }
  throw new Error(message);
}

function command(method, params = {}, useSession = true) {
  const id = ++nextId;
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timed out: ${method}`)); }, 10000);
    pending.set(id, { resolve, reject, timeout });
    socket.send(JSON.stringify({ id, method, params, ...(useSession && sessionId ? { sessionId } : {}) }));
  });
}

async function evaluate(expression) {
  const result = await command('Runtime.evaluate', { expression, returnByValue: true });
  if (result.exceptionDetails) throw new Error('Page evaluation failed');
  return result.result.value;
}

try {
  await until(() => existsSync(join(profile, 'DevToolsActivePort')), 'Chrome did not start');
  const [port, path] = readFileSync(join(profile, 'DevToolsActivePort'), 'utf8').trim().split('\n');
  socket = new WebSocket(`ws://127.0.0.1:${port}${path}`);
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  socket.onmessage = event => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const holder = pending.get(message.id);
      pending.delete(message.id);
      clearTimeout(holder.timeout);
      if (message.error) holder.reject(new Error(message.error.message));
      else holder.resolve(message.result);
    }
    if (message.method === 'Runtime.exceptionThrown') errors.push('Uncaught browser exception');
  };
  const target = await command('Target.createTarget', { url: 'about:blank' }, false);
  const attached = await command('Target.attachToTarget', { targetId: target.targetId, flatten: true }, false);
  sessionId = attached.sessionId;
  await command('Runtime.enable');
  await command('Page.enable');
  await command('Page.navigate', { url: `${base}/#/project/${encodeURIComponent(project.project_id)}/mission-hub` });
  await until(() => evaluate(`Boolean(document.querySelector('section[aria-label="ทำงานต่อจาก checkpoint"]'))`), 'Recovery card missing in Mission Hub');
  if (!await evaluate(`document.querySelector('section[aria-label="ทำงานต่อจาก checkpoint"]').textContent.includes('30 ไฟล์')`)) throw new Error('Checkpoint file count missing');
  await evaluate(`(() => {
    const originalFetch = window.fetch;
    window.fetch = (input, options) => String(input).endsWith('/retry')
      ? Promise.resolve(new Response(JSON.stringify({detail: 'Resume test rejection'}), {status: 409, headers: {'Content-Type': 'application/json'}}))
      : originalFetch(input, options);
    document.querySelector('section[aria-label="ทำงานต่อจาก checkpoint"] button').click();
  })()`);
  await until(() => evaluate(`document.body.textContent.includes('Resume test rejection')`), 'Resume failure feedback missing');
  if (await evaluate(`document.querySelector('section[aria-label="ทำงานต่อจาก checkpoint"] button').disabled`)) throw new Error('Resume button did not recover after failure');
  if (errors.length) throw new Error(errors.join('; '));
  console.log('Recovery UI passed: Mission Hub card, file count, Resume failure feedback and retry. Resume request intercepted; no AI calls.');
} finally {
  if (socket) socket.close();
  chrome.kill('SIGTERM');
  await Promise.race([new Promise(resolve => chrome.once('exit', resolve)), delay(2000)]);
  if (chrome.exitCode === null) chrome.kill('SIGKILL');
  await delay(100);
  rmSync(profile, { recursive: true, force: true });
}
