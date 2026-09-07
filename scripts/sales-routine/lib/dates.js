'use strict';
const KO_DOW = ['일', '월', '화', '수', '목', '금', '토'];

function pad(n) { return String(n).padStart(2, '0'); }

/** 'YYYY-MM-DD' → Date (로컬 자정). Date 입력이면 복사. */
function parseDate(s) {
  if (s instanceof Date) return new Date(s.getFullYear(), s.getMonth(), s.getDate());
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(s).trim());
  if (!m) throw new Error(`날짜 형식 오류(YYYY-MM-DD 필요): ${s}`);
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
}

function addDays(d, n) { const r = parseDate(d); r.setDate(r.getDate() + n); return r; }
function today() { return parseDate(new Date()); }
function yesterday() { return addDays(today(), -1); }

function iso(d) { return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; }
function compact(d) { return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`; }

/** 시트 A열 표기: '26.09.06(일)' */
function sheetLabel(d) {
  return `${String(d.getFullYear()).slice(2)}.${pad(d.getMonth() + 1)}.${pad(d.getDate())}(${KO_DOW[d.getDay()]})`;
}
/** 요일을 뺀 접두 '26.09.06' — A열 값이 날짜 서식이든 문자열이든 이 접두로 매칭한다. */
function sheetPrefix(d) {
  return `${String(d.getFullYear()).slice(2)}.${pad(d.getMonth() + 1)}.${pad(d.getDate())}`;
}

/** A열 표시값이 해당 날짜인지 판정. '26.09.06(일)', '26.09.06', '2026-09-06', '2026. 9. 6' 등 허용. */
function cellMatchesDate(cellText, d) {
  if (cellText == null) return false;
  const t = String(cellText).trim();
  if (!t) return false;
  if (t.startsWith(sheetPrefix(d))) return true;
  const m = /^(\d{4})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})/.exec(t);
  if (m) return Number(m[1]) === d.getFullYear() && Number(m[2]) === d.getMonth() + 1 && Number(m[3]) === d.getDate();
  return false;
}

function range(from, to) {
  const out = [];
  for (let d = parseDate(from); d <= parseDate(to); d = addDays(d, 1)) out.push(d);
  return out;
}

module.exports = { parseDate, addDays, today, yesterday, iso, compact, sheetLabel, sheetPrefix, cellMatchesDate, range, KO_DOW };
