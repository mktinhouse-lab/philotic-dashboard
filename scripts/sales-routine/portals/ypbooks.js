'use strict';
const config = require('../config');
const { looksLikeLogin, sleep, dumpDebug } = require('../lib/browser');

/**
 * 영풍문고 SCM(Kendo): 날짜 설정 → 검색 → .k-grid 행 파싱 (col[1]=ISBN, col[7]=판매수량).
 * 세션 만료가 잦다. 집계가 며칠 지연될 수 있다.
 * @returns Map<isbn, number>
 */
async function fetchYpbooks(page, date, { debug } = {}) {
  await page.goto(config.portals.ypbooks.page, { waitUntil: 'domcontentloaded' });
  if (await looksLikeLogin(page)) throw new Error('ypbooks: 로그인 필요(세션 만료)');
  await page.waitForFunction(() => window.jQuery && jQuery('#FromDate_BB').data('kendoDatePicker'), null, { timeout: 20000 });
  const y = date.getFullYear(), m = date.getMonth() + 1, d = date.getDate();
  await page.evaluate(({ y, m, d }) => {
    jQuery('#FromDate_BB').data('kendoDatePicker').value(new Date(y, m - 1, d));
    jQuery('#ToDate_BB').data('kendoDatePicker').value(new Date(y, m - 1, d));
    jQuery('#FromDate_BB').trigger('change'); jQuery('#ToDate_BB').trigger('change');
  }, { y, m, d });
  const btn = await page.$('button:has-text("검색"), a:has-text("검색"), input[value="검색"], button:has-text("조회"), #btnSearch');
  if (btn) await btn.click();
  else { const { x, y: yy } = config.portals.ypbooks.searchClickFallback; await page.mouse.click(x, yy); }
  await sleep(3000);
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
  const rows = await page.evaluate(() =>
    [...document.querySelectorAll('.k-grid tbody tr')].map((tr) => [...tr.querySelectorAll('td')].map((c) => c.innerText.trim())));
  if (debug) await dumpDebug(page, 'ypbooks');
  return parseYpRows(rows);
}

function parseYpRows(rows) {
  const out = new Map();
  for (const cells of rows) {
    if (cells.length < 8) continue;
    const isbn = String(cells[1] || '').replace(/\D/g, '');
    if (isbn.length !== 13) continue;
    const qty = Number(String(cells[7] || '').replace(/,/g, ''));
    if (!Number.isFinite(qty)) continue;
    out.set(isbn, (out.get(isbn) || 0) + qty);
  }
  return out;
}

module.exports = { fetchYpbooks, parseYpRows };
