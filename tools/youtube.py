#!/usr/bin/env python3
"""「1분지혜」 유튜브 수집기 — 클라우드 루틴용

    python3 youtube.py <html경로>

<html경로> 안의 <script id="ytData"> 블록을 갈아끼운다. 표준 라이브러리만 쓴다.
로그인·자격증명·개인 API 키를 쓰지 않는다 — 공개 페이지만 본다.

설계 원칙은 tools/ranks.py 와 같다 — **실패해도 절대 배포를 막지 않는다.**
유튜브가 마크업을 바꾸거나 네트워크가 막히면 파일을 건드리지 않고 사유만 찍고 exit 0 한다.
유튜브가 하루 비는 것보다 판매·광고 갱신이 통째로 멈추는 쪽이 훨씬 나쁘다.

── 무엇을 어디서 긁는가 ────────────────────────────────────────────────
1) 채널 목록 (영상 id · 제목 · 쇼츠 여부)
   https://www.youtube.com/channel/<id>/videos  와  /shorts 의 HTML 안
   `ytInitialData = {...}` 덩어리. 한 번에 ~48편만 오고 나머지는
   continuationItemRenderer 의 토큰으로 이어받는다. 이어받기는 공개 페이지가
   자기 스크롤에 쓰는 것과 같은 /youtubei/v1/browse 다. 키(INNERTUBE_API_KEY)는
   페이지 HTML에 그대로 박혀 있는 공개 상수라서 우리가 발급받는 자격증명이 아니다.
2) 채널 규모 (구독자 · 영상 수 · 총 조회수)
   /about 의 aboutChannelViewModel — subscriberCountText / videoCountText / viewCountText.
   구독자는 유튜브가 공개 화면에서 반올림해 준다("2.88만명") → subsApprox=true.
   총 조회수는 정확한 값("조회수 17,387,343회")으로 온다.
3) 영상별 조회수 · 올린 날짜 · 좋아요
   /youtubei/v1/next (videoId) 의 응답. 목록 쪽 숫자는 "조회수 8.9만회" 처럼
   줄여서 오므로 쓰지 않는다 — 여기 videoViewCountRenderer.viewCount 가
   "조회수 866,402회" 로 정확하다. 날짜도 dateText 가 "2026. 8. 24." 로 확정이다.

   **시간대를 반드시 넘겨야 한다.** context.client 에 timeZone=Asia/Seoul,
   utcOffsetMinutes=540 을 안 넣으면 컨테이너 아이피(미국)로 판정해서 dateText 가
   하루 빠르게 온다 — 기존 자료와 하루씩 어긋난다. 실제로 겪은 일이다.

── 못 받는 값 ──────────────────────────────────────────────────────────
댓글 수 · 저장 수 · 공유 수는 공개 화면에 없다. 댓글은 commentsHeaderRenderer 에
개수가 없고(세려면 댓글을 전부 넘겨받아야 한다), 저장·공유는 유튜브 스튜디오
애널리틱스 지표다. 그래서 **기존 값을 그대로 들고 간다.** 이번에 처음 본 영상만
그 자리를 None(화면에서 '–')으로 비운다 — 0 으로 채우면 '실적 0' 으로 읽힌다.
일별 시계열(chDaily · books[*].daily)도 애널리틱스라 손대지 않는다.

── 유튜브가 마크업을 바꾸면 어디를 보나 ────────────────────────────────
한 군데에만 기대지 않도록 짰지만, 그래도 빗나가면 아래 순서로 본다.
 * 영상이 0편으로 잡힌다 → GRID_KEYS / parse_grid_item.
   목록 칸이 shortsLockupViewModel → lockupViewModel → videoRenderer 로
   몇 번 바뀌었다. 세 가지를 다 보지만 네 번째가 나올 수 있다.
   `python3 tools/youtube.py --dump` 로 어떤 Renderer 키가 몇 개 오는지 찍어 본다.
 * 48편에서 멈춘다 → find_continuation (continuationItemRenderer 경로).
 * 조회수가 None → VIEW_PATHS / parse_detail 의 videoViewCountRenderer.
 * 날짜가 하루씩 어긋난다 → ctx() 의 timeZone / utcOffsetMinutes.
 * 구독자·총 조회수가 None → about_channel 의 aboutChannelViewModel 키 이름.
 * 전부 실패하면 블록은 그대로 두고 lastTry 에 사유만 남는다 — 화면에 뜬다.
"""
import sys, os, json, re, gzip, zlib, time, datetime, urllib.request, urllib.error

CHANNEL_ID = 'UC_eCtsz2CxxDgTzev6kroOQ'
OPEN = '<script id="ytData" type="application/json">'

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36')

# 목록을 받아 올 탭. /videos 와 /shorts 는 겹치는 영상이 많지만 한쪽에만 있는 것도
# 있어서 둘 다 받고 id 로 합친다. 쇼츠 여부는 어느 탭에서 왔는지로 가른다.
TABS = [('videos', False), ('shorts', True)]

MIN_WANT = 60          # 최소 이만큼은 받아야 한다 (못 받으면 받은 만큼 쓰고 보고한다)
PAGE_CAP = 12          # 탭별 이어받기 횟수 상한 — 무한루프 방지
DETAIL_CAP = 400       # 영상 상세를 받아 올 최대 편수
DETAIL_PAUSE = 0.15    # 상세 요청 사이 숨 고르기

