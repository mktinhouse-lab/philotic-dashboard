# 필로틱 출판 대시보드 — 운영 메모

대시보드 본체는 이 저장소가 아니라 **아티팩트**에 있습니다.

- 대시보드: https://claude.ai/code/artifact/6b8299e5-b019-4650-9a92-93d16ac845e1
- 판매 시트: https://docs.google.com/spreadsheets/d/1d8Cll3n8ZxUtaqF5acSn9FekjsD8_4IuO33KkDklqB8/edit
- 메타 광고계정: 581875957830502

아티팩트 HTML 안에 `<script type="application/json">` 블록으로 데이터가 들어 있고,
갱신 스크립트(`ranksPy`·`organicPy`)도 같은 방식으로 그 안에 박혀 있습니다.
여기 `tools/` 는 그중 **판매 시트 → 아티팩트** 경로만 따로 떼어 둔 것입니다.

## 매일 하는 일

| 원천 | 누가 | 어떻게 |
| --- | --- | --- |
| 판매 (교보·예스24·알라딘·영풍) | **사람** | 포털 4곳 로그인 → 구글시트 각 책 탭에 전날 판매량 입력 (`pilotic-sales-routine` 스킬) |
| 판매 시트 → 아티팩트 | 자동 | `필로틱 대시보드 자동 갱신 (판매 + 광고)` 루틴 · 매일 09:00 / 18:00 KST |
| 메타 광고 | 자동 | 같은 루틴 (meta MCP) |
| 인스타 · 페북 | 자동 | 같은 루틴 (Windsor 커넥터) + `organicPy` |
| 교보 순위 | 자동 | `ranksPy` — 교보 공개 API 직접 호출 |
| 유튜브 | **사람** | Windsor 유튜브 커넥터 미연결 |
| 볼라 단축링크 | **사람** | 로그인해야 통계가 보임 |

아티팩트 맨 위 **「데이터 신선도」** 카드가 원천별로 며칠까지 채워져 있는지 보여줍니다.
갱신을 맡았으면 이 카드부터 보면 됩니다.

## tools/

```bash
pip install openpyxl

# 1) 시트를 xlsx 로 내려받는다 (Google Drive MCP: download_file_content,
#    exportMimeType=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet)
# 2) 아티팩트 HTML 을 받아둔다 (Artifact action:"read")
python3 tools/merge_sales.py dash.html sales.xlsx 2026-09-11   # 마지막 인자 = 오늘
# 3) dash.html 을 같은 URL 로 republish
```

`merge_sales.py` 규칙

- 기존 행은 지우지 않는다. **새 날짜만 붙이고**, 이미 있는 날짜는 값이 달라졌을 때만 고친다
  (교보·영풍은 며칠 늦게 집계돼 뒤늦게 백필된다).
- payload 가 이미 잡아 둔 시작일보다 앞은 건드리지 않는다 — 시트에는 출간 전 진열 메모 행이
  몇 달치 있어서 그대로 끌어오면 차트가 늘어진다.
- 맨 끝의 빈 줄(값도 메모도 없는 날)은 붙이지 않는다 — 아직 안 채운 날이지 0부 판매가 아니다.
  중간의 0 은 진짜 0 이므로 남긴다.
- `collected`(화면의 기준일) = 각 책 마지막 판매 기록일 중 가장 늦은 날.

시트 열 매핑은 `extract_sales.py` 에 있습니다. 무한의부·세네카 탭은 **영풍 열이 없는 구형**이라
열 번호가 한 칸씩 밀립니다.

## 알려진 제약 — 클라우드 세션의 네트워크 정책

Claude Code on the web 세션은 외부 HTTPS 가 조직 정책으로 막혀 있어
**교보(store·product·event.kyobobook.co.kr) · 유튜브 · 볼라 · 알라딘에 닿지 못합니다**
(CONNECT 403). MCP 커넥터(구글 드라이브·메타·윈저)만 통합니다.

그래서 클라우드에서는

- 판매 시트 → 아티팩트, 메타 광고, 인스타·페북 = **된다**
- 교보 순위(`ranksPy`) · 유튜브 · 볼라 = **안 된다** — 이전 값이 그대로 남는다

풀려면 환경(Environments)의 네트워크 정책에 해당 호스트를 열어 주어야 합니다.
