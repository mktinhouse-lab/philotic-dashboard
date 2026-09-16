/* 교보 순위 수집기 — 브라우저 콘솔용
 * ────────────────────────────────────────────────────────────
 *  1) https://store.kyobobook.co.kr/bestseller/online/daily 를 연다
 *  2) F12 → Console 탭
 *  3) 이 파일 전체를 붙여넣고 Enter
 *  4) 화면에 뜨는 상자의 JSON 을 복사해서 클로드에게 준다
 *
 * 왜 브라우저인가 — 클라우드 세션은 교보로 나가는 길이 막혀 있다(CONNECT 403).
 * 이 스크립트는 교보 사이트 안에서 도니까 같은 출처라 막힐 것이 없다.
 * 로그인도 필요 없다 — 베스트셀러는 공개 데이터다.
 *
 * tools/ranks.py 와 같은 면·같은 순서로 훑는다. 산출물도 같은 모양이라
 * tools/apply_ranks_json.py 가 그대로 받아 아티팩트에 넣는다.
 */
(async () => {
  const KEY = 'eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0..SAuG7hzFxwWfewcz.gMw0bGwwgB9Xx8Wxz-Y6ihk4IMgSa-5CM-'
            + 'ZzIdfRNQbqMbvLUmv5-9sRubZjE-iJ-wNPlNbpFnHprd3aMGDrJGqCkUNz3AkvR24a6S18-9PUCOySLlK296YlQwyHKRLDprH1Atq8'
            + '.Vy8qyA72gFcghwWdO0q-_A';
  const BASE = 'https://store.kyobobook.co.kr/api/gw/best/best-seller/';
  const DEPTH = 500, PER = 50;

  const BOOKS = {
    kaljung: { title:'칼 융의 내면수업',   match:'칼 융의 내면수업',   cat:'인문',     catCode:'I', pid:'S000220665243' },
    wonsiin: { title:'완벽한 원시인',      match:'완벽한 원시인',      cat:'인문',     catCode:'I', pid:'S000219310977' },
    freud:   { title:'프로이트의 감정수업', match:'프로이트의 감정수업', cat:'인문',     catCode:'I', pid:'S000218149524' },
    muhan:   { title:'무한의 부',          match:'무한의 부',          cat:'자기계발', catCode:'c', pid:'S000214211407' },
  };

  const SURFACES = [
    { key:'onlineDaily',     label:'온라인 일간 · 종합', ep:'online',   q:{period:'001', dsplDvsnCode:'000', dsplTrgtDvsnCode:'001'}, deep:true },
    { key:'onlineWeekly',    label:'온라인 주간 · 종합', ep:'online',   q:{period:'002', dsplDvsnCode:'000', dsplTrgtDvsnCode:'001'}, deep:true },
    { key:'onlineMonthly',   label:'온라인 월간 · 종합', ep:'online',   q:{period:'003', dsplDvsnCode:'000', dsplTrgtDvsnCode:'001'}, deep:true },
    { key:'realtime',        label:'실시간 베스트',      ep:'realtime', q:{}, deep:true },
    { key:'steady',          label:'스테디셀러',         ep:'steady',   q:{}, deep:true },
    { key:'totalWeeklyAll',  label:'종합 주간 · 전체',   ep:'total',    q:{period:'002', bsslBksClstCode:'A'}, deep:true },
    { key:'totalMonthlyAll', label:'종합 월간 · 전체',   ep:'total',    q:{period:'003', bsslBksClstCode:'A'}, deep:true },
    /* 분야별은 교보가 20개까지만 준다 — 더 넘겨도 빈 페이지다 */
    { key:'totalWeeklyCat',  label:'종합 주간 · 분야',   ep:'total',    q:{period:'002'}, byCat:true },
    { key:'totalMonthlyCat', label:'종합 월간 · 분야',   ep:'total',    q:{period:'003'}, byCat:true },
    { key:'totalAnnualCat',  label:'종합 연간 · 분야',   ep:'total',    q:{period:'004'}, byCat:true },
  ];

  const say = (...a) => console.log('%c[교보]', 'color:#2a78d6;font-weight:700', ...a);

  async function page(ep, q, p) {
    const u = new URL(BASE + ep);
    Object.entries({ ...q, page: String(p), per: String(PER) }).forEach(([k, v]) => u.searchParams.set(k, v));
    const r = await fetch(u, { headers: { 'content-type':'application/json', 'x-api-gw-key': KEY }, credentials:'omit' });
    if (!r.ok) throw new Error(ep + ' HTTP ' + r.status + (r.status === 403 ? ' — API 키가 갈렸습니다' : ''));
    const d = (await r.json() || {}).data || {};
    return [d.bestSeller || [], d.ymw];
  }

  /* 한 면을 훑어 대상 책을 찾는다. 다 찾으면 바로 멈춘다 — 500위까지 다 볼 이유가 없다. */
  async function sweep(sf, targets, q) {
    const found = {}; let ymw = null;
    const maxp = sf.deep ? Math.ceil(DEPTH / PER) : 1;
    for (let p = 1; p <= maxp; p++) {
      const [lst, y] = await page(sf.ep, q, p);
      if (p === 1) ymw = y;
      if (!lst.length) break;
      for (const t of targets) {
        if (found[t.key]) continue;
        const hit = lst.find(x => String(x.cmdtName || '').includes(t.match));
        if (hit) found[t.key] = { rank: hit.prstRnkn, prev: hit.frmrRnkn };
      }
      if (Object.keys(found).length === targets.length) break;
      if (lst.length < PER) break;
    }
    return [found, ymw];
  }

  const out = {}, periods = {};
  for (const k of Object.keys(BOOKS)) out[k] = { ranks: {}, weeklyBest: null };

  for (const sf of SURFACES) {
    try {
      if (sf.byCat) {
        const byCode = {};
        for (const [k, b] of Object.entries(BOOKS)) (byCode[b.catCode] = byCode[b.catCode] || []).push({ key:k, match:b.match });
        for (const [code, targets] of Object.entries(byCode)) {
          const [found, ymw] = await sweep(sf, targets, { ...sf.q, bsslBksClstCode: code });
          targets.forEach(t => out[t.key].ranks[sf.key] = found[t.key] || null);
          periods[sf.key] = ymw;
        }
      } else {
        const targets = Object.entries(BOOKS).map(([k, b]) => ({ key:k, match:b.match }));
        const [found, ymw] = await sweep(sf, targets, sf.q);
        targets.forEach(t => out[t.key].ranks[sf.key] = found[t.key] || null);
        periods[sf.key] = ymw;
      }
      const hits = Object.keys(BOOKS).filter(k => out[k].ranks[sf.key]).length;
      say(sf.label.padEnd(16), hits + '/4권', periods[sf.key] || '-');
    } catch (e) {
      say(sf.label.padEnd(16), '실패 —', e.message);
      Object.keys(BOOKS).forEach(k => { if (!(sf.key in out[k].ranks)) out[k].ranks[sf.key] = null; });
    }
  }

  /* 상품 페이지의 '주간베스트'. 분야 목록이 20위까지만 주므로 그 밖의 책은 이 값만 있다.
     store 와 product 는 서로 다른 출처라 브라우저가 막을 수 있다 — 막히면 조용히 건너뛴다.
     (그 경우 아티팩트는 이전 주간베스트 값을 그대로 유지한다.) */
  const WB = /<span>([^<>]{1,20})<!--\s*-->\s*<span>([\d,]+)<\/span>위<\/span>/g;
  for (const [k, b] of Object.entries(BOOKS)) {
    try {
      const t = await (await fetch('https://product.kyobobook.co.kr/detail/' + b.pid)).text();
      const hits = [...t.matchAll(WB)].map(m => [m[1].trim(), +m[2].replace(/,/g, '')]);
      const ov = hits.find(h => h[0] === '국내도서'), ct = hits.find(h => h[0] !== '국내도서');
      if (ov || ct) out[k].weeklyBest = { overall: ov ? ov[1] : null, cat: ct ? ct[1] : null, catName: ct ? ct[0] : b.cat };
      say('  주간베스트', b.title, ov ? ov[1] + '위' : '–', ct ? ct[0] + ' ' + ct[1] + '위' : '');
    } catch (e) {
      say('  주간베스트', b.title, '건너뜀 (' + e.message + ') — 이전 값이 유지됩니다');
    }
  }

  const kst = new Date(Date.now() + (new Date().getTimezoneOffset() + 540) * 60000);
  const pad = n => String(n).padStart(2, '0');
  const payload = {
    source: 'browser-console',
    asOf: periods.onlineDaily || null,
    collected: `${kst.getFullYear()}-${pad(kst.getMonth()+1)}-${pad(kst.getDate())} ${pad(kst.getHours())}:${pad(kst.getMinutes())}`,
    periods, books: out,
  };
  const json = JSON.stringify(payload);
  window.__RANKS = json;

  /* 클립보드 API 는 탭이 포커스를 잃으면 막히므로, 화면에 상자를 띄워 전체 선택까지 해 둔다.
     Ctrl+C(⌘C) 한 번이면 끝난다. */
  const box = document.createElement('textarea');
  box.value = json;
  Object.assign(box.style, { position:'fixed', zIndex:2147483647, left:'4vw', top:'4vh', width:'92vw', height:'40vh',
                             font:'12px/1.4 monospace', padding:'12px', border:'3px solid #2a78d6', borderRadius:'10px',
                             background:'#fff', color:'#111' });
  const tip = document.createElement('div');
  tip.textContent = '⬇ 전체 선택돼 있습니다. Ctrl+C (맥은 ⌘C) 로 복사해서 클로드에게 붙여넣으세요. (닫으려면 이 줄을 클릭)';
  Object.assign(tip.style, { position:'fixed', zIndex:2147483647, left:'4vw', top:'calc(4vh - 30px)', width:'92vw',
                             font:'700 14px/1.6 system-ui', background:'#2a78d6', color:'#fff', padding:'4px 12px',
                             borderRadius:'8px 8px 0 0', cursor:'pointer' });
  tip.onclick = () => { box.remove(); tip.remove(); };
  document.body.append(tip, box);
  box.focus(); box.select();
  try { await navigator.clipboard.writeText(json); say('클립보드에도 복사했습니다.'); } catch (_) {}

  const n = Object.values(out).reduce((a, b) => a + Object.values(b.ranks).filter(Boolean).length, 0);
  say(`끝 — 기준 ${payload.asOf || '?'} · 순위 ${n}개. 위 상자의 JSON 을 클로드에게 주세요.`);
  return payload;
})();