# 제목에 박힌 책 이름으로 도서를 가른다. 기존 자료가 그렇게 갈라져 있다.
# 띄어쓰기가 제각각이라("칼 융의 내면수업" / "칼융의내면수업") **공백을 모두 지운 뒤**
# 비교한다. 오타 변형이 있는 건 공통 토막으로 잡는다
# ("우리는 서로의/서로에게 전부이자 지옥이었다" → '전부이자지옥').
BOOKS = [
    ('kaljung', ['칼융의내면수업']),
    ('wonsiin', ['완벽한원시인']),
    ('freud',   ['프로이트의감정수업']),
    ('muhan',   ['무한의부']),
    ('pyoryu',  ['전부이자지옥']),
]

# 영상 한 줄의 자리 — 기존 블록과 같은 순서를 지킨다.
#   [0]=id [1]=제목 [2]=올린날 [3]=조회 [4]=좋아요 [5]=댓글 [6]=저장 [7]=쇼츠여부
# [8] 은 우리가 덧붙인 것: 1 이면 올린날이 "3일 전" 같은 상대표기를 환산한 **추정값**이다.
# 화면은 [0]~[7] 만 읽으므로 뒤에 붙여도 안전하다.
I_ID, I_TITLE, I_DATE, I_VIEWS, I_LIKES, I_CMTS, I_SAVES, I_SHORT, I_APPROX = range(9)


# ───────────────────────── 그릇: HTTP · JSON ─────────────────────────

def _inflate(raw, enc):
    """압축을 푼다 — 헤더가 아니라 **바이트 첫머리**로도 판단한다.

    유튜브는 accept-encoding 을 안 보내도 gzip 으로 답할 때가 있고, 그러면 raw 를
    그대로 decode 해서 json.loads 가 'Expecting value: line 1 column 1' 로 죽는다.
    (ranks.py 가 교보에서 똑같이 데인 자리다.)"""
    if enc == 'gzip' or raw[:2] == b'\x1f\x8b':
        return gzip.decompress(raw)
    if enc == 'deflate':
        try:
            return zlib.decompress(raw)
        except zlib.error:
            return zlib.decompress(raw, -zlib.MAX_WBITS)
    return raw


def http(url, data=None, headers=None, timeout=30, tries=3):
    hd = {'user-agent': UA, 'accept-language': 'ko-KR,ko;q=0.9',
          'accept-encoding': 'gzip, deflate',
          # hl/gl/tz 를 쿠키로도 못 박는다. HTML 경로는 context 를 못 넘기므로
          # 이쪽이 유일한 수단이다.
          'cookie': 'PREF=hl=ko&gl=KR&tz=Asia.Seoul'}
    if data is None:
        hd['accept'] = 'text/html,application/xhtml+xml,*/*;q=0.8'
    else:
        hd['content-type'] = 'application/json'
    hd.update(headers or {})
    last = None
    for a in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=hd)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = _inflate(r.read(), (r.headers.get('content-encoding') or '').lower())
            return raw.decode('utf-8', 'replace')
        except Exception as e:            # 네트워크는 가끔 그냥 흔들린다
            last = e
            if a + 1 < tries:
                time.sleep(1.5 * (a + 1))
    raise RuntimeError('%s 요청 실패: %s' % (url.split('?')[0], last))


def grab(html, name):
    """`name = {...}` 를 **중괄호 균형**으로 끊어 읽는다.

    `ytInitialData\\s*=\\s*(\\{.*?\\})` 같은 정규식은 JSON 안에 중괄호가 있으면
    중간에서 잘린다. 문자열 리터럴과 역슬래시 이스케이프를 넘기면서 깊이를 센다.
    같은 이름이 여러 번 나오면(유튜브는 보통 2번 박는다) 파싱되는 첫 덩어리를 쓴다."""
    for m in re.finditer(re.escape(name) + r'\s*=\s*\{', html):
        i = m.end() - 1
        depth, instr, esc = 0, False, False
        for j in range(i, len(html)):
            c = html[j]
            if instr:
                if esc:
                    esc = False
                elif c == '\\':
                    esc = True
                elif c == '"':
                    instr = False
                continue
            if c == '"':
                instr = True
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(html[i:j + 1])
                    except ValueError:
                        break
    return None


def walk(node, want):
    """중첩 구조를 훑어 `want` 라는 키의 값을 모두 모은다.

    유튜브는 같은 칸을 감싸는 껍데기 경로를 수시로 바꾼다. 경로를 외우지 않고
    **키 이름만** 찾으면 껍데기가 바뀌어도 살아남는다."""
    out = []
    stack = [node]
    while stack:
        o = stack.pop()
        if isinstance(o, dict):
            for k, v in o.items():
                if k == want:
                    out.append(v)
                stack.append(v)
        elif isinstance(o, list):
            stack.extend(o)
    return out


def texts(node):
    """노드 안의 사람이 읽는 글자를 모두 긁어 모은다 (simpleText / runs / content).

    숫자 하나를 꺼낼 때 'a.b.c.simpleText' 를 외워 두면 유튜브가 runs 로 바꾸는
    순간 None 이 된다. 그래서 글자를 다 모아 놓고 **글자 모양**으로 찾는다."""
    out = []
    stack = [node]
    while stack:
        o = stack.pop()
        if isinstance(o, str):
            out.append(o)
        elif isinstance(o, dict):
            for k, v in o.items():
                if k in ('simpleText', 'content', 'label', 'accessibilityText', 'title', 'text'):
                    if isinstance(v, str):
                        out.append(v)
                        continue
                stack.append(v)
        elif isinstance(o, list):
            stack.extend(o)
    return out


