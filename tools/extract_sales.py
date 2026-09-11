import openpyxl, datetime, json, sys

TABS = {
    'pyoryu':  ('우서전지(26.9)',   'new'),
    'kaljung': ('칼 융(26.7)',      'new'),
    'wonsiin': ('완벽한원시인(26.3)','new'),
    'freud':   ('프로이트(25.10)',  'new'),
    'muhan':   ('무한의부(24.10)',  'old'),
}
# 0-based 열: 날짜 / 교보(오프) / 교보(온라인) / 교보(법인) / 예스24 / 알라딘 / 영풍 / 메모
COLS = {
    'new': dict(date=0, cols=[1,2,3,5,6,7], memo=9),
    'old': dict(date=0, cols=[1,2,3,5,6,None], memo=8),
}

def num(v):
    if v is None or v == '':
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0

def extract(path):
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    out = {}
    for key, (tab, kind) in TABS.items():
        c = COLS[kind]
        rows = []
        for r in wb[tab].iter_rows(min_row=4, max_col=20, values_only=True):
            d = r[c['date']]
            if not isinstance(d, (datetime.datetime, datetime.date)):
                continue
            nums = [num(r[i]) if i is not None else 0.0 for i in c['cols']]
            memo = r[c['memo']] if len(r) > c['memo'] else None
            memo = str(memo).strip() if memo not in (None, '') else ''
            rows.append([d.strftime('%Y-%m-%d')] + nums + [memo, ''])
        # 앞뒤의 '아직 안 채운 날' 잘라내기 — 값도 메모도 없는 줄
        def empty(x):
            return all(v == 0 for v in x[1:7]) and not x[7]
        while rows and empty(rows[0]):
            rows.pop(0)
        while rows and empty(rows[-1]):
            rows.pop()
        out[key] = rows
    return out

if __name__ == '__main__':
    json.dump(extract(sys.argv[1]), open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False)
    print('ok')
