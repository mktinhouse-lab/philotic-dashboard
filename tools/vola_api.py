#!/usr/bin/env python3
"""볼라(vo.la) API 로 링크별 누적 클릭수를 받아 온다.

왜 API 인가 — 예전에는 사람이 로그인한 브라우저 콘솔에서 수기로 긁었다. 매일 할 일이
아니다. 볼라는 라이트 플랜부터 공개 API 를 주므로 그걸 쓴다.

    GET https://vo.la/api/urls?limit=500&page=1&order=date
    Authorization: Bearer <키>

응답의 `data.urls[]` 한 칸이 링크 하나다 — `alias`(짧은 주소 뒤에 붙는 코드), `clicks`(누적),
`longurl`, `title`, `date`. 우리가 쓰는 건 alias 와 clicks 다.

**누적만 준다. 일별은 안 준다.** 그래서 대시보드의 `daily` 는 건드리지 않고 `total` 만 채운다
(`tools/set_vola_totals.py` 가 그 일을 한다). 게다가 볼라는 라이트 플랜에서 통계를 30일만
보관하므로, 과거는 우리가 매일 받아서 쌓는 수밖에 없다 — 교보 순위와 같은 사정이다.

키는 **환경변수 `VOLA_API_KEY`** 에서 읽는다. 저장소에 적지 마라.

    python3 tools/vola_api.py > vola_totals.json
    python3 tools/set_vola_totals.py dash.html vola_totals.json

이 환경에서 vo.la 로 못 나가면(프록시 CONNECT 403) 그 사실을 적고 1 로 끝낸다 — 우회하지 않는다.
"""
import json, os, sys, time, urllib.error, urllib.request

BASE = 'https://vo.la/api/urls'
PER_PAGE = 500          # 한 번에 되도록 많이 — 분당 30회 한도를 아끼려는 것이다
MAX_PAGES = 20          # 149개뿐이지만 늘어날 수 있으니 여유를 둔다. 무한루프 방지용.
PAUSE = 2.5             # 분당 30회 = 2초에 한 번. 조금 여유 있게 쉰다.


def fetch(key, page, timeout=30):
    url = '%s?limit=%d&page=%d&order=date' % (BASE, PER_PAGE, page)
    req = urllib.request.Request(url, headers={
        'authorization': 'Bearer ' + key,
        'content-type': 'application/json',
        'accept': 'application/json',
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def main():
    key = os.environ.get('VOLA_API_KEY')
    if not key:
        sys.exit('VOLA_API_KEY 가 없다. 환경 비밀값에 넣어라 — 코드에 적지 마라.')

    totals, meta, page = {}, {}, 1
    while page <= MAX_PAGES:
        try:
            body = fetch(key, page)
        except urllib.error.HTTPError as e:
            detail = e.read()[:300].decode('utf-8', 'replace')
            if e.code == 401:
                sys.exit('키가 거절됐다(401). 볼라에서 키를 바꿨다면 환경 비밀값도 바꿔라. ' + detail)
            if e.code == 429:
                sys.exit('호출 한도를 넘었다(429) — 분당 30회다. 잠시 뒤 다시 돌려라.')
            sys.exit('볼라가 HTTP %d 로 거절했다: %s' % (e.code, detail))
        except urllib.error.URLError as e:
            sys.exit('볼라에 못 닿았다: %s  (환경 네트워크 허용목록에 vo.la 가 있는지 봐라)' % e.reason)

        # 볼라는 error 를 "0"(문자) 으로도 0(숫자) 으로도 준다. 둘 다 성공으로 본다.
        if str(body.get('error', '0')) not in ('0', ''):
            sys.exit('볼라가 오류를 돌려줬다: %s' % body.get('message', body))

        d = body.get('data') or {}
        for u in (d.get('urls') or []):
            # 사람이 볼라 화면에서 코드를 만들다 앞뒤에 공백을 흘리는 일이 있다
            # (' jung5분yes'). 짧은주소는 다듬은 코드로 열리고 대시보드도 다듬은
            # 코드로 들고 있으므로, 받을 때 다듬어 같은 링크가 두 줄로 갈라지지 않게 한다.
            alias = (u.get('alias') or '').strip()
            if not alias:
                continue
            clicks = int(u.get('clicks') or 0)
            if alias in totals:
                # 공백만 다른 코드가 둘 있으면 합치지 말고 큰 쪽을 남긴다 — 어느 쪽이
                # 진짜인지 모르는 채로 더하면 숫자가 부풀어 오른다.
                print('공백만 다른 코드가 겹쳤다: %r (클릭 %d vs %d) — 큰 쪽을 쓴다'
                      % (alias, totals[alias], clicks), file=sys.stderr)
                if clicks <= totals[alias]:
                    continue
            totals[alias] = clicks
            meta[alias] = {'title': (u.get('title') or '').strip(),
                           'longurl': u.get('longurl') or '',
                           'date': u.get('date') or ''}

        cur, mx = int(d.get('currentpage') or page), int(d.get('maxpage') or page)
        if cur >= mx:
            break
        page += 1
        time.sleep(PAUSE)

    if not totals:
        sys.exit('링크를 하나도 못 받았다 — 키나 응답 모양이 바뀌었는지 봐라.')

    json.dump({'asOf': time.strftime('%Y-%m-%d'),
               'collected': time.strftime('%Y-%m-%d %H:%M'),
               'totals': totals,
               'meta': meta},
              sys.stdout, ensure_ascii=False, indent=1)
    print(file=sys.stdout)
    print('볼라 링크 %d개 · 클릭 합계 %s' % (len(totals), format(sum(totals.values()), ',')),
          file=sys.stderr)


if __name__ == '__main__':
    main()
