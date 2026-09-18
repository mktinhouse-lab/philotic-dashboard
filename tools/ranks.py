#!/usr/bin/env python3
"""교보 순위 수집기 — 클라우드 루틴용 (collect-ranks.js 의 파이썬 이식본)

    python3 ranks.py <html경로>

<html경로> 안의 <script id="kyoboRanks"> 블록을 갈아끼운다. 표준 라이브러리만 쓴다.

설계 원칙 — **실패해도 절대 배포를 막지 않는다.**
교보가 API 키를 갈거나(403) 네트워크가 막히면, 파일을 건드리지 않고 사유만 찍고 exit 0 한다.
순위가 하루 비는 것보다 판매·광고 갱신이 통째로 멈추는 쪽이 훨씬 나쁘다.

hist(순위 추이)는 교보가 과거를 안 주므로 우리가 매일 쌓는다.
날짜 키는 '수집한 날'이 아니라 '집계 기준일'(온라인 일간의 ymw)이다 — 화면에서 "8/23 몇 위"로 읽히려면 그래야 한다.
"""
import sys, json, re, gzip, zlib, urllib.request, urllib.parse, datetime

API_KEY = ('eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0..SAuG7hzFxwWfewcz.gMw0bGwwgB9Xx8Wxz-Y6ihk4IMgSa-5CM-'
           'ZzIdfRNQbqMbvLUmv5-9sRubZjE-iJ-wNPlNbpFnHprd3aMGDrJGqCkUNz3AkvR24a6S18-9PUCOySLlK296YlQwyHKRLDprH1Atq8'
           '.Vy8qyA72gFcghwWdO0q-_A')
BASE = 'https://store.kyobobook.co.kr/api/gw/best/best-seller/'
SCAN_DEPTH, PER = 500, 50

BOOKS = {
    'kaljung': {'title': '칼 융의 내면수업',   'match': '칼 융의 내면수업',   'cat': '인문',     'catCode': 'I', 'path': '인문 > 심리학 > 심리학자 > 융',    'pid': 'S000220665243'},
    'wonsiin': {'title': '완벽한 원시인',      'match': '완벽한 원시인',      'cat': '인문',     'catCode': 'I', 'path': '인문 > 인문학일반 > 인문교양',     'pid': 'S000219310977'},
    'freud':   {'title': '프로이트의 감정수업', 'match': '프로이트의 감정수업', 'cat': '인문',     'catCode': 'I', 'path': '인문 > 심리학 > 교양심리',        'pid': 'S000218149524'},
    'muhan':   {'title': '무한의 부',          'match': '무한의 부',          'cat': '자기계발', 'catCode': 'c', 'path': '자기계발 > 성공/처세 > 성공스토리', 'pid': 'S000214211407'},
}

SURFACES = [
    {'key': 'onlineDaily',     'label': '온라인 일간 · 종합', 'ep': 'online',   'q': {'period': '001', 'dsplDvsnCode': '000', 'dsplTrgtDvsnCode': '001'}, 'deep': True},
    {'key': 'onlineWeekly',    'label': '온라인 주간 · 종합', 'ep': 'online',   'q': {'period': '002', 'dsplDvsnCode': '000', 'dsplTrgtDvsnCode': '001'}, 'deep': True},
    {'key': 'onlineMonthly',   'label': '온라인 월간 · 종합', 'ep': 'online',   'q': {'period': '003', 'dsplDvsnCode': '000', 'dsplTrgtDvsnCode': '001'}, 'deep': True},
    {'key': 'realtime',        'label': '실시간 베스트',      'ep': 'realtime', 'q': {}, 'deep': True},
    {'key': 'steady',          'label': '스테디셀러',         'ep': 'steady',   'q': {}, 'deep': True},
    {'key': 'totalWeeklyAll',  'label': '종합 주간 · 전체',   'ep': 'total',    'q': {'period': '002', 'bsslBksClstCode': 'A'}, 'deep': True},
    {'key': 'totalMonthlyAll', 'label': '종합 월간 · 전체',   'ep': 'total',    'q': {'period': '003', 'bsslBksClstCode': 'A'}, 'deep': True},
    # 분야별 목록은 교보가 20개까지만 준다 — 더 넘겨도 빈 페이지다. 20위 밖은 상품페이지 주간베스트로 본다.
    {'key': 'totalWeeklyCat',  'label': '종합 주간 · 분야',   'ep': 'total',    'q': {'period': '002'}, 'byCat': True},
    {'key': 'totalMonthlyCat', 'label': '종합 월간 · 분야',   'ep': 'total',    'q': {'period': '003'}, 'byCat': True},
    {'key': 'totalAnnualCat',  'label': '종합 연간 · 분야',   'ep': 'total',    'q': {'period': '004'}, 'byCat': True},
]

