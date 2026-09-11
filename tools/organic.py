"""오가닉(인스타·페북) 게시물 성과를 아티팩트에 병합한다 — 매일 도는 클라우드 루틴용.

  python3 organic-cloud.py <html경로> [ig.json] [fb.json]    (제자리 수정)

읽는 파일 (루틴이 윈저 커넥터로 받아 저장해 둔다). 생략하면 /tmp 를 본다:
  /tmp/ig.json  인스타 media 지표 + 캡션
  /tmp/fb.json  페북 post 지표 + 본문
경로를 인자로 받는 이유는 로컬에서 같은 코드로 시험해 보기 위해서다 —
클라우드에서만 돌아가는 스크립트는 고칠 때마다 하루를 기다려야 한다.

설계 원칙 — **절대 배포를 막지 않는다.**
순위 수집(ranks-cloud.py)과 같다. 무슨 일이 있어도 SKIP 을 찍고 0 으로 끝난다.
오가닉이 하루 비는 것보다 판매·광고 갱신이 멈추는 쪽이 훨씬 나쁘다.

맞추는 키
  · 인스타 = shortcode
  · 페북   = 게시 시각(UTC 분). 커넥터 post_id 는 `페이지id_글id` 라
             페이로드에 들어 있는 릴스 id 와 형식이 달라 id 로는 못 맞춘다.

도서 귀속은 캡션·본문에 박힌 책 이름으로 가른다. 어느 책도 안 걸리면 igOther 로 보낸다
(계정 전체 성과를 보려면 책에 안 붙는 게시물도 남아 있어야 한다).

안전장치 — 지표는 시간이 갈수록 늘기만 한다. 하나라도 줄면 필드를 잘못 골랐다는 뜻이므로
아무것도 쓰지 않고 SKIP 한다. 실제로 페북 `post_reactions_total` 이 어느 날부터 전 행 0 을
돌려주기 시작했고(2026-08-27 확인), 그걸 그대로 넣었으면 기존 좋아요를 전부 지웠을 것이다.
그래서 좋아요는 `post_activity_by_action_type_like` 를 쓴다.
"""
import sys, os, re, json
from datetime import datetime, timedelta, timezone


def skip(msg):
    print('SKIP ' + msg)
    sys.exit(0)


ACC = {'book_ta_ku': 'B', 'philotic_book': 'P'}
TYP = {'CAROUSEL_ALBUM': 'C', 'REELS': 'R', 'IMAGE': 'I', 'VIDEO': 'V'}

# 캡션에서 책을 가르는 말. 먼저 걸리는 것이 이긴다 — 아래로 갈수록 느슨하다.
BOOKWORDS = [
    ('kaljung', ['칼 융의 내면수업', '칼융의 내면수업', '내면수업', '칼 융', '칼융']),
    ('wonsiin', ['완벽한 원시인', '완벽한원시인', '원시인']),
    ('freud',   ['프로이트의 감정수업', '프로이트']),
    ('muhan',   ['무한의 부', '무한의부']),
]


def which_book(text):
    t = (text or '').replace(' ', '')
    for key, words in BOOKWORDS:
        for w in words:
            if w.replace(' ', '') in t:
                return key
    return None


def note_drop(stat, tag, i, old, new):
    """행 하나를 견줘 기록만 한다 — 멈출지 말지는 나중에 필드 단위로 정한다."""
    key = (tag, i)
    seen, fell, samples = stat.setdefault(key, [0, 0, []])
    stat[key][0] = seen + 1
    if new < old:
        stat[key][1] = fell + 1
        if len(samples) < 4:
            samples.append('%s [%d] %s→%s' % (tag, i, old, new))


def collapsed(stat):
    """필드 전체가 무너진 것만 골라낸다.

    전 행 0 을 돌려주는 죽은 필드(원래 막으려던 사고)는 100% 라 반드시 걸린다.
    한두 게시물의 저장·공유 취소는 비율이 낮아 통과한다.
    """
    bad = []
    for (tag, i), (seen, fell, samples) in sorted(stat.items()):
        if seen >= 3 and fell / seen >= 0.2:
            bad.append('%s [%d] — %d/%d 행 감소: %s' % (tag, i, fell, seen, ' · '.join(samples)))
    return bad


def num(x):
    try:
        return int(float(x))
    except Exception:
        return 0


