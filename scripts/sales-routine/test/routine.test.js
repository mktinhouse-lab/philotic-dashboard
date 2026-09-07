'use strict';
const test = require('node:test');
const assert = require('node:assert');
const dates = require('../lib/dates');
const { planCells } = require('../lib/planner');
const { SheetClient } = require('../lib/sheet');
const { parseYes24 } = require('../portals/yes24');
const { parseAladinRows } = require('../portals/aladin');
const { parseKyoboRows, lookupKyobo } = require('../portals/kyobo');
const { parseYpRows } = require('../portals/ypbooks');
const config = require('../config');

const book = (name) => config.books.find((b) => b.name === name);

test('dates: label/prefix/compact', () => {
  const d = dates.parseDate('2026-09-06');
  assert.equal(dates.sheetLabel(d), '26.09.06(일)');
  assert.equal(dates.sheetLabel(dates.parseDate('2026-09-01')), '26.09.01(화)');
  assert.equal(dates.compact(d), '20260906');
  assert.equal(dates.iso(d), '2026-09-06');
  assert.ok(dates.cellMatchesDate('26.09.06(일)', d));
  assert.ok(dates.cellMatchesDate('2026. 9. 6', d));
  assert.ok(!dates.cellMatchesDate('26.09.07(월)', d));
  assert.ok(!dates.cellMatchesDate('', d));
  assert.equal(dates.range('2026-09-04', '2026-09-06').length, 3);
});

test('planner: skips zero, keeps existing, old layout drops ypbooks', () => {
  const data = { kyobo: { off: 21, on: 48, corp: 0 }, yes24: 20, aladin: 21, ypbooks: 2 };
  const p = planCells(book('칼융'), ['26.09.06(일)', '', '', '', '', '', '', '', ''], data);
  assert.deepEqual(p.writes.map((w) => `${w.col}=${w.value}`), ['B=21', 'C=48', 'F=20', 'G=21', 'H=2']);
  assert.ok(p.skipped.some((s) => s.col === 'D' && s.reason === 'zero'));

  const old = planCells(book('세네카'), [], data);
  assert.ok(!old.writes.some((w) => w.col === 'H'));

  const keep = planCells(book('강풍'), ['x', '5', '', '', '', '20', '', '', ''], data);
  assert.ok(!keep.writes.some((w) => w.col === 'B'));
  assert.ok(keep.skipped.some((s) => s.col === 'B' && s.reason === 'exists'));
  assert.ok(keep.skipped.some((s) => s.col === 'F' && s.reason === 'same'));
  const forced = planCells(book('강풍'), ['x', '5'], data, { force: true });
  assert.ok(forced.writes.some((w) => w.col === 'B' && w.value === 21));

  const neg = planCells(book('강풍'), [], { kyobo: { off: 0, on: 0, corp: -1 } });
  assert.deepEqual(neg.writes, [{ col: 'D', portal: 'kyobo', value: -1 }]);
});

test('yes24 parser', () => {
  const m = parseYes24({ RESULT_LIST: [{ EAN2: '9791199903432', ORD_CNT: 20, GOODS_NM: '칼 융' }, { EAN2: '123', ORD_CNT: 5 }] });
  assert.equal(m.get('9791199903432'), 20);
  assert.equal(m.size, 1);
});

test('aladin parser: header-based and total row excluded', () => {
  const rows = [
    ['도서명', 'ISBN', '판매권수'],
    ['필로틱출판 총계', '', '42'],
    ['칼 융', '9791199903432', '21'],
    ['강풍', '9791199383043', '1,003'],
  ];
  const m = parseAladinRows(rows);
  assert.equal(m.get('9791199903432'), 21);
  assert.equal(m.get('9791199383043'), 1003);
  assert.equal(m.size, 2);
  // 헤더가 없어도 ISBN 셀 뒤 첫 숫자를 잡는다
  const m2 = parseAladinRows([['칼 융', '9791199903432', '7']]);
  assert.equal(m2.get('9791199903432'), 7);
});

test('kyobo parser: column positions from header, title fallback', () => {
  const rows = [
    ['순번', '상품명', 'ISBN', '영업점', '온라인', '인터파크', '법인', '합계'],
    ['1', '칼 융, 무의식의 발견', '9791199903432', '21', '48', '0', '30', '99'],
    ['2', '상향혼', '', '3', '1', '0', '', '4'],
    ['', '합계', '', '24', '49', '0', '30', '103'],
  ];
  const m = parseKyoboRows(rows);
  assert.deepEqual(lookupKyobo(m, book('칼융')), { off: 21, on: 48, corp: 30 });
  assert.deepEqual(lookupKyobo(m, book('상향혼')), { off: 3, on: 1, corp: 0 });
  assert.equal(lookupKyobo(m, book('세네카')), null);
});

test('ypbooks parser', () => {
  const m = parseYpRows([['1', '9791199903432', 'a', 'b', 'c', 'd', 'e', '2'], ['x'], ['2', '9791199903432', '', '', '', '', '', '3']]);
  assert.equal(m.get('9791199903432'), 5);
});

test('sheet client: resolves gid → title, finds row by date, batch writes', async () => {
  const calls = [];
  const fake = {
    spreadsheets: {
      get: async () => ({ data: { sheets: [{ properties: { sheetId: 945888298, title: '칼융 25.09' } }] } }),
      values: {
        get: async ({ range }) => {
          calls.push(range);
          if (range.endsWith('!A1:A3000')) return { data: { values: [['첫번째 칸만 수정'], ['26.09.05(토)'], ['26.09.06(일)'], ['26.09.07(월)']] } };
          return { data: { values: [['26.09.06(일)', '', '', '', '0', '20']] } };
        },
        batchUpdate: async ({ requestBody }) => { calls.push(requestBody); return {}; },
      },
    },
  };
  const s = await new SheetClient('sid', { sheetsApi: fake }).init();
  const title = s.titleForGid(945888298);
  assert.equal(title, '칼융 25.09');
  assert.equal(await s.findRow(title, dates.parseDate('2026-09-06')), 3);
  assert.equal(await s.findRow(title, dates.parseDate('2026-09-09')), null);
  const row = await s.readRow(title, 3);
  assert.equal(row[5], '20');
  await s.writeCells([{ title, row: 3, col: 'F', value: 20 }, { title, row: 3, col: 'G', value: 21 }]);
  const body = calls[calls.length - 1];
  assert.equal(body.valueInputOption, 'RAW');
  assert.deepEqual(body.data.map((d) => d.range), ["'칼융 25.09'!F3", "'칼융 25.09'!G3"]);
  assert.throws(() => s.titleForGid(1));
});
