/* 볼라(vo.la) 정탐기 — 브라우저 콘솔용
 * ────────────────────────────────────────────────────────────
 * 볼라는 로그인해야 통계가 보이고, 클라우드 세션은 vo.la 로 나가지도 못한다.
 * 그래서 수집기를 바로 쓸 수가 없다 — 어떤 주소로 무슨 모양의 값이 오는지를 모르기 때문이다.
 * 이 파일은 그걸 알아내기 위한 것이다. 한 번만 돌리면 된다.
 *
 *  1) book@pudufu.co.kr 로 로그인한 채 https://vo.la/user/links 를 연다
 *  2) F12 → Console 에 이 파일 전체를 붙여넣고 Enter
 *  3) 평소처럼 화면을 만진다 — 링크 목록을 넘겨 보고, 링크 하나의 '통계'를 열고,
 *     일별 그래프와 리퍼러(유입경로)까지 눌러 본다. (30초면 충분하다)
 *  4) 콘솔에 __VOLA_DUMP() 를 치고 Enter → 뜨는 상자의 내용을 클로드에게 준다
 *
 * 무엇을 담는가 — 페이지가 스스로 부른 주소와 그 응답의 **모양**이다.
 * 응답이 크면 앞부분만 자르고, 배열은 처음 두 칸만 남긴다. 구조만 알면 되기 때문이다.
 * 쿠키·토큰·Authorization 헤더는 담지 않는다 — 로그인 정보는 이 상자에 들어가지 않는다.
 */
(() => {
  if (window.__VOLA_DUMP) { console.log('%c[볼라] 이미 켜져 있습니다. 화면을 만진 뒤 __VOLA_DUMP() 를 치세요.', 'color:#eb6834;font-weight:700'); return; }
  const LOG = [];
  const MAX = 60;
  const say = (...a) => console.log('%c[볼라]', 'color:#eb6834;font-weight:700', ...a);

  /* 응답을 통째로 담으면 상자가 터진다. 구조만 남긴다 —
     배열은 앞 2개, 문자열은 120자, 깊이는 6단까지. */
  const shrink = (v, d = 0) => {
    if (v === null || typeof v !== 'object') return typeof v === 'string' && v.length > 120 ? v.slice(0, 120) + '…' : v;
    if (d >= 6) return '…';
    if (Array.isArray(v)) return v.slice(0, 2).map(x => shrink(x, d + 1)).concat(v.length > 2 ? ['…총' + v.length + '개'] : []);
    const o = {};
    for (const k of Object.keys(v).slice(0, 40)) o[k] = shrink(v[k], d + 1);
    return o;
  };

  const note = (how, url, status, ct, body) => {
    if (LOG.length >= MAX) return;
    if (/\.(js|css|png|jpe?g|gif|svg|woff2?|ico)(\?|$)/i.test(url)) return;   // 정적 파일은 볼 것 없다
    let shape = null;
    try { shape = shrink(JSON.parse(body)); }
    catch (_) { shape = String(body || '').slice(0, 300); }
    LOG.push({ how, url, status, ct, shape });
    say(how, status, url.replace(/^https?:\/\/[^/]+/, ''));
  };

  const of = window.fetch;
  window.fetch = async function (...a) {
    const r = await of.apply(this, a);
    try {
      const u = typeof a[0] === 'string' ? a[0] : (a[0] && a[0].url) || '';
      const c = r.clone();
      note('fetch', new URL(u, location.href).href, r.status, c.headers.get('content-type') || '', await c.text());
    } catch (_) {}
    return r;
  };

  const oo = XMLHttpRequest.prototype.open, os = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (m, u, ...rest) { this.__u = u; this.__m = m; return oo.call(this, m, u, ...rest); };
  XMLHttpRequest.prototype.send = function (...a) {
    this.addEventListener('load', () => {
      try { note('xhr ' + this.__m, new URL(this.__u, location.href).href, this.status,
                 this.getResponseHeader('content-type') || '', this.responseText); } catch (_) {}
    });
    return os.apply(this, a);
  };

  /* 통계가 서버 호출 없이 화면에 박혀 있는 경우도 있다 — 표의 생김새도 같이 담는다 */
  const domPeek = () => {
    const out = [];
    document.querySelectorAll('table').forEach((t, i) => {
      if (i >= 4) return;
      const head = [...t.querySelectorAll('thead th, tr:first-child th, tr:first-child td')].map(x => x.innerText.trim()).slice(0, 12);
      const rows = [...t.querySelectorAll('tbody tr')].slice(0, 3)
        .map(r => [...r.children].map(c => c.innerText.trim().slice(0, 40)).slice(0, 12));
      out.push({ head, rows, rowCount: t.querySelectorAll('tbody tr').length });
    });
    return out;
  };

  window.__VOLA_DUMP = () => {
    const dump = { page: location.href, at: new Date().toISOString(), calls: LOG, tables: domPeek() };
    const json = JSON.stringify(dump, null, 1);
    const box = document.createElement('textarea');
    box.value = json;
    Object.assign(box.style, { position:'fixed', zIndex:2147483647, left:'4vw', top:'6vh', width:'92vw', height:'70vh',
                               font:'12px/1.4 monospace', padding:'12px', border:'3px solid #eb6834', borderRadius:'10px',
                               background:'#fff', color:'#111' });
    const tip = document.createElement('div');
    tip.textContent = '⬇ 전체 선택돼 있습니다. Ctrl+C (맥은 ⌘C) 로 복사해 클로드에게 주세요. (닫으려면 이 줄 클릭)';
    Object.assign(tip.style, { position:'fixed', zIndex:2147483647, left:'4vw', top:'calc(6vh - 30px)', width:'92vw',
                               font:'700 14px/1.6 system-ui', background:'#eb6834', color:'#fff', padding:'4px 12px',
                               borderRadius:'8px 8px 0 0', cursor:'pointer' });
    tip.onclick = () => { box.remove(); tip.remove(); };
    document.body.append(tip, box);
    box.focus(); box.select();
    try { navigator.clipboard.writeText(json); } catch (_) {}
    say('호출 ' + LOG.length + '건 · 표 ' + dump.tables.length + '개를 담았습니다.');
    return dump;
  };

  say('켰습니다. 이제 링크 목록을 넘겨 보고, 링크 하나의 통계(일별·리퍼러)를 열어 보세요.');
  say('다 만졌으면 __VOLA_DUMP() 를 치고 Enter.');
})();
