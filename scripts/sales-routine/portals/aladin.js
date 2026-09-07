'use strict';
const config = require('../config');
const { looksLikeLogin, sleep, dumpDebug } = require('../lib/browser');

/**
 * 알라딘 공급자: 기간 select 설정 → cmdGetStat 클릭 → 표 파싱. '하루 전까지' 제공.
 * @returns Map<isbn, number>  (판매권수)
 */
async function fetchAladin(page, date, { debug } = {}) {
  await page.goto(config.portals.aladin.page, { waitUntil: 'domcontentloaded' });
  if (await looksLikeLogin(page)) throw new Error('aladin: 로그인 필요');
  const y = date.getFullYear(), m = date.getMonth() + 1, d = date.getDate();
  await page.evaluate(({ y, m, d }) => {
    const pick = (id, n) => {
      const sel = document.getElementById(id);
      if (!sel) throw new Error(`select 없음: ${id}`);
      const opt = [...sel.options].find((o) => parseInt(o.value, 10) === n) || [...sel.options].find((o) => parseInt(o.text, 10) === n);
      if (!opt) throw new Error(`${id}에 ${n} 옵션 없음`);
      sel.value = opt.value;
      sel.dispatchEvent(new Event('change', { bubbles: true }));
    };
    pick('cboStartYear', y); pick('cboStartMonth', m); pick('cboStartDay', d);
    pick('cboEndYear', y); pick('cboEndMonth', m); pick('cboEndDay', d);
    document.getElementById('cmdGetStat').click();
  }, { y, m, d });
  await sleep(3500);
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
  const rows = await page.evaluate(() =>
    [...document.querySelectorAll('table tr')].map((tr) => [...tr.querySelectorAll('td,th')].map((c) => c.innerText.trim())));
  if (debug) await dumpDebug(page, 'aladin');
  return parseAladinRows(rows);
}

/** rows: 셀 문자열 배열의 배열. 헤더에서 'ISBN'·'판매권수' 열 위치를 찾고, 총계행은 제외. */
function parseAladinRows(rows) {
  const out = new Map();
  let isbnIdx = -1, qtyIdx = -1;
  for (const cells of rows) {
    if (isbnIdx < 0) {
      const i = cells.findIndex((c) => /isbn/i.test(c));
      const q = cells.findIndex((c) => /판매권수|판매수량|판매부수/.test(c));
      if (i >= 0 && q >= 0) { isbnIdx = i; qtyIdx = q; continue; }
    }
    if (cells.some((c) => /총계|합계/.test(c))) continue;
    let isbn, qty;
    if (isbnIdx >= 0 && cells[isbnIdx]) {
      isbn = cells[isbnIdx].replace(/\D/g, '');
      qty = Number(String(cells[qtyIdx] || '').replace(/,/g, ''));
    } else {
      const i = cells.findIndex((c) => /^\d{13}$/.test(c.replace(/\D/g, '')) && c.replace(/\D/g, '').length === 13);
      if (i < 0) continue;
      isbn = cells[i].replace(/\D/g, '');
      const nums = cells.slice(i + 1).map((c) => Number(c.replace(/,/g, ''))).filter((n) => Number.isFinite(n));
      qty = nums[0];
    }
    if (!isbn || isbn.length !== 13 || !Number.isFinite(qty)) continue;
    out.set(isbn, (out.get(isbn) || 0) + qty);
  }
  return out;
}

module.exports = { fetchAladin, parseAladinRows };
