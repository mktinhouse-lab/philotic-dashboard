#!/usr/bin/env python3
"""최근 7일 소재별 광고 성적을 아티팩트에 넣는다 (`adsWeek` 블록).

  python3 tools/set_ads_week.py <html경로> <adsWeek.json>

왜 따로 있나 — 아티팩트의 `payload` 에는 소재별 성적이 **캠페인 전 기간 누적**으로만 있다.
날짜별 소재 성적은 없다. 그런데 보고는 주 단위로 하니까 "이번 주에 뭐가 잘 됐나"가 필요하다.
그 값은 메타 광고 리포트를 **소재(ad) 단위 · 최근 7일**로 다시 물어야 나온다.

메타는 MCP 커넥터로만 닿으므로 이 스크립트가 직접 받아오지는 못한다. 받아온 JSON 을 넣는 일만 한다.
받는 법 (세션에서):

    ads_get_ad_entities(ad_account_id='581875957830502', level='ad',
                        date_preset='last_7d', sort='spend_descending',
                        fields=['name','spend','impressions','reach','clicks','ctr','cpc',
                                'campaign_name'])

캠페인 이름으로 책을 가른다. 캠페인이 새로 생기면 `campaign` 에 짝을 적어 두면 된다.

JSON 모양:
    {"from":"2026-09-11","to":"2026-09-17","collected":"2026-09-18 14:00",
     "src":"...","campaign":{"캠페인명":"책키"},
     "books":{"kaljung":[["소재명",광고비,노출,도달,클릭,CTR,CPC], ...]}}

주 1회만 갱신하면 된다. 화면은 `to` 가 광고 기준일보다 이틀 넘게 뒤지면 꼬리표를 단다.
"""
import sys, json

OPEN = '<script id="adsWeek" type="application/json">'


def main(html_path, json_path):
    data = json.load(open(json_path, encoding='utf-8'))
    for f in ('from', 'to', 'books'):
        if f not in data:
            sys.exit('JSON 에 %s 가 없습니다' % f)
    if not data['books']:
        sys.exit('books 가 비어 있습니다 — 넣을 것이 없습니다')

    html = open(html_path, encoding='utf-8').read()
    enc = json.dumps(data, ensure_ascii=False).replace('</script', r'<\/script')
    block = OPEN + enc + '</script>'

    if OPEN in html:
        s = html.index(OPEN)
        e = html.index('</script>', s + len(OPEN)) + len('</script>')
        doc = html[:s] + block + html[e:]
    else:
        # 새로 넣을 때는 payload 블록 바로 앞에 — 다른 블록을 건드리지 않는 자리다
        anchor = '<script id="payload" type="application/json">'
        if anchor not in html:
            sys.exit('payload 블록을 못 찾아 넣을 자리를 정할 수 없습니다')
        i = html.index(anchor)
        doc = html[:i] + block + '\n' + html[i:]

    for name, ok in [('payload 유지', 'id="payload"' in doc), ('thumbs 유지', 'id="thumbs"' in doc),
                     ('adsWeek 1회', doc.count(OPEN) == 1)]:
        if not ok:
            sys.exit('검증 실패(%s) — 아무것도 쓰지 않았습니다' % name)

    open(html_path, 'w', encoding='utf-8').write(doc)
    n = sum(len(v) for v in data['books'].values())
    print('adsWeek %s~%s · 책 %d권 · 소재 %d개 (수집 %s)'
          % (data['from'], data['to'], len(data['books']), n, data.get('collected', '?')))


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