OPEN = '<script id="kyoboRanks" type="application/json">'


def get(url, headers, timeout=25):
    """응답을 글자로 돌려준다 — 압축돼 오더라도.

    교보 게이트웨이는 Accept-Encoding 을 안 보내도 gzip 으로 답할 때가 있다. 그러면
    raw 바이트를 그대로 decode 하게 되고, json.loads 가 'Expecting value: line 1 column 1'
    로 죽는다. 원인이 순위 없음도 키 만료도 아닌데 그렇게 보여서 며칠을 헤맸다.
    그래서 압축 여부를 헤더가 아니라 **바이트의 첫머리**로도 판단한다 — 헤더가 빠져 오는
    경우가 실제로 있었기 때문이다.
    """
    req = urllib.request.Request(url, headers=dict(headers, **{'accept-encoding': 'gzip, deflate'}))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        enc = (r.headers.get('content-encoding') or '').lower()
        status = r.status
    if enc == 'gzip' or raw[:2] == b'\x1f\x8b':
        raw = gzip.decompress(raw)
    elif enc == 'deflate':
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
    return status, raw.decode('utf-8', 'replace')


def page(ep, q, p):
    qs = dict(q); qs['page'] = str(p); qs['per'] = str(PER)
    url = BASE + ep + '?' + urllib.parse.urlencode(qs)
    try:
        st, body = get(url, {'content-type': 'application/json', 'x-api-gw-key': API_KEY})
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise RuntimeError('교보가 API 키를 거부했습니다 (403) — 키가 갱신된 것으로 보입니다. '
                               'store.kyobobook.co.kr/bestseller/online/daily 의 네트워크 탭에서 '
                               'x-api-gw-key 를 새로 복사해 넣어야 합니다.')
        raise RuntimeError('%s HTTP %s' % (ep, e.code))
    try:
        d = (json.loads(body) or {}).get('data') or {}
    except ValueError:
        # 무엇이 왔는지 적어 둔다. '파싱 실패' 만 남으면 압축인지 오류 페이지인지 알 수 없다.
        raise RuntimeError('%s 응답이 JSON 이 아닙니다 (HTTP %s) — 앞부분: %r'
                           % (ep, st, body[:160]))
    return d.get('bestSeller') or [], d.get('ymw')


def sweep(sf, targets, q):
    found, ymw = {}, None
    maxp = (SCAN_DEPTH + PER - 1) // PER if sf.get('deep') else 1
    for p in range(1, maxp + 1):
        lst, y = page(sf['ep'], q, p)
        if p == 1:
            ymw = y
        if not lst:
            break
        for t in targets:
            if t['key'] in found:
                continue
            for x in lst:
                if t['match'] in str(x.get('cmdtName') or ''):
                    found[t['key']] = {'rank': x.get('prstRnkn'), 'prev': x.get('frmrRnkn')}
                    break
        if len(found) == len(targets):
            break
        if len(lst) < PER:
            break
    return found, ymw


WB = re.compile(r'<span>([^<>]{1,20})<!--\s*-->\s*<span>([\d,]+)</span>위</span>')


