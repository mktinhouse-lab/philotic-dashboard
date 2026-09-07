'use strict';
const config = require('../config');
const { iso } = require('../lib/dates');
const { looksLikeLogin } = require('../lib/browser');

/**
 * 예스24 SCM: 판매분석 API 직접 호출(T+1 제공).
 * @returns Map<isbn, number>  (ORD_CNT)
 */
async function fetchYes24(page, date) {
  await page.goto(config.portals.yes24.page, { waitUntil: 'domcontentloaded' });
  if (await looksLikeLogin(page)) throw new Error('yes24: 로그인 필요');
  const day = iso(date);
  const body = {
    START_DATE: day, END_DATE: day, GOODS_TYPE: 'GOODS_NM', GOODS_VALUE: '', STATE_CODE: '', MK_ENTR_NO: 0,
    GOODS_SORT_NO: '', PAGE: 1, COUNT: 100, ORDER_TARGET: 'ORD_CNT', ORDER_TYPE: 'DESC',
  };
  const json = await page.evaluate(async ({ api, body }) => {
    const r = await fetch(api, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }, { api: config.portals.yes24.api, body });
  return parseYes24(json);
}

function parseYes24(json) {
  const list = (json && (json.RESULT_LIST || json.resultList || json.data)) || [];
  const out = new Map();
  for (const row of list) {
    const isbn = String(row.EAN2 || row.ean2 || row.ISBN || '').replace(/\D/g, '');
    if (isbn.length !== 13) continue;
    const qty = Number(row.ORD_CNT ?? row.ord_cnt ?? 0);
    out.set(isbn, (out.get(isbn) || 0) + (Number.isFinite(qty) ? qty : 0));
  }
  return out;
}

module.exports = { fetchYes24, parseYes24 };
