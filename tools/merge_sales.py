"""시트에서 뽑은 판매 행을 아티팩트 payload 에 병합한다.

원칙 — 기존 행은 지우지 않는다. 새 날짜는 붙이고, 이미 있는 날짜는 값이 달라졌을 때만 고친다
(교보·영풍은 며칠 늦게 집계돼 뒤늦게 백필되므로 덮어쓰기가 필요하다).
출간 전 0 행까지 끌어오면 차트가 늘어지므로 payload 가 이미 잡아 둔 시작일보다 앞은 건드리지 않는다.
"""
import json, re, sys, datetime
from extract_sales import extract

def main(html_path, xlsx_path, today):
    html = open(html_path, encoding='utf-8').read()
    sheet = extract(xlsx_path)

    OPEN = '<script id="payload" type="application/json">'
    s = html.index(OPEN) + len(OPEN)
    e = html.index('</script>', s)
    D = json.loads(html[s:e])

    log = []
    for key, b in D['books'].items():
        rows = sheet.get(key)
        if not rows:
            log.append(f'{key}: 시트 탭 없음 — 건너뜀')
            continue
        cur = {r[0]: r for r in b['sales']}
        start = b['sales'][0][0] if b['sales'] else rows[0][0]
        fresh, fixed = [], []
        for r in rows:
            d = r[0]
            if d < start or d > today:
                continue
            if d not in cur:
                fresh.append(r)
            else:
                prev = cur[d]
                if [float(x) for x in prev[1:7]] != [float(x) for x in r[1:7]]:
                    fixed.append(d)
                    prev[1:7] = r[1:7]
                if not prev[7] and r[7]:
                    prev[7] = r[7]
        # 아직 안 채운 맨 끝 날짜(값도 메모도 없는 줄)는 붙이지 않는다 — 0부 판매로 읽힌다.
        # 중간의 0 은 진짜 0 이므로 끝에서만 잘라낸다.
        while fresh and all(v == 0 for v in fresh[-1][1:7]) and not fresh[-1][7]:
            fresh.pop()
        added = [r[0] for r in fresh]
        for r in fresh:
            cur[r[0]] = r
        merged = [cur[d] for d in sorted(cur)]
        b['sales'] = merged
        log.append(f'{key}: +{len(added)}행 {added} · 값수정 {len(fixed)} {fixed} · 마지막 {merged[-1][0]}')

    D['collected'] = max(b['sales'][-1][0] for b in D['books'].values() if b['sales'])
    D['generated'] = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M')
    D['asOfRun'] = today

    html = html[:s] + json.dumps(D, ensure_ascii=False) + html[e:]
    open(html_path, 'w', encoding='utf-8').write(html)
    print('\n'.join(log))
    print('collected =', D['collected'], '| generated =', D['generated'])

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])