def collect():
    out = {k: {'cat': b['cat'], 'path': b['path'], 'pid': b['pid'], 'ranks': {}} for k, b in BOOKS.items()}
    meta = {}
    for sf in SURFACES:
        if sf.get('byCat'):
            bycode = {}
            for k, b in BOOKS.items():
                bycode.setdefault(b['catCode'], []).append({'key': k, 'match': b['match']})
            for code, targets in bycode.items():
                q = dict(sf['q']); q['bsslBksClstCode'] = code
                found, ymw = sweep(sf, targets, q)
                for t in targets:
                    out[t['key']]['ranks'][sf['key']] = found.get(t['key'])
                meta[sf['key']] = ymw
        else:
            targets = [{'key': k, 'match': b['match']} for k, b in BOOKS.items()]
            found, ymw = sweep(sf, targets, sf['q'])
            for t in targets:
                out[t['key']]['ranks'][sf['key']] = found.get(t['key'])
            meta[sf['key']] = ymw
        hits = sum(1 for k in BOOKS if out[k]['ranks'].get(sf['key']))
        print('  %-18s %d/%d권 · %s' % (sf['label'], hits, len(BOOKS), meta.get(sf['key']) or '-'))

    print('  상품 페이지 주간베스트')
    for k, b in BOOKS.items():
        try:
            st, t = get('https://product.kyobobook.co.kr/detail/' + b['pid'], {'user-agent': 'Mozilla/5.0'})
            if '주간베스트' not in t:
                print('    %-14s 주간베스트 표기 없음' % b['title']); continue
            hits = [(m.group(1).strip(), int(m.group(2).replace(',', ''))) for m in WB.finditer(t)]
            ov = next((h for h in hits if h[0] == '국내도서'), None)
            ct = next((h for h in hits if h[0] != '국내도서'), None)
            out[k]['weeklyBest'] = {'overall': ov[1] if ov else None,
                                    'cat': ct[1] if ct else None,
                                    'catName': ct[0] if ct else b['cat']}
            print('    %-14s 국내도서 %s / %s %s' % (b['title'], (str(ov[1]) + '위') if ov else '–',
                                                  b['cat'], (str(ct[1]) + '위') if ct else '–'))
        except Exception as e:
            print('    %-14s 실패: %s' % (b['title'], e))
    return out, meta


def stamp_try(src, html, s, e, ok, why):
    """수집을 시도했다는 사실 자체를 순위 블록에 남긴다.

    실패해도 화면에는 이전 순위가 그대로 보인다. 그래서 '왜 안 바뀌었는지'를 적어두지 않으면,
    열어 본 사람은 순위가 안 움직인 건지 수집이 죽은 건지 구별할 수 없다.
    기존 값은 하나도 건드리지 않고 lastTry 만 덧붙인다."""
    try:
        blk = json.loads(html[s + len(OPEN):e]) or {}
    except Exception:
        return                                   # 블록을 못 읽으면 아무것도 하지 않는다
    kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    blk['lastTry'] = {'at': kst.strftime('%Y-%m-%d %H:%M'), 'ok': bool(ok), 'why': why}
    doc = html[:s] + OPEN + json.dumps(blk, ensure_ascii=False) + '</script>' + html[e + len('</script>'):]
    if doc.count(OPEN) != 1 or 'id="payload"' not in doc or 'id="thumbs"' not in doc:
        return
    try:
        open(src, 'w', encoding='utf-8').write(doc)
        print('     (수집 시도 기록을 남겼습니다 — 화면에 사유가 표시됩니다)')
    except Exception:
        pass