def load(path):
    with open(path, encoding='utf-8') as f:
        d = json.loads(f.read().strip())
    if isinstance(d, str):
        d = json.loads(d)
    if isinstance(d, dict):
        for k in ('result', 'data', 'rows'):
            if isinstance(d.get(k), (list, str)):
                d = d[k]
                if isinstance(d, str):
                    d = json.loads(d)
                break
    if not isinstance(d, list):
        raise ValueError('목록이 아님: ' + str(type(d)))
    return d


def main():
    if len(sys.argv) < 2:
        skip('html 경로가 없습니다')
    src = sys.argv[1]
    if not os.path.exists(src):
        skip('html 을 못 찾음: ' + src)

    igF = sys.argv[2] if len(sys.argv) > 2 else '/tmp/ig.json'
    fbF = sys.argv[3] if len(sys.argv) > 3 else '/tmp/fb.json'
    try:
        ig_raw = load(igF)
    except Exception as e:
        ig_raw = None
        print('  인스타 파일 못 읽음: %s' % e)
    try:
        fb_raw = load(fbF)
    except Exception as e:
        fb_raw = None
        print('  페북 파일 못 읽음: %s' % e)
    if not ig_raw and not fb_raw:
        skip('인스타·페북 둘 다 읽을 게 없습니다')

    html = open(src, encoding='utf-8').read()
    m = re.search(r'<script id="payload" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        skip('payload 블록이 없습니다')
    try:
        P = json.loads(m.group(1))
    except Exception as e:
        skip('payload 파싱 실패: %s' % e)
    if not P.get('books'):
        skip('payload 에 books 가 없습니다')

    P.setdefault('igOther', {'ig': [], 'fb': []})
    P['igOther'].setdefault('ig', [])
    P['igOther'].setdefault('fb', [])

    stat = {}          # (채널, 필드) -> [견준 행, 줄어든 행, 예시] — 필드가 무너지면 포기한다
    ig_upd = ig_add = 0
    fb_upd = fb_add = 0

    # ---------- 인스타 ----------
    if ig_raw:
        where = {}     # shortcode -> 담긴 곳
        for k, b in P['books'].items():
            for r in b.get('igPosts') or []:
                where[str(r[7])] = k
        for r in P['igOther']['ig']:
            where[str(r[7])] = '__other'

        for it in ig_raw:
            sc = str(it.get('media_shortcode') or '')
            ts = str(it.get('timestamp') or '')[:16]
            if not sc or len(ts) < 16:
                continue
            acc = ACC.get(str(it.get('account_name') or ''))
            if not acc:
                continue                      # 모르는 계정은 건드리지 않는다
            typ = TYP.get(str(it.get('media_type') or ''), '?')
            row = [ts, acc, typ,
                   num(it.get('media_views')), num(it.get('media_reach')),
                   num(it.get('media_saved')), num(it.get('media_shares')), sc]

            slot = where.get(sc)
            if slot is None:
                slot = which_book(it.get('media_caption')) or '__other'
            lst = P['igOther']['ig'] if slot == '__other' else P['books'].setdefault(
                slot, {}).setdefault('igPosts', [])

            at = next((i for i, x in enumerate(lst) if str(x[7]) == sc), -1)
            if at >= 0:
                for i in (3, 4, 5, 6):
                    note_drop(stat, 'ig', i, lst[at][i], row[i])
                lst[at] = row
                ig_upd += 1
            else:
                lst.append(row)
                ig_add += 1

    # ---------- 페북 ----------
    if fb_raw:
        at_min = {}    # 게시 분 -> (담긴 곳, 행)
        for k, b in P['books'].items():
            for r in b.get('fbPosts') or []:
                at_min[str(r[0])[:16]] = (k, r)
        for r in P['igOther']['fb']:
            at_min[str(r[0])[:16]] = ('__other', r)

        for it in fb_raw:
            ts = str(it.get('post_created_time') or '')[:16]
            if len(ts) < 16:
                continue
            imp = num(it.get('post_impressions'))
            like = num(it.get('post_activity_by_action_type_like'))
            cmt = num(it.get('post_activity_by_action_type_comment'))
            shr = num(it.get('post_activity_by_action_type_share'))
            clk = num(it.get('post_clicks_by_type_link_clicks'))

            hit = at_min.get(ts)
            if hit:
                r = hit[1]
                for i, v in ((2, imp), (3, like), (4, cmt), (5, shr), (6, clk)):
                    note_drop(stat, 'fb', i, r[i], v)
                # r[1] 은 정체를 못 밝힌 칸이라 화면에 안 쓴다 — 덮어쓰지 않는다.
                # r[7] 도 기존 릴스 id 를 유지한다(형식이 달라 바꾸면 다음 대조가 깨진다).
                r[2], r[3], r[4], r[5], r[6] = imp, like, cmt, shr, clk
                fb_upd += 1
            else:
                pid = str(it.get('post_id') or '')
                pid = pid.split('_')[-1] if '_' in pid else pid
                if not pid:
                    continue
                slot = which_book(it.get('post_message')) or '__other'
                lst = P['igOther']['fb'] if slot == '__other' else P['books'].setdefault(
                    slot, {}).setdefault('fbPosts', [])
                lst.append([ts, 0, imp, like, cmt, shr, clk, pid])
                fb_add += 1

    bad = collapsed(stat)
    if bad:
        print('  필드 단위로 무너진 곳 %d 군데:' % len(bad))
        for x in bad:
            print('   ', x)
        skip('지표가 줄었습니다 — 커넥터 필드가 바뀐 것으로 보입니다. 아무것도 쓰지 않았습니다')
    minor = sum(f for _, f, _ in stat.values())
    if minor:
        print('  줄어든 행 %d 개 — 저장·공유 취소로 보고 그대로 반영합니다' % minor)

    if ig_upd + ig_add + fb_upd + fb_add == 0:
        skip('반영할 게시물이 없습니다')

    for k, b in P['books'].items():
        if b.get('igPosts'):
            b['igPosts'].sort(key=lambda r: str(r[0]))
        if b.get('fbPosts'):
            b['fbPosts'].sort(key=lambda r: str(r[0]))
    P['igOther']['ig'].sort(key=lambda r: str(r[0]))
    P['igOther']['fb'].sort(key=lambda r: str(r[0]))

    # utcnow() 는 파이썬 최신판에서 없어질 예정이라 시간대를 붙여 쓴다
    kst = (datetime.now(timezone.utc) + timedelta(hours=9)).strftime('%Y-%m-%d')
    if ig_raw:
        P['igAsOf'] = kst
    if fb_raw:
        P['fbAsOf'] = kst

    new = '<script id="payload" type="application/json">' + json.dumps(P, ensure_ascii=False) + '</script>'
    out = html[:m.start()] + new + html[m.end():]

    # 심은 것을 되꺼내 확인한다 — 깨진 문서를 배포하면 안 된다
    m2 = re.search(r'<script id="payload" type="application/json">(.*?)</script>', out, re.S)
    try:
        back = json.loads(m2.group(1))
    except Exception as e:
        skip('되꺼내기 실패: %s' % e)
    checks = {
        'payload 1회': out.count('id="payload"') == 1,
        '판매 보존': all((b.get('sales') or []) for b in back['books'].values()),
        '광고 보존': any((b.get('daily') or []) for b in back['books'].values()),
        'kyoboRanks 유지': 'id="kyoboRanks"' in out,
        'volaDaily 유지': 'id="volaDaily"' in out,
        'thumbs 유지': 'id="thumbs"' in out,
        '길이': len(out) > 100000,
    }
    if not all(checks.values()):
        print('  검증:', checks)
        skip('검증 실패 — 아무것도 쓰지 않았습니다')

    open(src, 'w', encoding='utf-8').write(out)
    tot_ig = sum(len(b.get('igPosts') or []) for b in back['books'].values())
    tot_fb = sum(len(b.get('fbPosts') or []) for b in back['books'].values())
    print('  인스타 갱신 %d · 추가 %d → 도서 귀속 %d건 (비귀속 %d)'
          % (ig_upd, ig_add, tot_ig, len(back['igOther']['ig'])))
    print('  페북   갱신 %d · 추가 %d → 도서 귀속 %d건 (비귀속 %d)'
          % (fb_upd, fb_add, tot_fb, len(back['igOther']['fb'])))
    print('  기준일 igAsOf=%s fbAsOf=%s' % (back.get('igAsOf'), back.get('fbAsOf')))
    print('ORGANIC_OK')


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        skip('예상 못한 오류: %r' % (e,))
