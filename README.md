# 필로틱 출판 대시보드 — 운영 메모

대시보드 본체는 이 저장소가 아니라 **아티팩트**에 있습니다.

- 대시보드: https://claude.ai/code/artifact/6b8299e5-b019-4650-9a92-93d16ac845e1
- 판매 시트: https://docs.google.com/spreadsheets/d/1d8Cll3n8ZxUtaqF5acSn9FekjsD8_4IuO33KkDklqB8/edit
- 메타 광고계정: 581875957830502

아티팩트 HTML 안에 `<script type="application/json">` 블록으로 데이터가 들어 있고,
갱신 스크립트(`ranksPy`·`organicPy`)도 같은 방식으로 그 안에 박혀 있습니다.
여기 `tools/` 는 그중 **판매 시트 → 아티팩트** 경로만 따로 떼어 둔 것입니다.

## 매일 하는 일

| 원천 | 누가 | 언제 |
| --- | --- | --- |
| 판매 (교보·예스24·알라딘·영풍) | **사람** | 포털 4곳 로그인 → 구글시트 각 책 탭에 전날 판매량 입력 (`pilotic-sales-routine` 스킬) |
| 판매 시트 → 아티팩트 | 자동 | `대시보드 자동 갱신 (판매 + 광고)` · 매일 **09:00 / 18:00** KST |
| 메타 광고 | 자동 | 같은 루틴 (meta MCP) |
| 인스타 · 페북 | 자동 | 같은 루틴 (Windsor 커넥터) + `organicPy` |
| 교보 순위 · 펀딩 · 볼라 · 유튜브 2채널 · 유튜브 썸네일 | 자동 | `필로틱 교보·볼라·유튜브(2채널)` · 매일 **11:10** KST (필로틱 환경) |
| **옛 대시보드 → 현황판** | 자동 | `필로틱 현황판 자동 갱신` · 매일 **12:00** KST |
| 주간 소재별 광고 성적 | **사람** | 주 1회 · 아래 「주 1회」 참고 |
| 유튜브 | **사람** | Windsor 유튜브 커넥터 미연결 |
| 볼라 단축링크 | **사람** | 로그인해야 통계가 보임 |

하루 흐름은 **11시 판매 시트(사람) → 11:10 교보·볼라·유튜브 → 11:40 판매·광고 → 12시 현황판** 이다.
현황판 루틴은 옛 대시보드를 **읽기만 한다** — 원천을 고치지 않는다. 순서가 뒤집히면
현황판이 어제 값을 들고 가므로, 앞 단계가 늦어지면 12시 것도 미뤄야 한다.

아티팩트 맨 위 **「데이터 신선도」** 카드가 원천별로 며칠까지 채워져 있는지 보여줍니다.
갱신을 맡았으면 이 카드부터 보면 됩니다.

## tools/

`ranks.py` 와 `organic.py` 는 아티팩트 안(`ranksPy`·`organicPy` 블록)에 박혀 있는 것과 같은
스크립트를 꺼내 둔 사본입니다. 셋 다 **아티팩트 HTML 을 제자리에서 고치고**, 고친 파일을
같은 URL 로 republish 하면 끝입니다.

```bash
pip install openpyxl

# 0) 아티팩트 HTML 을 받아둔다 — Artifact action:"read" (dash.html 로 저장됨)

# 판매 — 시트를 xlsx 로 내려받아 병합 (Google Drive MCP: download_file_content,
#        exportMimeType=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet)
python3 tools/merge_sales.py dash.html sales.xlsx 2026-09-11   # 마지막 인자 = 오늘

# 교보 순위 — 외부 네트워크 필요 (아래 '알려진 제약' 참고)
python3 tools/ranks.py dash.html

# 교보 순위를 손으로 한 칸만 넣기 (수집기가 못 도는 동안)
python3 tools/set_rank.py dash.html kaljung totalWeeklyCat 9        # '종합 인문 9위'
# → 타일에 '수기 입력' 딱지가 붙고, 수집기가 다시 돌면 자동 값으로 덮인다

# 오가닉 — 윈저로 받아둔 ig.json / fb.json 을 병합
python3 tools/organic.py dash.html ig.json fb.json

# 마지막에 dash.html 을 같은 URL 로 republish

# 새 현황판(v2) 다시 만들기 — 옛 대시보드를 배포한 뒤에 돌린다
python3 tools/make_v2.py dash.html v2.html
```

## 대시보드가 둘이다

