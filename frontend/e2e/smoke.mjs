import { existsSync, mkdirSync, rmSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { join, resolve } from 'node:path';

const baseUrl = process.env.E2E_BASE_URL || 'http://127.0.0.1:8000';
const candidates = [
  process.env.CHROME_PATH,
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
].filter(Boolean);
const chrome = candidates.find(existsSync);
if (!chrome) throw new Error('Chrome was not found. Set CHROME_PATH to run visual smoke tests.');

const response = await fetch(baseUrl);
if (!response.ok) throw new Error(`Dashboard returned HTTP ${response.status}`);

const outputDir = resolve('test-results');
const profileDir = join(outputDir, 'chrome-profile');
mkdirSync(outputDir, { recursive: true });
rmSync(profileDir, { recursive: true, force: true });

const common = [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  `--user-data-dir=${profileDir}`, '--virtual-time-budget=5000', '--window-size=1440,1000',
];
const domRun = spawnSync(chrome, [...common, '--dump-dom', baseUrl], { encoding: 'utf8', timeout: 30000 });
if (domRun.status !== 0) throw new Error(domRun.stderr || 'Chrome DOM smoke test failed');
for (const marker of ['Antigravity PM Workspace', 'Office Floor', 'สั่งสร้างงาน']) {
  if (!domRun.stdout.includes(marker)) throw new Error(`Rendered dashboard is missing: ${marker}`);
}

const screenshot = join(outputDir, 'dashboard.png');
const shotRun = spawnSync(chrome, [...common, `--screenshot=${screenshot}`, baseUrl], { encoding: 'utf8', timeout: 30000 });
if (shotRun.status !== 0 || !existsSync(screenshot)) throw new Error(shotRun.stderr || 'Screenshot capture failed');
console.log(`E2E smoke passed. Visual artifact: ${screenshot}`);
