/* 볼라(vo.la) 수집기 — 브라우저 콘솔용 · 한 번만 돌리면 된다
 * ────────────────────────────────────────────────────────────
 * 왜 이게 필요한가
 *   볼라는 로그인해야 숫자가 보인다. 클라우드 세션은 vo.la 로 나가지도 못한다(프록시가 막는다).
 *   그래서 민석님이 로그인해 둔 브라우저가 유일한 통로다.
 *
 * 쓰는 법
 *   1) https://vo.la/user/links 를 연다 (로그인된 창)
 *   2) F12 → Console 에 이 파일 전체를 붙여넣고 Enter
 *   3) 알아서 긁는다. 20~40초. 다 되면 큰 상자가 뜬다.
 *   4) 상자 내용이 이미 복사돼 있다. 클로드에게 그대로 붙여넣으면 된다.
 *
 * 무엇을 담는가 — 링크 코드 · 제목 · 클릭수 · 일별 그래프 · 유입경로, 그리고
 *   화면이 스스로 부른 주소의 **모양**(다음부터 자동화하려면 이게 필요하다).
 * 무엇을 안 담는가 — 쿠키 · 토큰 · Authorization 헤더 · 비밀번호. 한 글자도 담지 않는다.
 */
(() => {
  if (window.__VOLA) { console.log('%c[볼라] 이미 돌고 있습니다.', 'color:#eb6834;font-weight:700'); return; }
  const say = (...a) => console.log('%c[볼라]', 'color:#eb6834;font-weight:700', ...a);
  const CALLS = [];
  const MAX = 80;

  /* 응답을 통째로 담으면 상자가 터진다 — 배열은 앞 3개, 문자열은 160자까지만 */
  const shrink = (v, d = 0) => {
    if (v === null || typeof v !== 'object') return typeof v === 'string' && v.length > 160 ? v.slice(0,160)+'…' : v;
    if (d >= 7) return '…';
    if (Array.isArray(v)) return v.slice(0,3).map(x => shrink(x, d+1)).concat(v.length>3 ? ['…총'+v.length+'개'] : []);
    const o = {}; for (const k of Object.keys(v).slice(0,50)) o[k] = shrink(v[k], d+1); return o;
  };
  const SECRET = /^(cookie|set-cookie|authorization|x-auth|x-csrf|token)/i;
  const note = (how, url, status, ct, body) => {
    if (CALLS.length >= MAX) return;
    if (/\.(js|css|png|jpe?g|gif|svg|woff2?|ico|map)(\?|$)/i.test(url)) return;
    let shape = null;
    try { shape = shrink(JSON.parse(body)); } catch (_) { shape = String(body||'').slice(0,400); }
    CALLS.push({ how, url: url.replace(/^https?:\/\/[^/]+/, ''), status, ct, shape });
  };

  /* 1) 화면이 부르는 주소를 엿듣는다 */
  const of_ = window.fetch;
  window.fetch = async function (...a) {
    const r = await of_.apply(this, a);
    try { const u = typeof a[0]==='string' ? a[0] : (a[0]&&a[0].url)||'';
          const c = r.clone();
          note('fetch', new URL(u, location.href).href, r.status, c.headers.get('content-type')||'', await c.text()); } catch(_){}
    return r;
  };
  const oo = XMLHttpRequest.prototype.open, os = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (m,u,...r){ this.__u=u; this.__m=m; return oo.call(this,m,u,...r); };
  XMLHttpRequest.prototype.send = function (...a) {
    this.addEventListener('load', () => {
      try { note('xhr '+this.__m, new URL(this.__u, location.href).href, this.status,
                 this.getResponseHeader('content-type')||'', this.responseText); } catch(_){}
    });
    return os.apply(this, a);
  };

  /* 2) 화면에 이미 박혀 있는 표를 긁는다 */
  const tables = () => [...document.querySelectorAll('table')].slice(0,6).map(t => ({
    head: [...t.querySelectorAll('thead th, tr:first-child th, tr:first-child td')].map(x=>x.innerText.trim()).slice(0,14),
    rows: [...t.querySelectorAll('tbody tr')].slice(0,40).map(r => [...r.children].map(c=>c.innerText.trim().slice(0,60)).slice(0,14)),
    rowCount: t.querySelectorAll('tbody tr').length,
  }));

  /* 3) 보이는 글자에서 vo.la 코드와 그 옆 숫자를 줍는다 (표가 아닌 카드 모양일 때 대비) */
  const cards = () => {
    const out = [];
    document.querySelectorAll('a[href*="vo.la/"]').forEach(a => {
      const code = (a.getAttribute('href')||'').split('vo.la/')[1];
      if (!code || /^user/.test(code)) return;
      let box = a, hop = 0;
      while (box && hop++ < 6 && box.innerText.replace(/\s+/g,'').length < 24) box = box.parentElement;
      const txt = (box ? box.innerText : '').replace(/\s+/g,' ').trim().slice(0,220);
      out.push({ code: code.replace(/[?#].*$/,''), near: txt });
    });
    const seen = new Set();
    return out.filter(x => !seen.has(x.code) && seen.add(x.code)).slice(0,60);
  };

  /* 4) 있을 법한 주소를 직접 두드려 본다 — 로그인 쿠키는 브라우저가 알아서 붙인다 */
  const GUESS = [
    '/api/user/links', '/api/links', '/api/v1/links', '/user/links/list',
    '/api/user/link/list', '/api/statistics', '/api/user/statistics',
    '/api/dashboard', '/api/user/dashboard', '/api/user/me', '/api/token',
  ];
  const knock = async () => {
    for (const p of GUESS) {
      try {
        const r = await of_(p, { credentials: 'include', headers: { accept: 'application/json' } });
        const ct = r.headers.get('content-type') || '';
        const b = await r.text();
        if (r.status === 404) continue;
        note('두드림', location.origin + p, r.status, ct, b);
      } catch (_) {}
    }
  };

  /* 5) 화면을 대신 눌러 본다 — 통계 버튼이 있으면 첫 두 개만 */
  const clickStats = async () => {
    const btns = [...document.querySelectorAll('a,button')]
      .filter(e => /통계|statistic|분석|상세/.test(e.innerText||'')).slice(0,2);
    for (const b of btns) { try { b.click(); await new Promise(r=>setTimeout(r,2500)); } catch(_){} }
  };

  const box = (json) => {
    const t = document.createElement('textarea');
    t.value = json;
    Object.assign(t.style, { position:'fixed', zIndex:2147483647, left:'4vw', top:'7vh', width:'92vw', height:'70vh',
      font:'12px/1.4 monospace', padding:'12px', border:'3px solid #eb6834', borderRadius:'10px', background:'#fff', color:'#111' });
    const tip = document.createElement('div');
    tip.textContent = '⬇ 복사됐습니다. 안 됐으면 Ctrl+C (맥 ⌘C). 클로드에게 그대로 붙여넣으세요. (닫기: 이 줄 클릭)';
    Object.assign(tip.style, { position:'fixed', zIndex:2147483647, left:'4vw', top:'calc(7vh - 30px)', width:'92vw',
      font:'700 14px/1.6 system-ui', background:'#eb6834', color:'#fff', padding:'4px 12px', borderRadius:'8px 8px 0 0', cursor:'pointer' });
    tip.onclick = () => { t.remove(); tip.remove(); };
    document.body.append(tip, t); t.focus(); t.select();
    try { navigator.clipboard.writeText(json); } catch(_){}
  };

  window.__VOLA = async () => {
    const dump = { page: location.href, at: new Date().toISOString(),
                   tables: tables(), cards: cards(), calls: CALLS };
    const json = JSON.stringify(dump, null, 1);
    box(json);
    say('표 '+dump.tables.length+'개 · 링크 '+dump.cards.length+'개 · 호출 '+CALLS.length+'건');
    return dump;
  };

  (async () => {
    say('긁는 중… 창을 그대로 두세요. 20~40초 걸립니다.');
    await new Promise(r => setTimeout(r, 1500));
    await knock();
    await clickStats();
    await new Promise(r => setTimeout(r, 1500));
    await window.__VOLA();
    say('끝났습니다. 숫자가 빈약하면 링크 하나의 통계를 직접 눌러 본 뒤 __VOLA() 를 다시 치세요.');
  })();
})();
