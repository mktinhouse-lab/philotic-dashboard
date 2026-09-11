# -*- coding: utf-8 -*-
"""대시보드 맨 위에 '데이터 신선도' 카드를 붙인다.

이 대시보드는 원천이 여덟 갈래고 각자 다른 속도로 들어온다. 어떤 건 매일 자동으로 차고,
어떤 건 사람이 포털에 로그인해야만 채워진다. 그런데 화면에는 '기준일' 하나만 찍혀 있어서,
유튜브가 열흘 밀려 있어도 열어 본 사람은 모른다. 그래서 원천별로 며칠까지 들어와 있는지를
한 줄로 세운다 — 매일 갱신을 맡은 사람이 제일 먼저 볼 화면이다.
"""
import sys

CSS = """
/* ---- 데이터 신선도 ----
   원천마다 들어오는 속도가 달라서, '기준일' 한 개로는 무엇이 밀렸는지 알 수 없다.
   테두리 색으로 밀린 정도를, 꼬리표로 자동/수기를 구분한다. */
.freshrow{display:flex;flex-wrap:wrap;gap:8px}
.fr{border:1px solid var(--border);border-left-width:3px;border-radius:10px;padding:7px 11px;background:var(--plane)}
.fr b{display:block;font-size:12.5px;font-weight:620}
.fr span{font-size:12px;color:var(--text-secondary);font-variant-numeric:tabular-nums}
.fr.ok{border-left-color:var(--success-text)}
.fr.warn{border-left-color:var(--warning)}
.fr.bad{border-left-color:var(--critical)}
.fr i{font-style:normal;font-size:10.5px;border-radius:999px;padding:1px 6px;margin-left:6px;
 border:1px solid var(--border);color:var(--muted);white-space:nowrap}
"""

HTML = """
<div class="card" id="freshCard" style="padding:15px 18px">
 <h2 style="font-size:16px;margin:0 0 3px">데이터 신선도</h2>
 <p class="cap" id="freshCap" style="margin:0 0 11px"></p>
 <div class="freshrow" id="freshRow"></div>
 <p class="cap" id="freshNote" style="margin:11px 0 0"></p>
</div>
"""

JS = r"""
/* ---- 데이터 신선도 ----
   기준일을 원천별로 쪼개 보여준다. 날짜는 전부 이미 페이로드 안에 있는 값이라
   따로 관리하는 표가 없다 — 루틴이 무엇을 갱신했든 화면이 스스로 사실을 말한다. */
(function renderFresh(){
  const row = document.getElementById('freshRow');
  if (!row) return;
  const REF = D.asOfRun || D.collected;
  const dayGap = (a, b) => Math.round((Date.parse(b+'T00:00:00Z') - Date.parse(a+'T00:00:00Z')) / 86400000);
  /* 교보 순위 기준일은 ymw('20260908') 로 들어온다 */
  const ymd = v => (v && /^\d{8}$/.test(String(v))) ? String(v).slice(0,4)+'-'+String(v).slice(4,6)+'-'+String(v).slice(6,8) : null;
  const maxOf = f => { const xs = D.order.map(f).filter(Boolean); return xs.length ? xs.sort().pop() : null; };

  const items = [
    {n:'판매 (구글시트)', d: maxOf(k => (D.books[k].sales||[]).length ? D.books[k].sales[D.books[k].sales.length-1][0] : null),
     m:'수기', why:'서점 포털 4곳에서 사람이 받아 시트에 넣습니다'},
    {n:'메타 광고',       d: maxOf(k => (D.books[k].daily||[]).length ? D.books[k].daily[D.books[k].daily.length-1][0] : null), m:'자동'},
    {n:'인스타',          d: D.igAsOf, m:'자동'},
    {n:'페이스북',        d: D.fbAsOf, m:'자동'},
    {n:'교보 순위',       d: ymd(typeof KR !== 'undefined' && KR ? KR.asOf : null), m:'자동', why:'교보 서버에 닿지 못하면 이전 값이 그대로 남습니다'},
    {n:'유튜브',          d: (typeof YT !== 'undefined' && YT) ? YT.through : null, m:'수기', why:'윈저 유튜브 커넥터가 아직 연결되지 않았습니다'},
    {n:'볼라 링크',       d: (typeof VD !== 'undefined' && VD) ? VD.to : null, m:'수기', why:'로그인해야 통계가 보여 자동 수집이 안 됩니다'},
    {n:'교보 펀딩',       d: (typeof FD !== 'undefined' && FD && FD.asOf) ? String(FD.asOf).slice(0,10) : null, m:'자동'}
  ].filter(x => x.d);

  row.innerHTML = items.map(x => {
    const lag = dayGap(x.d, REF);
    const cls = lag <= 1 ? 'ok' : (lag <= 3 ? 'warn' : 'bad');
    const ago = lag <= 0 ? '오늘' : (lag === 1 ? '어제' : lag + '일 전');
    return '<div class="fr '+cls+'"'+(x.why ? ' title="'+esc(x.why)+'"' : '')+'>'
         + '<b>'+esc(x.n)+'<i>'+x.m+'</i></b>'
         + '<span>'+x.d.slice(5).replace('-','/')+' · '+ago+'</span></div>';
  }).join('');

  const late = items.filter(x => dayGap(x.d, REF) > 3);
  document.getElementById('freshCap').innerHTML =
    '원천마다 들어오는 속도가 다릅니다. <b>'+REF+'</b> 기준으로 각 원천이 며칠 치까지 채워져 있는지입니다 — '
    + '<i>자동</i>은 매일 도는 루틴이, <i>수기</i>는 사람이 채웁니다.';
  document.getElementById('freshNote').innerHTML = late.length
    ? '<b style="color:var(--critical)">4일 넘게 밀린 원천 '+late.length+'개</b> — '
      + late.map(x => esc(x.n)+'('+x.d.slice(5).replace('-','/')+(x.why ? ', '+esc(x.why) : '')+')').join(' · ')
      + '. 이 구간은 화면의 다른 카드에서도 비어 있거나 예전 값입니다.'
    : '모든 원천이 3일 안쪽입니다.';
})();
"""

def main(path):
    h = open(path, encoding='utf-8').read()
    assert 'id="freshCard"' not in h, '이미 붙어 있습니다'

    anchor = '.warnbox{border-left:3px solid var(--warning);padding-left:13px;font-size:13px;color:var(--text-secondary)}'
    assert anchor in h
    h = h.replace(anchor, anchor + '\n' + CSS.strip(), 1)

    anchor = '<nav class="tabs" id="tabs" role="tablist"></nav>\n'
    assert anchor in h
    h = h.replace(anchor, anchor + HTML, 1)

    anchor = "document.getElementById('acctId').textContent = D.account;"
    assert anchor in h
    h = h.replace(anchor, JS.strip() + '\n\n' + anchor, 1)

    open(path, 'w', encoding='utf-8').write(h)
    print('신선도 카드 삽입 완료')

if __name__ == '__main__':
    main(sys.argv[1])
