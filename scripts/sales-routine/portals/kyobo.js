'use strict';
const config = require('../config');
const { compact } = require('../lib/dates');
const { looksLikeLogin, sleep, dumpDebug } = require('../lib/browser');

/**
 * 교보 SCM(WebSquare): 기간 설정 → 조회 두 번(첫 클릭은 이전 결과가 남음) → 표 파싱.
 * 하루 늦게 집계됨. 미집계면 0으로 나오므로 planner가 건너뛰고 다음날 백필된다.
 * @returns Map<isbn|title, {off,on,corp}>
 */
async function fetchKyobo(page, date, { debug } = {}) {
  await page.goto(config.portals.kyobo.page, { waitUntil: 'domcontentloaded' });
  if (await looksLikeLogin(page)) throw new Error('kyobo: 로그인 필요');
  await page.waitForFunction(() => window.$w && $w.getComponentById && $w.getComponentById('btn_search'), null, { timeout: 20000 });
  const ymd = compact(date);
  for (let i = 0; i < 2; i++) {
    await page.evaluate((ymd) => {
      $w.getComponentById('sel_strDateFrom').setValue(ymd);
      $w.getComponentById('sel_strDateTo').setValue(ymd);
      $w.getComponentById('btn_search').click();
    }, ymd);
    await sleep(3000);
  }
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
  const rows = await page.evaluate(() =>
    [...document.querySelectorAll('tr')].map((tr) => [...tr.querySelectorAll('td,th')].map((c) => c.innerText.trim())).filter((r) => r.length > 2));
  if (debug) await dumpDebug(page, 'kyobo');
  return parseKyoboRows(rows);
}

/**
 * 헤더 행(영업점/온라인/인터파크/법인 포함)에서 열 위치를 잡고, ISBN 또는 도서명 셀이 있는 행을 읽는다.
 * 인터파크는 항상 0이라 무시.
 */
function parseKyoboRows(rows) {
  const out = new Map();
  let idx = null;
  const num = (s) => { const n = Number(String(s ?? '').replace(/,/g, '')); return Number.isFinite(n) ? n : 0; };
  for (const cells of rows) {
    if (!idx) {
      const off = cells.findIndex((c) => /영업점/.test(c));
      const on = cells.findIndex((c) => /온라인/.test(c));
      const corp = cells.findIndex((c) => /법인/.test(c));
      if (off >= 0 && on >= 0 && corp >= 0) {
        idx = { off, on, corp, isbn: cells.findIndex((c) => /isbn|바코드/i.test(c)), title: cells.findIndex((c) => /도서명|상품명|서명/.test(c)) };
      }
      continue;
    }
    if (cells.some((c) => /^(합계|총계|계)$/.test(c))) continue;
    const rec = { off: num(cells[idx.off]), on: num(cells[idx.on]), corp: num(cells[idx.corp]) };
    const isbnCell = idx.isbn >= 0 ? cells[idx.isbn] : cells.find((c) => /^\d{13}$/.test(c.replace(/\D/g, '')));
    const isbn = isbnCell ? isbnCell.replace(/\D/g, '') : '';
    if (isbn.length === 13) out.set(isbn, rec);
    const title = idx.title >= 0 ? cells[idx.title] : null;
    if (title) out.set(`title:${title}`, rec);
  }
  return out;
}

/** ISBN 우선, 없으면 aliases로 도서명 매칭 */
function lookupKyobo(map, book) {
  if (map.has(book.isbn)) return map.get(book.isbn);
  for (const [k, v] of map) {
    if (!k.startsWith('title:')) continue;
    const t = k.slice(6).replace(/\s+/g, '');
    if (book.aliases.some((a) => t.includes(a.replace(/\s+/g, '')))) return v;
  }
  return null;
}

module.exports = { fetchKyobo, parseKyoboRows, lookupKyobo };