def main():
    if len(sys.argv) < 2:
        print('SKIP 대상 html 경로가 없습니다'); return 0
    src = sys.argv[1]
    try:
        html = open(src, encoding='utf-8').read()
    except Exception as e:
        print('SKIP html 을 못 읽음:', e); return 0
    s = html.find(OPEN)
    if s < 0:
        print('SKIP kyoboRanks 블록이 없습니다 — 순위는 건너뜁니다'); return 0
    e = html.find('</script>', s)

    try:
        out, meta = collect()
    except Exception as ex:
        print('SKIP 순위 수집 실패 —', ex)
        print('     (판매·광고 배포는 그대로 진행합니다. 순위는 이전 값이 유지됩니다.)')
        why = str(ex)
        if 'Tunnel connection failed' in why or 'CONNECT' in why:
            why = ('교보 서버로 나가는 길이 실행 환경의 네트워크 정책에 막혀 있습니다 '
                   '(store.kyobobook.co.kr CONNECT 403). 네트워크가 열린 곳에서 tools/ranks.py 를 돌리거나, '
                   '환경 네트워크 정책에 교보 호스트를 허용해야 합니다.')
        stamp_try(src, html, s, e, False, why[:300])
        return 0

    kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    collected = kst.strftime('%Y-%m-%d %H:%M')
    payload = {
        'asOf': meta.get('onlineDaily'),
        'collected': collected,
        'scanDepth': SCAN_DEPTH,
        'catTop': 20,
        'surfaces': [{'key': s2['key'], 'label': s2['label'],
                      'deep': bool(s2.get('deep')), 'byCat': bool(s2.get('byCat'))} for s2 in SURFACES],
        'periods': meta,
        'books': out,
        'lastTry': {'at': collected, 'ok': True, 'why': ''},
    }

    # 이전 hist 를 이어받는다 — 못 읽으면 새로 시작하되 그 사실을 찍는다
    hist = {}
    try:
        hist = (json.loads(html[s + len(OPEN):e]) or {}).get('hist') or {}
    except Exception:
        print('  (이전 hist 를 못 읽어 새로 시작합니다)')

    a = payload['asOf']
    today = (a[0:4] + '-' + a[4:6] + '-' + a[6:8]) if (a and len(str(a)) == 8) else collected[:10]
    hist[today] = {}
    for k in BOOKS:
        row = {}
        for sf in SURFACES:
            r = out[k]['ranks'].get(sf['key'])
            if r and r.get('rank') is not None:
                row[sf['key']] = r['rank']
        wb = out[k].get('weeklyBest') or {}
        if wb.get('overall') is not None:
            row['wbOverall'] = wb['overall']
        if wb.get('cat') is not None:
            row['wbCat'] = wb['cat']
        hist[today][k] = row

    # 교보가 주는 '전일 순위'로 어제 하루만 채운다. 이미 있는 날은 덮지 않는다.
    yd = (datetime.date(int(today[0:4]), int(today[5:7]), int(today[8:10])) - datetime.timedelta(days=1)).isoformat()
    hist.setdefault(yd, {})
    for k in BOOKS:
        p = (out[k]['ranks'].get('onlineDaily') or {}).get('prev')
        if p in (None, 0):
            continue
        prev_row = hist[yd].get(k) or {}
        merged = {'onlineDaily': p}
        merged.update(prev_row)
        hist[yd][k] = merged
    if not hist[yd]:
        del hist[yd]

    days = sorted(hist)
    for d in days[:max(0, len(days) - 400)]:
        del hist[d]
    payload['hist'] = hist

    block = OPEN + json.dumps(payload, ensure_ascii=False) + '</script>'
    doc = html[:s] + block + html[e + len('</script>'):]

    checks = {
        'payload 유지': 'id="payload"' in doc,
        'volaDaily 유지': 'id="volaDaily"' in doc,
        'thumbs 유지': 'id="thumbs"' in doc,
        'kyoboRanks 1회': doc.count(OPEN) == 1,
        '기준일 있음': bool(payload['asOf']),
        '길이': len(doc) > 100000,
    }
    print('  순위 기록:', len(hist), '일치 (오늘 포함) · 기준', payload['asOf'], '· 수집', collected)
    for k, b in BOOKS.items():
        r = out[k]['ranks']
        f = lambda x: (str(r[x]['rank']) + '위') if r.get(x) else '–'
        print('    %-14s 일간 %s / 주간 %s / 종합주간 %s %s / 실시간 %s'
              % (b['title'], f('onlineDaily'), f('onlineWeekly'), b['cat'], f('totalWeeklyCat'), f('realtime')))
    print('  검증:', checks)
    if not all(checks.values()):
        print('SKIP 검증 실패 — 순위 블록을 바꾸지 않습니다'); return 0
    open(src, 'w', encoding='utf-8').write(doc)
    print('RANKS_OK 길이=', len(doc))
    return 0


if __name__ == '__main__':
    sys.exit(main())
