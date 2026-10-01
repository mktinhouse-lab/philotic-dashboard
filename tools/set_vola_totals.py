#!/usr/bin/env python3
"""볼라 링크별 누적 클릭수를 대시보드의 volaDaily 블록에 넣는다.

왜 이 모양인가 — 볼라는 로그인해야 숫자가 보이고 클라우드 세션은 vo.la 로 나가지 못한다
(프록시 CONNECT 403). 그래서 사람이 로그인한 브라우저 콘솔에서 `tools/vola-console.js`
한 줄을 돌려 누적 클릭수를 받아 온다. 그 결과를 JSON 으로 받아 여기서 반영한다.

받는 것은 **누적**이지 일별이 아니다. 그래서 `daily` 는 건드리지 않고 `total` 만 고친다.
화면(volaBlock)은 `total` 이 있으면 그걸 누적으로 쓰고, 없으면 daily 합을 쓴다.

    python3 tools/set_vola_totals.py dash.html totals.json [--out dash.html]

totals.json 모양:
    {"asOf": "2026-10-01",
     "totals": {"seameta": 79057, "seafb": 573, ...},
     "new": {"nRrG3l": {"name": "대표님 스토리 유입", "chan": "etc", "book": "pyoryu"}}}
`new` 는 처음 보는 링크만 적으면 된다 — 이미 있는 코드는 무시된다.
"""
import json, re, sys, datetime

BLOCK = 'volaDaily'
KEEP_DAYS = 180          # 날짜별 누적을 몇 날치까지 들고 있을지 — 반년이면 넉넉하다


def find_block(html, name):
    """블록의 진짜 끝을 찾는다. JSON 안에 </script> 가 들어 있을 수 있으므로
    닫는 태그마다 json.loads 를 시도해서 성공하는 자리를 끝으로 본다."""
    open_tag = '<script id="%s" type="application/json">' % name
    i = html.find(open_tag)
    if i < 0:
        raise SystemExit('블록 없음: ' + name)
    start = i + len(open_tag)
    pos = start
    while True:
        end = html.find('</script>', pos)
        if end < 0:
            raise SystemExit('블록이 안 닫힘: ' + name)
        try:
            return start, end, json.loads(html[start:end])
        except json.JSONDecodeError:
            pos = end + 1


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    path, feed = sys.argv[1], sys.argv[2]
    out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else path

    html = open(path, encoding='utf-8').read()
    start, end, d = find_block(html, BLOCK)
    src = json.load(open(feed, encoding='utf-8'))

    totals = {str(k): int(v) for k, v in (src.get('totals') or {}).items()}
    if not totals:
        raise SystemExit('totals 가 비었다 — 넣을 게 없다')

    # 「안 볼 링크」. 볼라에 남아 있어도 화면에서는 뺀다 — 잘못 붙였거나 안 쓰는 링크다.
    # 블록에 적어 두지 않으면 매일 API 가 다시 끌어와 되살아난다.
    drop = set(d.get('drop') or [])
    if drop:
        totals = {k: v for k, v in totals.items() if k not in drop}
    as_of = src.get('asOf') or datetime.date.today().isoformat()

    d.setdefault('total', {})
    d.setdefault('book', {})
    links = d.setdefault('links', [])
    known = {l[0] for l in links}

    # 처음 보는 링크를 목록에 넣는다. 이름이 없으면 코드를 그대로 쓴다.
    added = []
    for code in totals:
        if code in known:
            continue
        meta = (src.get('new') or {}).get(code) or {}
        links.append([code, meta.get('name') or code, meta.get('chan') or 'etc'])
        if meta.get('book'):
            d['book'][code] = meta['book']
        known.add(code)
        added.append(code)

    # 누적을 덮어쓴다. 줄어들면 수상하니 알린다 — 볼라에서 통계를 초기화한 경우다.
    daily = d.get('daily') or {}
    moved, shrank = [], []
    for code, v in totals.items():
        before = d['total'].get(code)
        if before is None:
            before = sum((daily.get(code) or {}).values())
        if v < before:
            shrank.append((code, before, v))
        if v != before:
            moved.append((code, before, v))
        d['total'][code] = v

    # 안 볼 링크가 이미 들어와 있으면 치운다
    for code in drop:
        d['total'].pop(code, None)
        d['book'].pop(code, None)
        (d.get('daily') or {}).pop(code, None)
    if drop:
        d['links'] = [l for l in links if l[0] not in drop]
        for bk, m in (d.get('chan') or {}).items():
            for ch, code in list(m.items()):
                if code in drop:
                    m[ch] = None

    d['totalAsOf'] = as_of
    d['collected'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

    # 날짜별 누적을 쌓는다. 볼라 API 는 누적만 주고 일별을 안 준다 —
    # 어제 누적과 오늘 누적의 차가 곧 그날 클릭이다. 화면은 그걸로 그린다.
    # 볼라 자신도 통계를 30일만 보관하므로, 여기 쌓이는 게 유일한 과거 기록이 된다.
    hist = d.setdefault('totalHist', {})
    hist[as_of] = dict(totals)
    for day in sorted(hist)[:-KEEP_DAYS]:          # 오래된 것부터 버린다
        del hist[day]
    d['histDays'] = len(hist)

    enc = json.dumps(d, ensure_ascii=False, separators=(',', ':'))
    enc = enc.replace('</script', r'<\/script')          # 블록이 일찍 끝나지 않도록
    open(out, 'w', encoding='utf-8').write(html[:start] + enc + html[end:])

    print('볼라 누적 %d개 반영 · 기준 %s' % (len(totals), as_of))
    if added:
        print('  새 링크 %d개: %s' % (len(added), ', '.join(added)))
    for code, a, b in sorted(moved, key=lambda x: -(x[2] - x[1]))[:12]:
        print('  %-16s %8s → %8s  (%+d)' % (code, a, b, b - a))
    for code, a, b in shrank:
        print('  ※ %s 가 %d → %d 로 줄었다 — 볼라에서 통계를 초기화했는지 확인해라' % (code, a, b))


if __name__ == '__main__':
    main()