# ───────────────────────── 숫자 · 날짜 풀기 ─────────────────────────

UNITS = [('억', 100000000), ('만', 10000), ('천', 1000)]


def korean_num(s):
    """"8.9만" · "2.88만" · "17,387,343" · "1.2억" → 정수. 못 읽으면 None.

    줄인 글자는 반올림된 값이라 정확하지 않다 — 정확한 값이 따로 오는 자리에서는
    그쪽을 먼저 쓰고, 여기는 마지막 수단이다."""
    if s is None:
        return None
    t = str(s).replace(',', '').replace(' ', '')
    m = re.search(r'(\d+(?:\.\d+)?)\s*([억만천]?)', t)
    if not m:
        return None
    v = float(m.group(1))
    for u, mul in UNITS:
        if m.group(2) == u:
            v *= mul
            break
    return int(round(v))


def exact_num(s):
    """쉼표만 든 **정확한** 숫자만 받는다. 줄인 글자(만/천/억)면 None.

    "조회수 866,402회" 는 받고 "조회수 86만회" 는 거른다 — 반올림된 값을
    확정값처럼 쓰지 않기 위해서다."""
    if s is None:
        return None
    t = str(s)
    if re.search(r'[억만천]', t):
        return None
    m = re.search(r'(\d[\d,]*)', t)
    return int(m.group(1).replace(',', '')) if m else None


def parse_abs_date(s):
    """"2026. 8. 24." / "2026년 8월 24일" → "2026-08-24". 아니면 None."""
    if not s:
        return None
    m = re.search(r'(20\d\d)\s*[.년]\s*(\d{1,2})\s*[.월]\s*(\d{1,2})', str(s))
    if not m:
        return None
    y, mo, d = (int(x) for x in m.groups())
    try:
        return datetime.date(y, mo, d).isoformat()
    except ValueError:
        return None


REL = [(r'(\d+)\s*년', 365), (r'(\d+)\s*개월', 30), (r'(\d+)\s*주', 7),
       (r'(\d+)\s*일', 1)]


def parse_rel_date(s, today):
    """"3일 전" · "2개월 전" → 오늘에서 빼서 날짜로. **추정값이다.**

    달·해는 길이가 제각각이고 유튜브가 내림해서 주므로 며칠씩 틀린다. 그래서
    이 경로로 만든 날짜는 호출한 쪽에서 approx 로 표시한다 — 지어낸 날짜를
    확정값처럼 쓰지 않기 위해서다. '몇 시간 전/방금'은 오늘로 본다."""
    if not s:
        return None
    t = str(s)
    if '전' not in t and '방금' not in t:
        return None
    if re.search(r'방금|초\s*전|분\s*전|시간\s*전', t):
        return today.isoformat()
    for pat, days in REL:
        m = re.search(pat, t)
        if m:
            return (today - datetime.timedelta(days=int(m.group(1)) * days)).isoformat()
    return None


def book_of(title):
    """제목에 박힌 책 이름으로 도서 키를 고른다. 못 가르면 None → other."""
    flat = re.sub(r'\s+', '', title or '')
    for key, pats in BOOKS:
        for p in pats:
            if p in flat:
                return key
    return None


# ───────────────────────── 이너튜브 ─────────────────────────

class Tube(object):
    """공개 페이지가 자기 스크롤에 쓰는 /youtubei/v1 경로.

    키와 클라이언트 버전은 채널 페이지 HTML에 박혀 있는 공개 상수를 그대로 읽는다 —
    우리가 발급받거나 보관하는 자격증명이 아니다. 로그인 쿠키는 보내지 않는다."""

    def __init__(self):
        self.key = None
        self.ver = None

    def boot(self, html):
        k = re.search(r'"INNERTUBE_API_KEY":\s*"([^"]+)"', html)
        v = re.search(r'"INNERTUBE_CLIENT_VERSION":\s*"([^"]+)"', html)
        if not k or not v:
            raise RuntimeError('채널 페이지에서 INNERTUBE_API_KEY / CLIENT_VERSION 을 '
                               '못 찾았습니다 — 유튜브가 페이지 구성을 바꾼 것으로 보입니다')
        self.key, self.ver = k.group(1), v.group(1)

    def ctx(self):
        # timeZone / utcOffsetMinutes 가 핵심이다 — 안 넘기면 날짜가 하루 어긋난다.
        return {'client': {'clientName': 'WEB', 'clientVersion': self.ver,
                           'hl': 'ko', 'gl': 'KR',
                           'timeZone': 'Asia/Seoul', 'utcOffsetMinutes': 540}}

    def post(self, ep, body, tries=3):
        data = json.dumps(dict(body, context=self.ctx())).encode('utf-8')
        url = 'https://www.youtube.com/youtubei/v1/%s?key=%s' % (ep, self.key)
        body_s = http(url, data=data, tries=tries,
                      headers={'x-youtube-client-name': '1',
                               'x-youtube-client-version': self.ver})
        try:
            return json.loads(body_s)
        except ValueError:
            raise RuntimeError('%s 응답이 JSON 이 아닙니다 — 앞부분: %r' % (ep, body_s[:160]))


