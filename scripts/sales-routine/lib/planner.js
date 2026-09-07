'use strict';
const config = require('../config');

const COL_INDEX = (c) => c.charCodeAt(0) - 65; // 'A' → 0

function toNumber(v) {
  if (v == null || v === '') return null;
  const n = Number(String(v).replace(/,/g, ''));
  return Number.isFinite(n) ? n : null;
}

function isBlank(v) { return v == null || String(v).trim() === ''; }

/**
 * 한 책·한 날짜의 기록 계획.
 * @param book        config.books 항목
 * @param existingRow 시트 행 값 배열(A열부터, 표시값)
 * @param data        { kyobo:{off,on,corp}|null, yes24:number|null, aladin:number|null, ypbooks:number|null }
 * @param opts        { force }
 * @returns { writes:[{col,value}], skipped:[{col,value,reason}] }
 */
function planCells(book, existingRow, data, opts = {}) {
  const C = config.columns;
  const candidates = [];
  if (data.kyobo) {
    candidates.push([C.kyoboOff, data.kyobo.off, 'kyobo']);
    candidates.push([C.kyoboOn, data.kyobo.on, 'kyobo']);
    candidates.push([C.kyoboCorp, data.kyobo.corp, 'kyobo']);
  }
  if (data.yes24 != null) candidates.push([C.yes24, data.yes24, 'yes24']);
  if (data.aladin != null) candidates.push([C.aladin, data.aladin, 'aladin']);
  if (data.ypbooks != null) {
    if (book.layout === 'new') candidates.push([C.ypbooks, data.ypbooks, 'ypbooks']);
    // old 레이아웃은 H가 총계 수식이므로 영풍 값을 버린다.
  }

  const writes = [], skipped = [];
  for (const [col, raw, portal] of candidates) {
    const value = toNumber(raw);
    if (value == null || value === 0) { skipped.push({ col, portal, value, reason: 'zero' }); continue; }
    const cur = existingRow ? existingRow[COL_INDEX(col)] : undefined;
    if (!isBlank(cur) && !opts.force) {
      if (toNumber(cur) === value) skipped.push({ col, portal, value, reason: 'same' });
      else skipped.push({ col, portal, value, current: cur, reason: 'exists' });
      continue;
    }
    writes.push({ col, portal, value });
  }
  return { writes, skipped };
}

module.exports = { planCells, toNumber, isBlank, COL_INDEX };
