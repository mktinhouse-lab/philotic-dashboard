#!/usr/bin/env python3
"""교보 바로펀딩 모금액을 손으로 넣는다.

  python3 tools/set_funding.py <html경로> <프로젝트> <모금액> [기준일시]

  예: python3 tools/set_funding.py dash.html pyoryu 4120000

교보 펀딩 서버(event.kyobobook.co.kr)도 클라우드 세션에서 막혀 있다. 그런데 펀딩은
마감이 있는 숫자라 하루만 묵어도 달성률·예상 도달액이 어긋난다. 펀딩 페이지에서 읽은
모금액 하나만 넣으면 나머지(달성률·적립 단계·일평균·예상 최종)는 화면이 다시 계산한다.

hist 에 날짜별로 쌓아 두므로, 며칠 이어 넣으면 모금 추이가 남는다.
"""
import sys, json, datetime

OPEN = '<script id="funding" type="application/json">'


def main(path, key, raised, at=None):
    raised = int(str(raised).replace(',', '').replace('원', '').strip())
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    at = at or now.strftime('%Y-%m-%d %H:%M')

    html = open(path, encoding='utf-8').read()
    s = html.index(OPEN) + len(OPEN)
    e = html.index('</script>', s)
    FD = json.loads(html[s:e])

    p = (FD.get('projects') or {}).get(key)
    if not p:
        sys.exit('그런 펀딩이 없습니다: %s (있는 것: %s)' % (key, ', '.join(FD.get('projects') or {})))

    before, beforePct = p.get('raised'), p.get('pct')
    p['raised'] = raised
    p['pct'] = round(raised / p['goal'] * 100) if p.get('goal') else p.get('pct')
    p.setdefault('hist', {})[at[:10]] = raised
    # daysLeft 는 화면이 마감일에서 다시 세므로 굳이 맞추지 않지만, 옛 값이 남아 헷갈리지 않게 지운다
    try:
        to = datetime.date(*map(int, p['to'].split('-')))
        p['daysLeft'] = max(0, (to - now.date()).days)
        p['done'] = now.date() > to
    except Exception:
        pass
    FD['asOf'] = at

    open(path, 'w', encoding='utf-8').write(html[:s] + json.dumps(FD, ensure_ascii=False) + html[e:])
    print('%s · 모금액 %s → %s원 · 달성률 %s%% → %s%% · D-%s (기준 %s)'
          % (key, format(before or 0, ','), format(raised, ','), beforePct, p['pct'], p.get('daysLeft'), at))


if __name__ == '__main__':
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    main(*sys.argv[1:5])