# ───────────────────────── 목록 긁기 ─────────────────────────

# 목록 한 칸이 들어 있을 수 있는 키들. 유튜브는 이 칸을
# videoRenderer → gridVideoRenderer → lockupViewModel → shortsLockupViewModel
# 로 몇 번 갈았다. 하나만 보면 다음에 바뀔 때 0편이 된다.
GRID_KEYS = ['shortsLockupViewModel', 'lockupViewModel', 'videoRenderer',
             'gridVideoRenderer', 'reelItemRenderer']


def parse_grid_item(kind, it, is_shorts_tab, today):
    """목록 한 칸 → {id, title, date?, approx?, views?, shorts}. 못 읽으면 None.

    목록의 조회수는 "조회수 8.9만회" 처럼 줄여서 오므로 **임시값**이다.
    상세(next)에서 정확한 값을 받아 덮는다."""
    blob = json.dumps(it, ensure_ascii=False)

    vid = None
    for v in walk(it, 'videoId'):
        if isinstance(v, str) and re.match(r'^[\w-]{11}$', v):
            vid = v
            break
    if not vid:                                  # shortsLockup 은 entityId 에 들어 있다
        m = re.search(r'shorts-shelf-item-([\w-]{11})', blob)
        if m:
            vid = m.group(1)
    if not vid:
        m = re.search(r'"url"\s*:\s*"/(?:shorts/|watch\?v=)([\w-]{11})', blob)
        if m:
            vid = m.group(1)
    if not vid:
        return None

    cand = texts(it)
    title = None
    # overlayMetadata.primaryText / title 쪽이 가장 깨끗하다
    for src in (it.get('overlayMetadata') if isinstance(it, dict) else None, it):
        for t in texts(src or {}):
            if t and len(t) > 6 and '조회수' not in t and '재생' not in t and '전' != t:
                title = t
                break
        if title:
            break
    if not title:
        # accessibilityText("제목, 조회수 3.3천회 - Shorts 동영상 재생") 에서 떼어낸다
        for t in cand:
            if '조회수' in t and ',' in t:
                title = t.split(', 조회수')[0].strip()
                break
    if not title:
        return None

    views = None
    for t in cand:
        if '조회수' in t:
            views = korean_num(t.replace('조회수', ''))
            break

    date, approx = None, False
    for t in cand:
        d = parse_abs_date(t)
        if d:
            date = d
            break
    if not date:
        for t in cand:
            d = parse_rel_date(t, today)
            if d:
                date, approx = d, True
                break

    shorts = 1 if (is_shorts_tab or kind in ('shortsLockupViewModel', 'reelItemRenderer')
                   or '/shorts/' in blob) else 0
    return {'id': vid, 'title': title, 'views': views,
            'date': date, 'approx': approx, 'shorts': shorts}


# 목록이 담긴 그릇. 여기로 **범위를 좁히는 게 중요하다** — 채널 페이지에는
# 「정보」 패널 같은 다른 continuationItemRenderer 도 2개 더 들어 있어서,
# 페이지 전체에서 토큰을 찾으면 그 패널 토큰을 집어 영상 0편을 받는다. 실제로 겪었다.
GRID_ROOT_KEYS = ['richGridRenderer', 'gridRenderer', 'itemSectionRenderer']


def grid_root(data):
    """영상 격자 노드를 돌려준다. 못 찾으면 받은 것 전체를 그대로 쓴다."""
    for k in GRID_ROOT_KEYS:
        got = walk(data, k)
        for g in got:
            if walk(g, 'continuationItemRenderer') or any(walk(g, x) for x in GRID_KEYS):
                return g
    return data


def next_items(resp):
    """이어받기 응답에서 **덧붙일 칸들만** 꺼낸다 (appendContinuationItemsAction)."""
    items = []
    for a in walk(resp, 'appendContinuationItemsAction'):
        if isinstance(a, dict):
            items.extend(a.get('continuationItems') or [])
    for a in walk(resp, 'reloadContinuationItemsCommand'):
        if isinstance(a, dict):
            items.extend(a.get('continuationItems') or [])
    return items if items else resp


def find_continuation(node):
    """다음 쪽 토큰. **격자 안에서만** 찾는다 — 범위를 넓히면 엉뚱한 패널을 집는다."""
    for c in walk(node, 'continuationItemRenderer'):
        if isinstance(c, dict) and c.get('trigger') not in (
                None, 'CONTINUATION_TRIGGER_ON_ITEM_SHOWN'):
            continue
        for t in walk(c, 'token'):
            if isinstance(t, str) and len(t) > 20:
                return t
    for t in walk(node, 'continuationCommand'):
        tok = t.get('token') if isinstance(t, dict) else None
        if isinstance(tok, str) and len(tok) > 20:
            return tok
    return None


