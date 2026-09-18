#!/usr/bin/env python3
"""새 현황판(v2)을 옛 대시보드 아티팩트에서 만들어 낸다.

  python3 tools/make_v2.py <옛대시보드.html> [내보낼경로]

옛 대시보드(EGzqReRqxyLWBAZZiLDjKv)가 **원천이고**, 현황판은 그걸 다시 그린 것이다.
그래서 갱신 순서는 늘 이렇다 — 판매·순위·펀딩을 옛 대시보드에 먼저 넣고, 배포한 뒤,
그 파일로 이 스크립트를 돌려 현황판을 다시 만든다. 현황판만 따로 고치면 다음 갱신에 덮인다.

옛 대시보드가 가진 것은 **다 옮긴다** — 판매·광고·순위·펀딩은 물론 인스타·페북·유튜브·
볼라 단축링크·썸네일까지. 썸네일이 base64 라 결과가 7MB 대가 되는데, 그게 빠지면
콘텐츠 줄이 글자 카드로 떨어져서 "메타나 이런 거 다 어디 갔냐"가 된다.

전에는 이 변환을 세션 안에서 손으로 했는데, 그러다 판매만 새로 넣고 펀딩은 옛 값을
남기는 일이 있었다. 한 군데서 다 뽑게 해 두면 그런 어긋남이 생기지 않는다.
"""
import sys, json, os

HERE = os.path.dirname(os.path.abspath(__file__))

# 현황판은 옛 대시보드가 가진 것을 **다 보여 준다**. 그래서 책별 항목도 전부 가져온다.
# (한동안 판매·광고만 가져갔는데, 그러면 "메타는 어디 갔냐"가 된다 — 실제로 그렇게 됐다.)
BOOK_KEYS = ('title', 'short', 'pub', 'hasYp', 'sales', 'daily', 'monthly', 'ads', 'campaigns',
             'platforms', 'igPosts', 'fbPosts', 'igToken', 'dailyFrom', 'dailyNote')

# 책에 딸리지 않은 블록들. 통째로 실어 나른다.
#   thumbs  — 인스타·유튜브·페북·광고 썸네일 (base64, 7MB). 이게 빠지면 콘텐츠 줄이 글자 카드가 된다.
#   adThumb — 광고 소재명 → 썸네일 열쇠
#   igExtra — 게시물별 [프로필활동, 프로필방문, 팔로우, 릴스여부]
#   igFollow— 릴스 팔로우 (인스타 API 가 안 줘서 앱에서 옮긴 값)
#   adsWeek — 최근 7일 소재별 광고 성적. 옛 대시보드는 이 블록을 안 그리지만,
#             거기 얹어 두면 다시 만들 때마다 따라온다 (tools/set_ads_week.py 로 넣는다)
#   ytCollab— 다른 채널과 한 협업·협찬 영상 (썸네일 포함). 다른 세션이 채워 넣는다.
WHOLE = ('econ', 'volaDaily', 'ytData', 'igExtra', 'igFollow', 'adThumb', 'thumbs',
         'adsWeek', 'ytCollab')

# 정가와 공급률은 어느 원천에도 없다 — 계약 조건이라 사람이 적어 두는 값이다.
# 바뀌면 여기를 고친다. 화면의 「예상 정산액」이 이 둘로 계산된다.
LIST_PRICE = {'pyoryu': 22000, 'kaljung': 18000, 'wonsiin': 22000, 'freud': 18000, 'muhan': 18000}
SUPPLY_RATE = 0.65


def block(html, bid, required=True):
    o = '<script id="%s" type="application/json">' % bid
    if o not in html:
        if required:
            sys.exit('옛 대시보드에 %s 블록이 없습니다' % bid)
        return None
    s = html.index(o) + len(o)
    # 블록 안에 </script> 가 들어 있을 수 있다(ranksPy 가 그렇다). JSON 이 되는 자리가 진짜 끝이다.
    e = -1
    while True:
        e = html.find('</script>', s if e < 0 else e + 1)
        if e < 0:
            sys.exit('%s 블록의 끝을 못 찾았습니다' % bid)
        try:
            return json.loads(html[s:e])
        except ValueError:
            pass


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

    out = {
        'collected': P['collected'],
        'order': P['order'],
        'account': P['account'],
        'supplyRate': SUPPLY_RATE,
        'list': {k: LIST_PRICE[k] for k in P['order']},
        'books': books,
        'ranks': KR['books'],
        'rankAsOf': KR.get('asOf'),
        'rankLastTry': KR.get('lastTry'),
        'rankSurfaces': {s['key']: s['label'] for s in KR.get('surfaces') or []},
        'funding': FD,
        # 원천마다 들어오는 속도가 달라서 '기준일' 하나로는 무엇이 밀렸는지 알 수 없다.
        'meta': {k: P.get(k) for k in
                 ('igAcc', 'igNote', 'igFrom', 'igAsOf', 'fbPage', 'fbAsOf', 'generated', 'lastAuto')},
    }
    for b in WHOLE:
        out[b] = block(html, b, required=False)
    return out


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