| | 주소 | 누가 보나 |
| --- | --- | --- |
| 옛 대시보드 (팀장님 제작) | `artifact/EGzqReRqxyLWBAZZiLDjKv` | 팀장님 · 원천 데이터가 여기 있다 |
| 새 현황판 | `artifact/M1VQ4E5zfZdctNuTzejpqo` | 쉬운 말로 다시 그린 것 |

**옛 대시보드가 원천이다.** 판매·순위·펀딩은 거기에 먼저 넣고, 배포한 뒤,
`tools/make_v2.py` 로 현황판을 다시 만든다. 현황판만 따로 고치면 다음 갱신에 덮인다.
현황판의 화면(머리말·본문·자바스크립트)은 `tools/v2/` 에 있다.

현황판은 옛 대시보드가 가진 것을 **다 보여 준다** — 판매·광고·순위·펀딩에 더해
메타 광고 상세, 인스타·페북 게시물, 유튜브 영상, 볼라 짧은 링크, 썸네일까지.
썸네일이 base64 라 결과가 7MB 대가 되는데, 빼면 콘텐츠 줄이 글자 카드로 떨어진다.
바뀌는 건 **말**이지 내용이 아니다 — 「공급률」은 「출판사 몫」, 「CTR」은 「본 사람 중
누른 비율」로 적고, 맨 아래 「말 풀이」에 뜻을 달아 둔다.

정가와 공급률(65%)은 어느 원천에도 없는 계약 조건이라 `tools/make_v2.py` 안에 적혀 있다 —
바뀌면 거기를 고친다.

### 주 1회 — 소재별 주간 광고 성적

보고가 주 단위라 "이번 주에 뭐가 잘 됐나"가 필요한데, 아티팩트의 `payload` 에는 소재별 성적이
**캠페인 전 기간 누적**으로만 있다. 날짜별 소재 성적은 메타에 다시 물어야 나온다.

```
ads_get_ad_entities(ad_account_id='581875957830502', level='ad',
                    date_preset='last_7d', sort='spend_descending',
                    fields=['name','spend','impressions','reach','clicks','ctr','cpc','campaign_name'])
```

캠페인 이름으로 책을 가른 뒤 `tools/set_ads_week.py dash.html adsWeek.json` 으로 넣는다.
화면은 `to` 가 광고 기준일보다 이틀 넘게 뒤지면 「주 1회 갱신」 꼬리표를 단다.

세 스크립트 모두 **실패해도 파일을 건드리지 않고 SKIP 하고 끝납니다.** 순위가 하루 비는 것보다
판매·광고 갱신이 통째로 멈추는 쪽이 나쁘기 때문입니다. 그래서 순서에 상관없이 이어 돌려도 됩니다.

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

## 막힌 원천을 브라우저로 뚫기

클라우드 세션이 교보·유튜브·볼라에 못 나가는 건 정책이라 여기서 풀 수 없다.
대신 **사람 브라우저**로 받아오면 된다 — 같은 출처라 막힐 것이 없고 로그인 세션도 그대로 쓴다.

### 교보 순위

1. https://store.kyobobook.co.kr/bestseller/online/daily 를 연다
2. F12 → Console 에 `tools/collect-ranks-console.js` 전체를 붙여넣고 Enter
3. 화면에 뜨는 상자의 JSON 을 복사 (전체 선택돼 있으니 Ctrl+C)
4. 그 JSON 을 클로드에게 주면 — `python3 tools/apply_ranks_json.py dash.html ranks.json`

수집기는 `ranks.py` 와 같은 면·같은 순서로 훑고 산출물 모양도 같다. 면 하나가 실패해도
나머지는 그대로 나온다. 상품 페이지(주간베스트)는 출처가 달라 브라우저가 막을 수 있는데,
그때는 이전 값이 유지된다.

### 교보 펀딩

펀딩 페이지에서 모금액만 읽어 넣으면 달성률·적립 단계·예상 최종은 화면이 다시 계산한다.

```bash
python3 tools/set_funding.py dash.html pyoryu 4120000
```

### 유튜브 — 채널이 둘이다

| 채널 | 주소 | 블록 |
| --- | --- | --- |
| 1분지혜 (우리) | `UC_eCtsz2CxxDgTzev6kroOQ` | `ytData` |
| 1분수업 (브랜드미디어팀) | `@1min_th1` | `ytData2` |

```bash
python3 tools/youtube.py dash.html                                      # 1분지혜
python3 tools/youtube.py --channel @1min_th1 --block ytData2 dash.html   # 1분수업
```

커넥터도 API 키도 안 쓴다 — 채널 공개 페이지를 긁는다. 그래서 **유튜브로 나가는 길이
열린 환경(필로틱)에서만** 돈다. 블록이 없으면 `payload` 앞에 빈 블록을 만들어 넣고 이어간다.