def collect_grid(tube, tab, is_shorts_tab, today, log):
    """한 탭을 끝까지(또는 PAGE_CAP 까지) 받아 영상 목록을 돌려준다."""
    url = 'https://www.youtube.com/channel/%s/%s' % (CHANNEL_ID, tab)
    html = http(url)
    if not tube.key:
        tube.boot(html)
    data = grab(html, 'ytInitialData')
    if data is None:
        raise RuntimeError('%s 탭에서 ytInitialData 를 못 찾았습니다 — '
                           '유튜브가 페이지 구성을 바꾼 것으로 보입니다' % tab)

    rows, seen, pages = [], set(), 0
    node = grid_root(data)
    while True:
        got = 0
        for k in GRID_KEYS:
            for it in walk(node, k):
                r = parse_grid_item(k, it, is_shorts_tab, today)
                if r and r['id'] not in seen:
                    seen.add(r['id'])
                    rows.append(r)
                    got += 1
        tok = find_continuation(node)
        pages += 1
        log('    %s 쪽%d: +%d편 (누적 %d)' % (tab, pages, got, len(rows)))
        if not tok or pages >= PAGE_CAP or got == 0:
            if tok and pages >= PAGE_CAP:
                log('    %s 이어받기 상한(%d쪽)에서 멈췄습니다' % (tab, PAGE_CAP))
            break
        node = next_items(tube.post('browse', {'continuation': tok}))
    return rows, data


# ───────────────────────── 채널 규모 ─────────────────────────

def about_channel(log):
    """구독자 · 영상 수 · 총 조회수. 못 읽은 값은 None 으로 둔다 (지어내지 않는다)."""
    html = http('https://www.youtube.com/channel/%s/about' % CHANNEL_ID)
    data = grab(html, 'ytInitialData')
    out = {'title': None, 'handle': None, 'subs': None, 'subsApprox': True,
           'videos': None, 'views': None}
    if data is None:
        log('    about: ytInitialData 를 못 찾았습니다 — 채널 규모는 이전 값을 둡니다')
        return out

    for md in walk(data, 'channelMetadataRenderer'):
        if isinstance(md, dict) and md.get('title'):
            out['title'] = md['title']
            break

    av = (walk(data, 'aboutChannelViewModel') or [None])[0]
    if isinstance(av, dict):
        sub = av.get('subscriberCountText')
        out['subs'] = korean_num(sub)
        # 유튜브가 "구독자 28,800명" 처럼 정확히 줄 때도 있다 — 그러면 반올림이 아니다
        out['subsApprox'] = exact_num(sub) is None
        out['videos'] = korean_num(av.get('videoCountText'))
        # 총 조회수는 정확한 값만 쓴다. 줄여서 오면 비워 둔다.
        out['views'] = exact_num(av.get('viewCountText'))
    else:
        log('    about: aboutChannelViewModel 이 없습니다 — 구독자·총조회수는 이전 값을 둡니다')

    for h in walk(data, 'pageHeaderViewModel'):
        for t in texts(h):
            if t.startswith('@') and len(t) < 40:
                out['handle'] = t
                break
        if out['handle']:
            break
    if out['videos'] is None or out['subs'] is None:
        for h in walk(data, 'pageHeaderViewModel'):
            for t in texts(h):
                if out['subs'] is None and '구독자' in t:
                    out['subs'] = korean_num(t)
                if out['videos'] is None and '동영상' in t:
                    out['videos'] = korean_num(t)
    return out


# ───────────────────────── 영상 상세 ─────────────────────────

def parse_detail(resp, today):
    """next 응답 → {views, date, approx, likes}. 못 읽은 값은 None."""
    out = {'views': None, 'date': None, 'approx': False, 'likes': None}

    # 조회수 — videoViewCountRenderer.viewCount 가 정확한 값이다.
    # shortViewCount("조회수 86만회") 는 반올림이라 쓰지 않는다.
    for vc in walk(resp, 'videoViewCountRenderer'):
        if not isinstance(vc, dict):
            continue
        n = exact_num(' '.join(texts(vc.get('viewCount') or {})))
        if n is not None:
            out['views'] = n
            break
    if out['views'] is None:                       # 마지막 수단 — 줄인 값이라도
        for t in texts(resp):
            if '조회수' in t and '회' in t:
                out['views'] = korean_num(t.replace('조회수', ''))
                if out['views'] is not None:
                    break

    # 날짜 — dateText / publishDate 가 "2026. 8. 24." 로 확정이다
    for key in ('dateText', 'publishDate'):
        for n in walk(resp, key):
            d = parse_abs_date(' '.join(texts(n)))
            if d:
                out['date'] = d
                break
        if out['date']:
            break
    if not out['date']:                            # 상대표기만 오면 환산하고 추정 표시
        for key in ('relativeDateText', 'publishedTimeText'):
            for n in walk(resp, key):
                d = parse_rel_date(' '.join(texts(n)), today)
                if d:
                    out['date'], out['approx'] = d, True
                    break
            if out['date']:
                break

    # 좋아요 — accessibilityText("다른 사용자 27,500명과 함께 …") 가 정확한 값이다.
    # 버튼 title 은 "2.7만" 으로 줄여 오므로 뒤로 미룬다.
    for lb in walk(resp, 'likeButtonViewModel'):
        for t in texts(lb):
            if '좋아요' in t and '명' in t:
                n = exact_num(t)
                if n is not None:
                    out['likes'] = n
                    break
        if out['likes'] is not None:
            break
    if out['likes'] is None:
        for lb in walk(resp, 'likeButtonViewModel'):
            for t in texts(lb):
                if re.match(r'^[\d.,]+[억만천]?$', t.strip()):
                    out['likes'] = korean_num(t)
                    break
            if out['likes'] is not None:
                break
    return out


# ───────────────────────── 합치기 ─────────────────────────

