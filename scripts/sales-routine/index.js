#!/usr/bin/env node
'use strict';
/**
 * 필로틱 출판 일별 판매 입력 루틴
 *   node index.js                      # 어제까지 최근 3일, 빈 칸만 채움(교보·영풍 지연분 자동 백필)
 *   node index.js --date 2026-09-06    # 특정 날짜
 *   node index.js --from 2026-09-01 --to 2026-09-06
 *   node index.js --portals yes24,aladin --dry-run
 *   node index.js --login              # 브라우저 띄워서 4개 포털 수동 로그인(세션은 profile/에 저장)
 */
const config = require('./config');
const dates = require('./lib/dates');
const { planCells, COL_INDEX } = require('./lib/planner');
const { SheetClient } = require('./lib/sheet');
const browser = require('./lib/browser');
const { fetchYes24 } = require('./portals/yes24');
const { fetchAladin } = require('./portals/aladin');
const { fetchKyobo, lookupKyobo } = require('./portals/kyobo');
const { fetchYpbooks } = require('./portals/ypbooks');

const ALL_PORTALS = ['yes24', 'aladin', 'kyobo', 'ypbooks'];

function parseArgs(argv) {
  const o = { days: 3, portals: ALL_PORTALS, dryRun: false, force: false, login: false, headed: false, debug: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i], next = () => argv[++i];
    if (a === '--date') { o.from = o.to = next(); }
    else if (a === '--from') o.from = next();
    else if (a === '--to') o.to = next();
    else if (a === '--days') o.days = Number(next());
    else if (a === '--portals') o.portals = next().split(',').map((s) => s.trim()).filter(Boolean);
    else if (a === '--dry-run') o.dryRun = true;
    else if (a === '--force') o.force = true;
    else if (a === '--login') { o.login = true; o.headed = true; }
    else if (a === '--headed') o.headed = true;
    else if (a === '--debug') o.debug = true;
    else if (a === '-h' || a === '--help') { o.help = true; }
    else throw new Error(`알 수 없는 옵션: ${a}`);
  }
  for (const p of o.portals) if (!ALL_PORTALS.includes(p)) throw new Error(`알 수 없는 포털: ${p}`);
  if (o.from && !o.to) o.to = o.from;
  if (!o.from) { const y = dates.yesterday(); o.to = dates.iso(y); o.from = dates.iso(dates.addDays(y, -(o.days - 1))); }
  return o;
}

async function doLogin(ctx) {
  const page = await ctx.newPage();
  for (const [name, p] of Object.entries(config.portals)) {
    if (name === 'booxen') continue;
    await page.goto(p.page, { waitUntil: 'domcontentloaded' }).catch(() => {});
    await browser.waitForEnter(`[${name}] 브라우저에서 라이프해킹 계정으로 로그인하세요 (${p.page})`);
  }
  console.log(`로그인 세션 저장됨: ${browser.PROFILE_DIR}`);
}

async function collect(page, portals, date, opts) {
  const out = { errors: {} };
  const tasks = {
    yes24: () => fetchYes24(page, date),
    aladin: () => fetchAladin(page, date, opts),
    kyobo: () => fetchKyobo(page, date, opts),
    ypbooks: () => fetchYpbooks(page, date, opts),
  };
  for (const p of portals) {
    try { out[p] = await tasks[p](); }
    catch (e) {
      out.errors[p] = e.message;
      if (opts.debug) await browser.dumpDebug(page, `${p}-error`).catch(() => {});
    }
  }
  return out;
}

function pick(map, book) { return map && map.has(book.isbn) ? map.get(book.isbn) : null; }

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (opts.help) { console.log(require('fs').readFileSync(__filename, 'utf8').split('\n').slice(2, 10).join('\n')); return; }

  const ctx = await browser.launch({ headed: opts.headed });
  try {
    if (opts.login) { await doLogin(ctx); return; }

    const sheet = await new SheetClient(config.spreadsheetId).init();
    const page = await ctx.newPage();
    const report = [];

    for (const date of dates.range(opts.from, opts.to)) {
      const label = dates.sheetLabel(date);
      console.log(`\n=== ${label} ===`);
      const data = await collect(page, opts.portals, date, opts);
      for (const [p, msg] of Object.entries(data.errors)) console.log(`  ! ${p}: ${msg}`);

      const writes = [];
      for (const book of config.books) {
        const title = sheet.titleForGid(book.gid);
        const row = await sheet.findRow(title, date);
        if (!row) { console.log(`  ${book.name}: A열에 ${label} 행 없음 → 건너뜀`); report.push({ date: label, book: book.name, row: null }); continue; }
        const existing = await sheet.readRow(title, row);
        const perBook = {
          kyobo: data.kyobo ? lookupKyobo(data.kyobo, book) : null,
          yes24: pick(data.yes24, book),
          aladin: pick(data.aladin, book),
          ypbooks: pick(data.ypbooks, book),
        };
        const plan = planCells(book, existing, perBook, { force: opts.force });
        for (const w of plan.writes) writes.push({ title, row, ...w, book: book.name });
        const desc = plan.writes.map((w) => `${w.col}${row}=${w.value}`).join(' ') || '(쓸 값 없음)';
        const conflicts = plan.skipped.filter((s) => s.reason === 'exists').map((s) => `${s.col}=${s.current}≠${s.value}`);
        console.log(`  ${book.name}(${row}행): ${desc}${conflicts.length ? '  [기존값 유지: ' + conflicts.join(', ') + ']' : ''}`);
        report.push({ date: label, book: book.name, row, title, layout: book.layout, writes: plan.writes, conflicts });
      }

      if (opts.dryRun) console.log(`  (dry-run) ${writes.length}개 셀 기록 예정`);
      else {
        const n = await sheet.writeCells(writes);
        console.log(`  ${n}개 셀 기록 완료`);
        // 검증: 읽어서 값 일치 확인 + 종계 표시
        for (const r of report.filter((x) => x.date === label && x.row)) {
          const after = await sheet.readRow(r.title, r.row);
          const bad = r.writes.filter((w) => Number(String(after[COL_INDEX(w.col)] || '').replace(/,/g, '')) !== w.value);
          const total = after[COL_INDEX(config.totalColumn[r.layout])] ?? '';
          r.total = total;
          console.log(`    ${r.book}: 종계 ${total}${bad.length ? '  !! 검증 실패: ' + bad.map((w) => w.col).join(',') : ''}`);
        }
      }
    }

    console.log('\n--- 요약 ---');
    for (const r of report) {
      if (!r.row) { console.log(`${r.date} ${r.book}: 행 없음`); continue; }
      const vals = r.writes.map((w) => `${w.portal}:${w.value}`).join(' ') || '-';
      console.log(`${r.date} ${r.book}: ${vals}${r.total !== undefined ? `  종계=${r.total}` : ''}`);
    }
    console.log('\n※ 교보(하루 지연)·영풍(며칠 지연) 미집계분은 다음 실행(기본 --days 3)에서 빈 칸만 자동 백필됩니다.');
  } finally {
    await ctx.close();
  }
}

main().catch((e) => { console.error(`\n오류: ${e.message}`); process.exit(1); });