화면 쪽은 `ytBlock(k, Y, ch)` · `ytChannelBlock(Y, ch)` 가 채널을 인자로 받으므로
세 번째 채널이 생기면 `ytData3` 블록과 호출 한 줄만 더하면 된다.

**1분수업에는 단축링크를 안 걸어 뒀다.** 그래서 클릭 칸이 「셀 수 없음」으로 뜬다 —
0 이라고 적으면 아무도 안 눌렀다는 뜻이 되어 거짓말이 된다. 링크를 걸면
`volaDaily.chan[책].Y2` 에 코드를 넣으면 그때부터 숫자가 뜬다.

윈저에 `youtube` 커넥터도 있다(OAuth). 공개 페이지로 못 얻는 저장·공유·댓글을 받으려면
연결해야 한다: https://onboard.windsor.ai/connect?connector=youtube&next=/youtube/authorize

## 어느 환경에서 도는지가 중요하다

같은 대시보드를 고치더라도 **세션이 어느 클라우드 환경에 있느냐**에 따라 되는 일이 다르다.

| 환경 | 네트워크 | 되는 것 |
| --- | --- | --- |
| **필로틱** (`env_01Dh1RCn6iVCQmC8j9vXgBW8`) | Custom · `*.kyobobook.co.kr` 허용 | 교보 순위·펀딩 **자동** |
| 기본(Default) | Trusted | 판매 시트·메타·인스타·페북만 |

기본 환경에서는 교보로 나가는 길이 조직 정책에 막혀 있다(`CONNECT 403`). 그래서
**교보 순위와 펀딩은 `필로틱` 환경의 루틴**(`trig_017i2zrDXyF4Z6PdNGinp2Rv`, 매일 11:10 KST)이 맡는다.
기본 환경 세션에서 급히 순위를 채워야 하면 그 루틴을 즉시 발사(`fire_trigger`)하면 된다 —
막힌 길을 우회하려 들지 말 것.

`update_trigger` 로는 루틴의 환경을 못 옮긴다. 옮기려면 새로 만들어야 한다.

### 환경 네트워크 정책을 여는 법 (새 환경을 만들 때)

세션 화면의 **구름 아이콘 → 환경 편집 → Network access → Custom** 을 고르고
**Allowed domains** 에 아래를 한 줄씩 넣는다. **「Also include default list of
common package managers」를 반드시 체크**한다 — 안 하면 적어 넣은 것만 남고
npm·pypi 같은 기본 목록이 통째로 빠진다.

```
*.kyobobook.co.kr
vo.la
*.youtube.com
```

접근 수준은 None / Trusted(기본) / Full / Custom 네 가지고, 환경마다 따로 잡는다.
조직 전체에 밀어 넣는 허용목록은 없다 — 환경을 쓰는 사람이 각자 잡아야 한다.
문서: https://code.claude.com/docs/en/cloud-environments#network-access

**열면 자동이 되는 것** — 교보 순위, 교보 펀딩 (둘 다 로그인 없는 공개 데이터).
**열어도 안 되는 것** — 볼라(로그인 필요), 판매 시트(서점 포털 로그인 필요).
이 둘은 이전 담당자도 브라우저에서 수기로 받아 넣었다.
유튜브는 allowlist 와 무관하다 — MCP 커넥터 트래픽은 앤트로픽 서버를 거치므로
윈저 커넥터만 붙이면 된다.

`tools/ranks.py` 안의 `API_KEY` 는 교보 공개 베스트셀러 화면이 쓰는 게이트웨이 키입니다.
교보가 키를 갈면 403 이 나므로, 그때는 `store.kyobobook.co.kr/bestseller/online/daily` 의
네트워크 탭에서 `x-api-gw-key` 를 새로 복사해 넣어야 합니다 — 스크립트가 그 사유를 찍어 줍니다.

## 루틴 목록

| 루틴 | 트리거 ID | 언제 | 환경 |
| --- | --- | --- | --- |
| 대시보드 자동 갱신 (판매 + 광고) | `trig_01YQJN4Hc7zcWU7oK8kPVWKD` | 09:00 · 18:00 ※ | 기본 |
| 필로틱 교보·볼라·유튜브(2채널) | `trig_017i2zrDXyF4Z6PdNGinp2Rv` | 11:10 | 필로틱 |
| **필로틱 현황판 자동 갱신** | `trig_01HjFwZ3JqhGQhPPzLYUPQiF` | 12:00 | 기본 |
| 대시보드 갱신 감시 (워치독) | `trig_01KQ1DfNSHSLDJE7jm8QaExo` | 10:00 | 기본 |