def merge(rows, prev_books, prev_other, log):
    """새로 받은 목록과 기존 블록을 합친다.

    * 공개 화면에 없는 값(댓글·저장)은 **기존 값을 그대로 둔다.** 처음 본 영상만 None.
    * 기존에만 있고 이번에 안 보인 영상은 **지우지 않고** 그대로 들고 간다 —
      유튜브가 목록을 덜 줬을 뿐일 수도 있어서다.
    """
    old = {}
    for bk, b in (prev_books or {}).items():
        for r in (b.get('videos') or []):
            if isinstance(r, list) and r:
                old[r[0]] = r

    out, fresh_ids = {}, set()
    for r in rows:
        o = old.get(r['id'])
        views = r.get('views')
        if views is None and o is not None:
            views = o[I_VIEWS]                      # 못 받았으면 어제 값이 덜 틀린다
        date = r.get('date')
        approx = bool(r.get('approx'))
        if o is not None and o[I_DATE] and not date:
            date, approx = o[I_DATE], bool(len(o) > I_APPROX and o[I_APPROX])
        if o is not None and o[I_DATE] and date and approx:
            date, approx = o[I_DATE], False         # 확정값이 이미 있으면 추정으로 덮지 않는다
        likes = r.get('likes')
        if likes is None and o is not None:
            likes = o[I_LIKES]
        cmts = o[I_CMTS] if o is not None else None     # 공개 화면에 없다
        saves = o[I_SAVES] if o is not None else None   # 공개 화면에 없다
        shorts = r.get('shorts')
        if shorts is None and o is not None:
            shorts = o[I_SHORT]
        row = [r['id'], r['title'] or (o[I_TITLE] if o else ''), date, views,
               likes, cmts, saves, 1 if shorts else 0]
        if approx:
            row.append(1)
        out[r['id']] = row
        fresh_ids.add(r['id'])

    kept = []
    for vid, o in old.items():
        if vid not in out:
            out[vid] = list(o)
            kept.append(vid)
    if kept:
        log('    이번 목록에 안 보인 기존 영상 %d편은 그대로 들고 갑니다 (%s%s)'
            % (len(kept), ', '.join(kept[:5]), ' …' if len(kept) > 5 else ''))
    return out, fresh_ids, kept


def bucket(rows_by_id, prev_books, prev_other):
    """도서별로 갈라 담고 n · views 를 다시 센다.

    댓글·저장·공유 누계는 공개 화면에서 못 받으므로 **기존 값을 그대로 둔다.**
    좋아요 누계는 영상별 좋아요를 전부 받았을 때만 다시 세고, 한 편이라도
    비어 있으면 기존 값을 둔다 — 반쯤 센 합계가 떨어진 것처럼 읽히면 안 된다."""
    books, other = {}, []
    for bk, _ in BOOKS:
        books[bk] = []
    for vid, r in rows_by_id.items():
        k = book_of(r[I_TITLE])
        (books[k] if k in books else other).append(r)

    out = {}
    for bk, _ in BOOKS:
        vids = sorted(books[bk], key=lambda r: (r[I_VIEWS] or 0), reverse=True)
        p = (prev_books or {}).get(bk) or {}
        node = {'n': len(vids),
                'views': sum(r[I_VIEWS] or 0 for r in vids)}
        if vids and all(r[I_LIKES] is not None for r in vids):
            node['likes'] = sum(r[I_LIKES] for r in vids)
        elif 'likes' in p:
            node['likes'] = p['likes']
        for key in ('comments', 'saves', 'shares'):
            if key in p:
                node[key] = p[key]
        if 'daily' in p:
            node['daily'] = p['daily']              # 애널리틱스 — 손대지 않는다
        node['videos'] = vids
        out[bk] = node

    oth = {'n': len(other), 'views': sum(r[I_VIEWS] or 0 for r in other)}
    if not other and prev_other:
        oth = prev_other                            # 한 편도 못 가렸으면 이전 값을 둔다
    return out, oth, other


# ───────────────────────── 블록 쓰기 ─────────────────────────

def kst_now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)


def stamp_try(src, html, s, e, ok, why, log):
    """수집을 시도했다는 사실만 블록에 남긴다 — 기존 값은 하나도 건드리지 않는다.

    실패하면 화면에는 어제 숫자가 그대로 보인다. 사유를 안 적어두면 열어 본 사람은
    '안 올라온 건지 수집이 죽은 건지' 구별할 수 없다. (ranks.py 와 같은 장치다.)"""
    try:
        blk = json.loads(html[s + len(OPEN):e]) or {}
    except Exception:
        return
    blk['lastTry'] = {'at': kst_now().strftime('%Y-%m-%d %H:%M'), 'ok': bool(ok), 'why': why}
    doc = html[:s] + OPEN + json.dumps(blk, ensure_ascii=False) + '</script>' + html[e + len('</script>'):]
    if doc.count(OPEN) != 1 or 'id="payload"' not in doc or 'id="thumbs"' not in doc:
        return
    try:
        open(src, 'w', encoding='utf-8').write(doc)
        log('     (수집 시도 기록을 남겼습니다 — 화면에 사유가 표시됩니다)')
    except Exception:
        pass


