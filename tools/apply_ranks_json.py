#!/usr/bin/env python3
"""브라우저 콘솔 수집기(collect-ranks-console.js)가 뱉은 JSON 을 아티팩트에 넣는다.

  python3 tools/apply_ranks_json.py <html경로> <json경로|->

ranks.py 가 네트워크로 직접 받아 하던 일을, 사람이 가져온 값으로 대신 한다.
hist 누적·정리 규칙은 ranks.py 와 똑같이 맞춰야 추이 그래프가 이어진다.

받은 값은 '사람이 브라우저에서 받아온 것'이지 API 가 이 세션에 직접 준 것이 아니다.
그래도 숫자 자체는 교보 API 원본이므로 set_rank.py 의 수기 딱지는 붙이지 않는다 —
대신 lastTry.via 에 경로를 남겨 두어, 나중에 누가 봐도 어디서 온 값인지 알 수 있게 한다.
"""
import sys, json, datetime

OPEN = '<script id="kyoboRanks" type="application/json">'
KEEP_DAYS = 400


def main(html_path, json_path):
    raw = sys.stdin.read() if json_path == '-' else open(json_path, encoding='utf-8').read()
    inc = json.loads(raw)
    if inc.get('source') != 'browser-console':
        sys.exit('collect-ranks-console.js 가 만든 JSON 이 아닙니다 (source 필드 확인).')
    if not inc.get('books'):
        sys.exit('books 가 비어 있습니다 — 수집이 실패한 JSON 입니다.')

    html = open(html_path, encoding='utf-8').read()
    s = html.index(OPEN) + len(OPEN)
    e = html.index('</script>', s)
    KR = json.loads(html[s:e])

    # 책 메타(cat/path/pid)와 면 목록은 아티팩트 쪽을 그대로 둔다 — 콘솔 수집기는 순위만 가져온다
    changed = []
    for k, nb in inc['books'].items():
        old = KR.setdefault('books', {}).setdefault(k, {'ranks': {}})
        before = {sf: (old.get('ranks') or {}).get(sf, {}).get('rank') if (old.get('ranks') or {}).get(sf) else None
                  for sf in nb.get('ranks', {})}
        old['ranks'] = nb.get('ranks') or {}
        # 주간베스트는 출처(product 페이지)가 막히면 None 으로 온다. 그때는 이전 값을 지키지 않으면
        # 20위 밖인 책의 유일한 순위가 사라진다.
        if nb.get('weeklyBest'):
            old['weeklyBest'] = nb['weeklyBest']
        for sf, nv in (nb.get('ranks') or {}).items():
            nvr = nv.get('rank') if nv else None
            if nvr != before.get(sf):
                changed.append('%s·%s %s→%s' % (k, sf, before.get(sf) or '–', nvr or '–'))

    a = str(inc.get('asOf') or '')
    KR['asOf'] = inc.get('asOf') or KR.get('asOf')
    KR['collected'] = inc.get('collected') or KR.get('collected')
    if inc.get('periods'):
        KR['periods'] = inc['periods']

    # ── hist: 날짜 키는 '집계 기준일'(온라인 일간의 ymw). ranks.py 와 같은 규칙.
    day = (a[0:4] + '-' + a[4:6] + '-' + a[6:8]) if len(a) == 8 else str(KR.get('collected'))[:10]
    hist = KR.setdefault('hist', {})
    hist[day] = {}
    for k, nb in inc['books'].items():
        row = {}
        for sf, v in (nb.get('ranks') or {}).items():
            if v and v.get('rank') is not None:
                row[sf] = v['rank']
        wb = (KR['books'][k].get('weeklyBest') or {})
        if wb.get('overall') is not None:
            row['wbOverall'] = wb['overall']
        if wb.get('cat') is not None:
            row['wbCat'] = wb['cat']
        hist[day][k] = row

    # 교보가 주는 '전일 순위'로 어제 하루만 채운다. 이미 있는 날은 덮지 않는다.
    try:
        yd = (datetime.date(int(day[0:4]), int(day[5:7]), int(day[8:10])) - datetime.timedelta(days=1)).isoformat()
        hist.setdefault(yd, {})
        for k, nb in inc['books'].items():
            p = ((nb.get('ranks') or {}).get('onlineDaily') or {}).get('prev')
            if p in (None, 0):
                continue
            merged = {'onlineDaily': p}
            merged.update(hist[yd].get(k) or {})
            hist[yd][k] = merged
        if not hist[yd]:
            del hist[yd]
    except ValueError:
        pass

    for d in sorted(hist)[:max(0, len(hist) - KEEP_DAYS)]:
        del hist[d]

    KR['lastTry'] = {'at': inc.get('collected'), 'ok': True,
                     'why': '', 'via': '브라우저 콘솔 수집 (세션 네트워크가 교보를 막고 있어 사람이 대신 받아왔습니다)'}

    doc = html[:s] + json.dumps(KR, ensure_ascii=False) + html[e:]
    for name, ok in [('payload 유지', 'id="payload"' in doc), ('thumbs 유지', 'id="thumbs"' in doc),
                     ('kyoboRanks 1회', doc.count(OPEN) == 1), ('기준일 있음', bool(KR.get('asOf')))]:
        if not ok:
            sys.exit('검증 실패(%s) — 아무것도 쓰지 않았습니다' % name)

    open(html_path, 'w', encoding='utf-8').write(doc)
    print('기준 %s · 수집 %s · hist %d일' % (KR['asOf'], KR['collected'], len(hist)))
    print('바뀐 순위 %d개: %s' % (len(changed), ', '.join(changed[:12]) or '없음'))


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