급할 때는 `fire_trigger` 로 즉시 돌릴 수 있다. 순서는 지켜라 — 순위를 받기 전에
현황판을 만들면 어제 순위가 실린다.

**현황판 루틴은 커넥터를 안 쓴다.** 아티팩트를 읽고 `tools/make_v2.py` 를 돌려 배포하는 게
전부라서, 구글 드라이브·메타 같은 커넥터가 없어도 돈다. 반대로 **커넥터가 필요한 일은
이 루틴에 넣으면 안 된다** — 트리거가 커넥터를 들고 가지 못한다.

## 알려진 문제

- **`ranksPy` 블록을 갈아끼울 때는 `</script>` 를 이스케이프해야 한다** (2026-09-18 확인).
  그 스크립트 소스에는 `'</script>'` 라는 문자열이 들어 있다. 날것으로 넣으면 브라우저가
  거기서 블록을 닫아 버리고, 뒤에 남은 4천 자가 **화면 아래에 파이썬 코드로 그대로 보인다.**
  실제로 며칠 그 상태로 배포돼 있었다. 넣을 때 이렇게 한다.

  ```python
  enc = json.dumps(src, ensure_ascii=False).replace('</script', r'<\/script')
  ```

  JSON 의 `\/` 는 `/` 로 되읽히므로 값은 그대로다. 넣은 뒤 **브라우저로 한 번 열어**
  `document.body` 직속에 긴 텍스트 노드가 없는지 확인하는 게 확실하다.

- **'교보 순위 수집 실패' 는 네트워크 탓이 아닐 수 있다** (2026-09-18 해결).
  사유가 `Expecting value: line 1 column 1 (char 0)` 이면 **응답이 gzip 인데 안 풀린 것**이다.
  교보 게이트웨이는 `Accept-Encoding` 을 안 보내도 압축해 답할 때가 있다. 지금은
  `tools/ranks.py` 가 헤더와 바이트 첫머리(`1f 8b`)를 둘 다 보고 풀어 주고, JSON 이 아니면
  어느 면·HTTP 몇·앞 160자를 사유에 적는다. 사유를 먼저 읽고 판단할 것.

- **자동 갱신 루틴이 우서전지 탭을 빠뜨린다** (2026-09-16 확인). 09-10~09-15 엿새치
  166부가 대시보드에 한 줄도 안 들어와 있었다. 다른 네 권은 같은 기간 정상이었다.
  루틴이 쓰는 시트 읽기 로직이 `tools/merge_sales.py` 와 달라서로 보인다 —
  루틴을 이 스크립트로 갈아끼우는 쪽이 낫다. 그전까지는 수동 실행으로 메워야 한다.

## 아직 사람이 해야 하는 두 가지 (2026-10-01 기준)

클로드가 못 고치는 것들이다. 이유도 같이 적어 둔다 — 다음 사람이 또 헤매지 않게.

### 1. 필로틱 환경 네트워크 허용목록에 두 줄 추가

```
www.instagram.com
www.facebook.com
```

인스타·페북 **썸네일**을 못 받아 최근 콘텐츠 칸이 글자 카드로 뜬다(2026-10-01 기준 인스타 25장·
페북 16장 비어 있음). 허용목록은 **환경을 쓰는 사람이 설정 화면에서** 잡아야 한다 — API 로 바꿀 수 없다.

유튜브 썸네일(`i.ytimg.com`)은 **Default 환경에서 막혀 있다** (2026-10-02 확인: `curl` 이 `000`,
프록시가 `connect_rejected`). 그래서 `tools/thumbs.py` 는 11:10 **필로틱** 루틴에서 돈다.
12시 Default 루틴이 도는 `thumbs.py` 는 인스타·페북 칸만 채운다. 한 도구가 두 환경에서
각자 되는 칸만 채우는 구조다 — 이상해 보이지만 망이 그렇게 갈려 있어서 그렇다.

### 2. 판매·광고 루틴 시각을 09:00 → 11:40 으로

`trig_01YQJN4Hc7zcWU7oK8kPVWKD` — 판매 시트가 **11시**에 채워지는데 이 루틴이 **09시**에 읽으므로,
12시 현황판이 하루 묵은 판매를 들고 간다. 저녁 18:00 치는 그대로 둬도 된다.

이 루틴은 웹 화면에서 만들어진 것(`created_via: http_api`)이라 **에이전트가 고칠 수 없다** —
`update_trigger` 가 거부한다. 에이전트가 만든 루틴만 에이전트가 고칠 수 있다.
사람이 https://claude.ai/code/routines/trig_01YQJN4Hc7zcWU7oK8kPVWKD 에서 바꿔야 한다.