def collect(log):
    today = kst_now().date()
    tube = Tube()

    log('  채널 목록')
    rows, _ = [], None
    seen = set()
    per_tab = {}
    for tab, is_short in TABS:
        try:
            got, _ = collect_grid(tube, tab, is_short, today, log)
        except Exception as ex:
            log('    %s 탭 실패: %s' % (tab, ex))
            per_tab[tab] = 0
            continue
        new = [r for r in got if r['id'] not in seen]
        for r in new:
            seen.add(r['id'])
        rows.extend(new)
        per_tab[tab] = len(got)
    if not rows:
        raise RuntimeError('채널 목록에서 영상을 한 편도 못 읽었습니다 — 유튜브가 목록 '
                           '마크업을 바꾼 것으로 보입니다. tools/youtube.py 의 GRID_KEYS / '
                           'parse_grid_item 을 봐야 합니다')
    log('    탭별 %s · 합쳐서 %d편' % (per_tab, len(rows)))
    if len(rows) < MIN_WANT:
        log('    받은 편수가 목표(%d편)보다 적습니다 — 받은 만큼만 씁니다' % MIN_WANT)

    log('  채널 규모')
    ch = about_channel(log)
    log('    %s %s · 구독 %s%s · 영상 %s개 · 총 조회 %s'
        % (ch['title'] or '–', ch['handle'] or '–',
           ch['subs'] if ch['subs'] is not None else '–',
           '(반올림)' if ch['subsApprox'] else '',
           ch['videos'] if ch['videos'] is not None else '–',
           ch['views'] if ch['views'] is not None else '–'))

    log('  영상별 조회·날짜·좋아요 (%d편)' % min(len(rows), DETAIL_CAP))
    ok = fail = 0
    for i, r in enumerate(rows[:DETAIL_CAP]):
        try:
            d = parse_detail(tube.post('next', {'videoId': r['id']}, tries=2), today)
        except Exception as ex:
            fail += 1
            if fail <= 3:
                log('    %s 상세 실패: %s' % (r['id'], str(ex)[:90]))
            continue
        if d['views'] is not None:
            r['views'] = d['views']
        if d['date']:
            r['date'], r['approx'] = d['date'], d['approx']
        if d['likes'] is not None:
            r['likes'] = d['likes']
        ok += 1
        if (i + 1) % 25 == 0:
            log('    %d/%d …' % (i + 1, min(len(rows), DETAIL_CAP)))
        time.sleep(DETAIL_PAUSE)
    log('    상세 성공 %d편 · 실패 %d편' % (ok, fail))
    if ok == 0:
        raise RuntimeError('영상 상세를 한 편도 못 읽었습니다 — /youtubei/v1/next 응답 구성이 '
                           '바뀐 것으로 보입니다. parse_detail 을 봐야 합니다')
    return rows, ch


