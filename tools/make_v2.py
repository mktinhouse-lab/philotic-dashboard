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
import sys, json, os, io, base64, datetime, re

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
#   covers  — 책 표지 (base64). 아티팩트는 외부 이미지를 막으므로 심어야 뜬다.
#   ytData2 — 두 번째 유튜브 채널(1분수업). ytData 와 같은 모양이라 같은 함수가 그린다.
WHOLE = ('econ', 'volaDaily', 'ytData', 'ytData2', 'igExtra', 'igFollow', 'adThumb', 'thumbs',
         'adsWeek', 'ytCollab', 'covers')

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
        'rankHist': KR.get('hist'),
        'rankSurfaces': {s['key']: s['label'] for s in KR.get('surfaces') or []},
        'funding': FD,
        # 원천마다 들어오는 속도가 달라서 '기준일' 하나로는 무엇이 밀렸는지 알 수 없다.
        'meta': {k: P.get(k) for k in
                 ('igAcc', 'igNote', 'igFrom', 'igAsOf', 'fbPage', 'fbAsOf', 'generated', 'lastAuto')},
    }
    for b in WHOLE:
        out[b] = block(html, b, required=False)
    return out


# ── 썸네일 다이어트 ───────────────────────────────────────────────────────
# 원천은 썸네일을 모두 base64 로 들고 있다(2026-10-02 기준 11.6MB). 그대로 거울에
# 옮기면 페이지가 12MB 를 넘고, 그러면 아티팩트가 아예 안 열린다
# ("Couldn't load this Artifact"). 거울은 **화면에 실제로 뜨는 것만** 들고 가면 된다.
#
# 화면이 쓰는 건 블록마다 「조회 많은 순 10장」 두 벌(최근 2주 · 전체)과 타임라인 8장뿐이다.
# 그래서 묶음마다 상위 TOP + 최근 NEW 만 남기고, 남긴 것도 220px JPEG 로 다시 줄인다.
# 버리는 게 아니다 — 원천에는 그대로 있고, 거울만 가볍게 만든다.
TOP, NEW, WIN = 12, 8, 14          # 상위 몇 장 · 최근 몇 장 · 최근 며칠을 '최근'으로 볼지
THUMB_W, THUMB_Q, THUMB_MIN = 220, 60, 6144   # 가로 · 품질 · 이보다 작으면 그대로 둔다
PAGE_WARN, PAGE_STOP = 8, 13       # MB — 넘으면 경고 / 멈춘다


def _pick(rows, ikey, idate, iview):
    """한 묶음에서 화면에 뜰 수 있는 것들의 열쇠."""
    w = (datetime.date.today() - datetime.timedelta(days=WIN)).isoformat()
    rows = [r for r in rows if len(r) > max(ikey, idate, iview) and r[ikey]]
    byv = sorted(rows, key=lambda r: -(r[iview] or 0))
    keep = {r[ikey] for r in byv[:TOP]}
    keep |= {r[ikey] for r in [x for x in byv if str(x[idate])[:10] >= w][:TOP]}
    keep |= {r[ikey] for r in sorted(rows, key=lambda r: str(r[idate]), reverse=True)[:NEW]}
    return keep


def _shrink(uri):
    """220px JPEG 로 다시 굽는다. 못 구우면 원래 것을 그대로 돌려준다."""
    if not isinstance(uri, str) or not uri.startswith('data:') or len(uri) < THUMB_MIN:
        return uri
    try:
        from PIL import Image
        raw = base64.b64decode(uri.split(',', 1)[1])
        im = Image.open(io.BytesIO(raw)).convert('RGB')
        if im.width > THUMB_W:
            im = im.resize((THUMB_W, max(1, round(im.height * THUMB_W / im.width))),
                           Image.LANCZOS)
        o = io.BytesIO()
        im.save(o, 'JPEG', quality=THUMB_Q, optimize=True, progressive=True)
        new = 'data:image/jpeg;base64,' + base64.b64encode(o.getvalue()).decode()
        return new if len(new) < len(uri) else uri
    except Exception:
        return uri


def slim_thumbs(data):
    th = data.get('thumbs')
    if not isinstance(th, dict):
        return
    need = {'ig': set(), 'fb': set(), 'yt': set()}
    for b in (data.get('books') or {}).values():
        ig = b.get('igPosts') or []
        for acc in {p[1] for p in ig if len(p) > 1}:
            need['ig'] |= _pick([p for p in ig if p[1] == acc], 7, 0, 3)
        need['fb'] |= _pick(b.get('fbPosts') or [], 7, 0, 2)
    for bid in ('ytData', 'ytData2'):
        y = data.get(bid) or {}
        for b in (y.get('books') or {}).values():
            need['yt'] |= _pick(b.get('videos') or [], 0, 2, 3)
        need['yt'] |= _pick((y.get('other') or {}).get('videos') or [], 0, 2, 3)

    was = sum(len(str(v)) for k in th if isinstance(th[k], dict) for v in th[k].values())
    for kind, keys in need.items():
        cur = th.get(kind)
        if isinstance(cur, dict):
            th[kind] = {i: _shrink(u) for i, u in cur.items() if i in keys}
    # 광고(ad) 는 수가 적고 광고 탭이 통째로 쓰므로 고르지 않고 줄이기만 한다
    if isinstance(th.get('ad'), dict):
        th['ad'] = {i: _shrink(u) for i, u in th['ad'].items()}
    now = sum(len(str(v)) for k in th if isinstance(th[k], dict) for v in th[k].values())
    th['slimmed'] = True
    print('  썸네일 %.1fMB → %.1fMB (%s)' % (
        was / 1048576, now / 1048576,
        ' · '.join('%s %d장' % (k, len(th[k])) for k in ('ig', 'fb', 'yt', 'ad')
                   if isinstance(th.get(k), dict))))


def main(src, out='v2.html'):
    html = open(src, encoding='utf-8').read()
    data = build_data(html)

    slim_thumbs(data)

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
    mb = len(doc.encode('utf-8')) / 1048576
    if mb > PAGE_STOP:
        sys.exit('검증 실패 페이지가 %.1fMB 입니다 — 이만큼 커지면 아티팩트가 안 열립니다 '
                 '("Couldn\'t load this Artifact"). 썸네일을 더 줄여야 합니다.' % mb)
    if not all(checks.values()):
        sys.exit('검증 실패 %s — 아무것도 쓰지 않았습니다' % checks)
    if mb > PAGE_WARN:
        print('  ⚠ 페이지가 %.1fMB 입니다 — %dMB 를 넘으면 안 열립니다' % (mb, PAGE_STOP))

    open(out, 'w', encoding='utf-8').write(doc)
    last = {k: (v['sales'][-1][0] if v.get('sales') else '–') for k, v in data['books'].items()}
    print('%s · %.0fKB' % (out, len(doc) / 1024))
    print('  기준일 %s · 순위 %s · 펀딩 %s' % (data['collected'], data['rankAsOf'], data['funding'].get('asOf')))
    print('  마지막 판매일 ' + ' / '.join('%s %s' % (k, last[k]) for k in data['order']))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], *sys.argv[2:3])
