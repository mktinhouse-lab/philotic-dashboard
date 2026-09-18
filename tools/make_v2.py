#!/usr/bin/env python3
"""새 현황판(v2)을 옛 대시보드 아티팩트에서 만들어 낸다.

  python3 tools/make_v2.py <옛대시보드.html> [내보낼경로]

옛 대시보드(EGzqReRqxyLWBAZZiLDjKv)가 **원천이고**, 현황판은 그걸 다시 그린 것이다.
그래서 갱신 순서는 늘 이렇다 — 판매·순위·펀딩을 옛 대시보드에 먼저 넣고, 배포한 뒤,
그 파일로 이 스크립트를 돌려 현황판을 다시 만든다. 현황판만 따로 고치면 다음 갱신에 덮인다.

옛 대시보드에서 뽑아 쓰는 블록은 payload · kyoboRanks · funding 세 개뿐이다.
썸네일(7MB)·볼라·인스타 원본은 현황판이 안 쓰므로 가져오지 않는다 — 그래서 120KB 로 끝난다.

전에는 이 변환을 세션 안에서 손으로 했는데, 그러다 판매만 새로 넣고 펀딩은 옛 값을
남기는 일이 있었다. 한 군데서 다 뽑게 해 두면 그런 어긋남이 생기지 않는다.
"""
import sys, json, os

HERE = os.path.dirname(os.path.abspath(__file__))

# 현황판이 쓰는 책별 항목만 추린다. payload 에는 인스타·페북 게시물 원본도 있는데
# 현황판은 그걸 안 보여 주므로 넣지 않는다 (넣으면 파일만 세 배가 된다).
BOOK_KEYS = ('title', 'short', 'pub', 'hasYp', 'sales', 'daily', 'monthly', 'ads', 'campaigns')

# 정가와 공급률은 어느 원천에도 없다 — 계약 조건이라 사람이 적어 두는 값이다.
# 바뀌면 여기를 고친다. 화면의 「예상 정산액」이 이 둘로 계산된다.
LIST_PRICE = {'pyoryu': 22000, 'kaljung': 18000, 'wonsiin': 22000, 'freud': 18000, 'muhan': 18000}
SUPPLY_RATE = 0.65


def block(html, bid):
    o = '<script id="%s" type="application/json">' % bid
    s = html.index(o) + len(o)
    e = html.index('</script>', s)
    return json.loads(html[s:e])


def build_data(html):
    P = block(html, 'payload')
    KR = block(html, 'kyoboRanks')
    FD = block(html, 'funding')

    books = {}
    for k, b in P['books'].items():
        books[k] = {x: b.get(x) for x in BOOK_KEYS}

    missing = [k for k in P['order'] if k not in LIST_PRICE]
    if missing:
        sys.exit('정가를 모르는 책이 있습니다: %s — tools/make_v2.py 의 LIST_PRICE 에 적어 주세요'
                 % ', '.join(missing))

    return {
        'collected': P['collected'],
        'order': P['order'],
        'account': P['account'],
        'supplyRate': SUPPLY_RATE,
        'list': {k: LIST_PRICE[k] for k in P['order']},
        'books': books,
        'ranks': KR['books'],
        'rankAsOf': KR.get('asOf'),
        'rankSurfaces': {s['key']: s['label'] for s in KR.get('surfaces') or []},
        'funding': FD,
    }


def main(src, out='v2.html'):
    html = open(src, encoding='utf-8').read()
    data = build_data(html)

    head = open(os.path.join(HERE, 'v2', 'head.html'), encoding='utf-8').read()
    body = open(os.path.join(HERE, 'v2', 'body.html'), encoding='utf-8').read()
    if '__DATA__' not in body:
        sys.exit('tools/v2/body.html 에 __DATA__ 자리가 없습니다')

    enc = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    # 데이터에 </script> 가 섞이면 블록이 조기 종료되고 뒷부분이 화면에 글로 샌다.
    # 판매 메모는 사람이 적는 칸이라 언제든 들어올 수 있다. (옛 대시보드에서 실제로 겪었다)
    enc = enc.replace('</script', r'<\/script')
    doc = head + body.replace('__DATA__', enc)

    checks = {
        'v2 블록 1회': doc.count('<script id="v2"') == 1,
        '데이터 자리 없음': '__DATA__' not in doc,
        '기준일 있음': bool(data['collected']),
        '책 다섯 권': len(data['books']) == len(data['order']),
    }
    if not all(checks.values()):
        sys.exit('검증 실패 %s — 아무것도 쓰지 않았습니다' % checks)

    open(out, 'w', encoding='utf-8').write(doc)
    last = {k: (v['sales'][-1][0] if v.get('sales') else '–') for k, v in data['books'].items()}
    print('%s · %.0fKB' % (out, len(doc) / 1024))
    print('  기준일 %s · 순위 %s · 펀딩 %s' % (data['collected'], data['rankAsOf'], data['funding'].get('asOf')))
    print('  마지막 판매일 ' + ' / '.join('%s %s' % (k, last[k]) for k in data['order']))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], *sys.argv[2:3])