def main():
    if len(sys.argv) < 2:
        print('SKIP 대상 html 경로가 없습니다')
        return 0
    if sys.argv[1] == '--dump':                     # 마크업이 바뀌었을 때 들여다보는 구멍
        html = http('https://www.youtube.com/channel/%s/videos' % CHANNEL_ID)
        d = grab(html, 'ytInitialData') or {}
        import collections
        c = collections.Counter()
        stack = [d]
        while stack:
            o = stack.pop()
            if isinstance(o, dict):
                for k, v in o.items():
                    if k.endswith(('Renderer', 'ViewModel')):
                        c[k] += 1
                    stack.append(v)
            elif isinstance(o, list):
                stack.extend(o)
        for k, v in c.most_common(25):
            print('%5d %s' % (v, k))
        return 0

    src = sys.argv[1]
    try:
        html = open(src, encoding='utf-8').read()
    except Exception as e:
        print('SKIP html 을 못 읽음:', e)
        return 0
    s = html.find(OPEN)
    if s < 0:
        print('SKIP ytData 블록이 없습니다 — 유튜브는 건너뜁니다')
        return 0
    e = html.find('</script>', s)
    try:
        prev = json.loads(html[s + len(OPEN):e]) or {}
    except Exception:
        print('SKIP ytData 블록이 JSON 이 아닙니다 — 건드리지 않습니다')
        return 0

    lines = []

    def log(m):
        print(m)
        lines.append(m)

    try:
        rows, ch = collect(log)
    except Exception as ex:
        print('SKIP 유튜브 수집 실패 —', ex)
        print('     (판매·광고 배포는 그대로 진행합니다. 유튜브는 이전 값이 유지됩니다.)')
        why = str(ex)
        if 'CONNECT' in why or 'Tunnel' in why:
            why = ('유튜브로 나가는 길이 실행 환경의 네트워크 정책에 막혀 있습니다 '
                   '(www.youtube.com CONNECT 403). 환경 네트워크 정책에 유튜브 호스트를 '
                   '허용해야 합니다.')
        stamp_try(src, html, s, e, False, why[:300])
        return 0

    prev_books = prev.get('books') or {}
    prev_other = prev.get('other')
    by_id, fresh_ids, kept = merge(rows, prev_books, prev_other, log)
    books, other, other_rows = bucket(by_id, prev_books, prev_other)

    approx_ids = [r[I_ID] for r in by_id.values() if len(r) > I_APPROX and r[I_APPROX]]
    miss_cm = [r[I_ID] for r in by_id.values() if r[I_CMTS] is None]
    miss_sv = [r[I_ID] for r in by_id.values() if r[I_SAVES] is None]
    no_views = [r[I_ID] for r in by_id.values() if r[I_VIEWS] is None]

    total_n = sum(b['n'] for b in books.values()) + other['n']
    views_sum = sum(b['views'] for b in books.values()) + other['views']

    out = dict(prev)                                # 모르는 키는 그대로 보존한다
    out['asOf'] = today_s = kst_now().strftime('%Y-%m-%d')
    out['chAsOf'] = today_s
    out['through'] = prev.get('through')            # 애널리틱스 — 우리가 못 올린다
    out['ch'] = {
        'title': ch['title'] or (prev.get('ch') or {}).get('title'),
        'handle': ch['handle'] or (prev.get('ch') or {}).get('handle'),
        'url': 'https://www.youtube.com/channel/' + CHANNEL_ID,
        'subs': ch['subs'] if ch['subs'] is not None else (prev.get('ch') or {}).get('subs'),
        'videos': ch['videos'] if ch['videos'] is not None else (prev.get('ch') or {}).get('videos'),
        'views': ch['views'] if ch['views'] is not None else (prev.get('ch') or {}).get('views'),
        'viewsSum': views_sum,
        'subsApprox': ch['subsApprox'],
    }
    if ch['handle']:
        out['ch']['url'] = 'https://www.youtube.com/' + ch['handle']
    out['books'] = books
    out['other'] = other
    out['chDaily'] = prev.get('chDaily')            # 애널리틱스 — 손대지 않는다
    out['collected'] = kst_now().strftime('%Y-%m-%d %H:%M')
    out['seen'] = total_n
    if approx_ids:
        out['approxDateIds'] = sorted(approx_ids)
    # 화면에 그대로 띄우는 한 줄 — 무엇이 새 값이고 무엇이 옛 값인지 적는다.
    note = ('조회수·올린날짜·좋아요는 채널 공개 페이지에서 %s 에 새로 받았습니다. '
            '댓글·저장·공유는 공개 화면에 없어 이전 값을 그대로 둡니다' % today_s)
    if prev.get('asOf'):
        note += ' (%s 기준)' % prev['asOf']
    note += '.'
    if miss_cm:
        note += ' 이번에 새로 들어온 %d편은 댓글·저장이 비어 있습니다 — 0 이 아니라 «없음»입니다.' % len(miss_cm)
    if approx_ids:
        note += ' 올린 날짜가 추정인 영상 %d편이 있습니다.' % len(approx_ids)
    out['aggNote'] = note

    old_tot = sum((prev_books.get(k) or {}).get('n') or 0 for k, _ in BOOKS) + \
        ((prev_other or {}).get('n') or 0)
    log('')
    log('  영상 %d편 (이전 %d편) · 누적 조회 %s' % (total_n, old_tot, format(views_sum, ',')))
    for bk, _ in BOOKS:
        b = books[bk]
        o = (prev_books.get(bk) or {}).get('n')
        vids = sorted(b['videos'], key=lambda r: (r[I_DATE] or ''), reverse=True)
        newest = vids[0] if vids else None
        log('    %-8s %3d편 (이전 %s) · 조회 %13s · 최근 %s %s'
            % (bk, b['n'], o if o is not None else '–', format(b['views'], ','),
               (newest[I_DATE] if newest else '–'),
               ((newest[I_TITLE] or '')[:30] if newest else '')))
    log('    other    %3d편 · 조회 %s' % (other['n'], format(other['views'], ',')))
    if no_views:
        log('    조회수를 못 받은 영상 %d편: %s' % (len(no_views), ', '.join(no_views[:5])))
    log('    댓글 없음 %d편 · 저장 없음 %d편 · 날짜 추정 %d편'
        % (len(miss_cm), len(miss_sv), len(approx_ids)))

    newest_all = max((r for r in by_id.values() if r[I_DATE]), key=lambda r: r[I_DATE], default=None)
    if newest_all:
        log('    채널 최신 영상 %s · %s' % (newest_all[I_DATE], newest_all[I_TITLE][:50]))

    # ── 검증 — 하나라도 어긋나면 블록을 바꾸지 않는다 ──
    kal_old = (prev_books.get('kaljung') or {}).get('n') or 0
    block = OPEN + json.dumps(out, ensure_ascii=False) + '</script>'
    doc = html[:s] + block + html[e + len('</script>'):]
    checks = {
        'payload 유지': 'id="payload"' in doc,
        'kyoboRanks 유지': 'id="kyoboRanks"' in doc,
        'volaDaily 유지': 'id="volaDaily"' in doc,
        'thumbs 유지': 'id="thumbs"' in doc,
        'ytData 1회': doc.count(OPEN) == 1,
        '영상수 안 줄었다': total_n >= old_tot,
        '칼융 %d편 이상' % kal_old: books['kaljung']['n'] >= kal_old,
        '목표 편수 확보': total_n >= MIN_WANT,
        '누적 조회 > 0': views_sum > 0,
        '길이': len(doc) > 100000,
    }
    log('  검증: %s' % checks)
    if not all(checks.values()):
        print('SKIP 검증 실패 — ytData 블록을 바꾸지 않습니다')
        return 1
    out['lastTry'] = {'at': out['collected'], 'ok': True, 'why': ''}
    block = OPEN + json.dumps(out, ensure_ascii=False) + '</script>'
    doc = html[:s] + block + html[e + len('</script>'):]
    open(src, 'w', encoding='utf-8').write(doc)
    print('YT_OK 영상=%d 조회합=%d 길이=%d' % (total_n, views_sum, len(doc)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
