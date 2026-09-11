#!/usr/bin/env python3
"""교보 순위를 손으로 한 칸 넣는다.

  python3 tools/set_rank.py <html경로> <책> <면> <순위> [기준일]

교보 수집기(ranks.py)가 못 도는 동안에도 사람은 교보 화면을 볼 수 있다. 그때 눈으로 읽은
순위를 넣기 위한 도구다. 자동 수집분과 섞이면 안 되므로 `manual` 표시를 같이 박는다 —
화면의 타일에 '수기 입력'이 뜨고, 그래야 나중에 보는 사람이 이 숫자를 API 값으로 오해하지 않는다.

수집기가 다시 돌면 books/hist 를 통째로 다시 쓰므로 이 값은 자연히 진짜 값으로 덮인다.
그게 맞다 — 수기는 임시방편이지 기록이 아니다.

면 이름은 화면 타일과 같다:
  onlineDaily     온라인 일간 · 종합
  onlineWeekly    온라인 주간 · 종합
  onlineMonthly   온라인 월간 · 종합
  realtime        실시간 베스트
  totalWeeklyAll  종합 주간 · 전체
  totalMonthlyAll 종합 월간 · 전체
  totalWeeklyCat  종합 주간 · 분야   ← '종합 인문 N위'는 보통 이것
  totalMonthlyCat 종합 월간 · 분야
  weeklyBestCat   주간베스트 · 분야 (상품 페이지에 적힌 값)
"""
import sys, json, datetime

OPEN = '<script id="kyoboRanks" type="application/json">'
SURFACES = ['onlineDaily', 'onlineWeekly', 'onlineMonthly', 'realtime', 'totalWeeklyAll',
            'totalMonthlyAll', 'totalWeeklyCat', 'totalMonthlyCat', 'totalAnnualCat', 'weeklyBestCat']


def main(path, book, surface, rank, at=None):
    rank = int(rank)
    at = at or (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime('%Y-%m-%d')
    if surface not in SURFACES:
        sys.exit('면 이름이 틀렸습니다. 쓸 수 있는 값: ' + ', '.join(SURFACES))

    html = open(path, encoding='utf-8').read()
    s = html.index(OPEN) + len(OPEN)
    e = html.index('</script>', s)
    KR = json.loads(html[s:e])

    b = (KR.get('books') or {}).get(book)
    if not b:
        sys.exit('그런 책이 없습니다: %s (있는 것: %s)' % (book, ', '.join(KR.get('books') or {})))

    if surface == 'weeklyBestCat':
        wb = b.setdefault('weeklyBest', {})
        before = wb.get('cat')
        wb['cat'] = rank
        wb['manual'] = {'at': at}
    else:
        prev = (b['ranks'].get(surface) or {}).get('rank')
        before = prev
        # prev 는 '직전에 기록된 값'이다. 없으면 비교할 게 없으니 넣지 않는다.
        b['ranks'][surface] = {'rank': rank, 'prev': prev, 'manual': {'at': at}}
        # 추이 그래프는 hist 를 읽는다 — 여기에도 같은 날짜로 한 점 찍어 준다
        KR.setdefault('hist', {}).setdefault(at, {}).setdefault(book, {})[surface] = rank

    html = html[:s] + json.dumps(KR, ensure_ascii=False) + html[e:]
    open(path, 'w', encoding='utf-8').write(html)
    print('%s · %s : %s → %d위 (수기, %s)' % (book, surface, before if before is not None else '없음', rank, at))


if __name__ == '__main__':
    if len(sys.argv) < 5:
        sys.exit(__doc__)
    main(*sys.argv[1:6])
