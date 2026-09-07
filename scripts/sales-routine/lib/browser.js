'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const { chromium } = require('playwright');

const PROFILE_DIR = process.env.PILOTIC_PROFILE_DIR || path.join(__dirname, '..', 'profile');
const DEBUG_DIR = path.join(__dirname, '..', 'debug');

/** 로그인 세션이 남는 영구 프로필로 크로미움 실행 */
async function launch({ headed = false } = {}) {
  fs.mkdirSync(PROFILE_DIR, { recursive: true });
  const opts = {
    headless: !headed,
    viewport: { width: 1440, height: 900 },
    locale: 'ko-KR',
    timezoneId: 'Asia/Seoul',
    args: ['--disable-blink-features=AutomationControlled'],
  };
  if (process.env.PILOTIC_CHROME_PATH) opts.executablePath = process.env.PILOTIC_CHROME_PATH;
  return chromium.launchPersistentContext(PROFILE_DIR, opts);
}

/** 로그인 페이지로 튕겼는지 판정 */
async function looksLikeLogin(page) {
  const url = page.url().toLowerCase();
  if (/login|signin|logon|member\/?$/.test(url)) return true;
  const pw = await page.$('input[type="password"]');
  return !!pw;
}

async function waitForEnter(msg) {
  process.stdout.write(`${msg}\n  → 완료 후 이 터미널에서 Enter: `);
  await new Promise((resolve) => {
    process.stdin.resume();
    process.stdin.once('data', () => { process.stdin.pause(); resolve(); });
  });
}

async function dumpDebug(page, name) {
  fs.mkdirSync(DEBUG_DIR, { recursive: true });
  const base = path.join(DEBUG_DIR, `${name}-${Date.now()}`);
  try { fs.writeFileSync(`${base}.txt`, await page.evaluate(() => document.body.innerText)); } catch {}
  try { fs.writeFileSync(`${base}.html`, await page.content()); } catch {}
  try { await page.screenshot({ path: `${base}.png`, fullPage: true }); } catch {}
  return base;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

module.exports = { launch, looksLikeLogin, waitForEnter, dumpDebug, sleep, PROFILE_DIR, DEBUG_DIR, homedir: os.homedir };
