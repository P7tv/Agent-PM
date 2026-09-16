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
  await command('Page.navigate', { url: `${base}/#/project/${encodeURIComponent(project.project_id)}/skills` });
  await until(() => evaluate(`Boolean(document.querySelector('section[aria-label="Agent identity"] textarea'))`), 'Agent identity editor did not render');
  if (await evaluate(`document.querySelector('section[aria-label="Agent identity"] textarea').value === 'Sprint aborted by PM.'`)) {
    throw new Error('Legacy status text was incorrectly restored as persona');
  }
  await evaluate(`(() => {
    const section = document.querySelector('section[aria-label="Prompt preview"]');
    const select = section.querySelector('select');
    select.value = 'consultation'; select.dispatchEvent(new Event('change', { bubbles: true }));
  })()`);
  await evaluate(`Array.from(document.querySelectorAll('button')).find(button => button.textContent.trim() === 'ดู Prompt และแหล่งข้อมูล').click()`);
  await until(() => evaluate(`document.querySelector('section[aria-label="Prompt preview"]').textContent.includes('โหมด: consultation')`), 'Consultation preview did not load');
  await evaluate(`Array.from(document.querySelectorAll('button')).find(button => button.textContent.trim() === 'ดูประวัติ Prompt ที่ประกอบตอนทำงาน').click()`);
  await until(() => evaluate(`document.querySelector('section[aria-label="Prompt preview"]').textContent.includes('โดยไม่เก็บข้อความ prompt')`), 'Prompt trace history did not render');
  if (!await evaluate(`document.body.textContent.includes('Core Role ถาวร')`)) throw new Error('Core and project rules are not shown separately');
  if (errors.length) throw new Error(errors.join('; '));
  if (process.env.E2E_SCREENSHOT) {
    const screenshot = await command('Page.captureScreenshot', { format: 'png' });
    writeFileSync(process.env.E2E_SCREENSHOT, Buffer.from(screenshot.data, 'base64'));
  }
  console.log('Prompt UI passed: identity, consultation preview, source trace history, separate core rules. No AI calls.');
} finally {
  if (socket) socket.close();
  chrome.kill('SIGTERM');
  await Promise.race([new Promise(resolve => chrome.once('exit', resolve)), delay(2000)]);
  if (chrome.exitCode === null) chrome.kill('SIGKILL');
  await delay(100);
  rmSync(profile, { recursive: true, force: true });
}
