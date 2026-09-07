# 필로틱 출판 일별 판매 입력 루틴 (자동화)

`/pilotic-sales-routine` 스킬의 절차를 그대로 코드로 옮긴 도구입니다.
예스24·알라딘·교보·영풍 4개 포털에서 ISBN별 일 판매량을 조회해
[판매 시트](https://docs.google.com/spreadsheets/d/1d8Cll3n8ZxUtaqF5acSn9FekjsD8_4IuO33KkDklqB8/edit)의 책 탭에 기록합니다.

## 준비 (최초 1회)

1. Node 18+ 설치 후
   ```bash
   cd scripts/sales-routine
   npm install
   npx playwright install chromium
   ```
2. **구글시트 API용 서비스 계정**
   - Google Cloud 콘솔에서 프로젝트 생성 → "Google Sheets API" 사용 설정 → 서비스 계정 생성 → JSON 키 다운로드.
   - 키 파일을 `scripts/sales-routine/service-account.json`으로 저장(또는 `GOOGLE_SERVICE_ACCOUNT_KEY=경로`).
   - 판매 시트를 서비스 계정 이메일(`client_email`)에 **편집자**로 공유.
3. **포털 로그인** (라이프해킹 계정, 세션은 `profile/`에 저장됨)
   ```bash
   npm run login
   ```
   브라우저가 포털을 차례로 열어 주면 직접 로그인하고 터미널에서 Enter.
   영풍은 세션이 자주 끊기므로 실행 중 `ypbooks: 로그인 필요`가 뜨면 다시 `npm run login`.

## 매일 실행

```bash
npm run routine
```

- 기본: **어제까지 최근 3일**을 대상으로, 각 탭에서 **비어 있는 셀만** 채웁니다.
  교보(하루 지연)·영풍(며칠 지연) 미집계분은 이 방식으로 다음 실행 때 자동 백필됩니다.
- 0인 값은 공란으로 둡니다(스킬 규칙). 이미 값이 있는 셀은 건드리지 않고, 값이 다르면 `[기존값 유지: …]`로 알려줍니다. 덮어쓰려면 `--force`.
- 실행 후 셀을 다시 읽어 기록값을 검증하고 각 책의 종계를 출력합니다.

옵션:

| 옵션 | 설명 |
|---|---|
| `--date 2026-09-06` | 특정 날짜만 |
| `--from A --to B` | 기간 백필 |
| `--days N` | 어제까지 N일 (기본 3) |
| `--portals yes24,aladin` | 일부 포털만 (교보·영풍 미집계 시) |
| `--dry-run` | 시트에 쓰지 않고 계획만 출력 |
| `--force` | 기존 값 덮어쓰기 |
| `--headed` | 브라우저를 보이게 실행 |
| `--debug` | 포털 페이지 텍스트/HTML/스크린샷을 `debug/`에 저장 |

## 시트 규칙 (config.js)

- 탭은 gid로 찾고, 행은 A열 표시값(`26.09.06(일)`)으로 찾습니다. 행 번호를 계산하지 않으므로 행이 추가돼도 안전합니다.
- 일반 탭: B=교보(오프) C=교보(온라인) D=교보(법인) F=예스24 G=알라딘 H=영풍. E·I는 수식이라 쓰지 않음.
- 구형 탭(무한의부·세네카): H가 총계 수식이라 **영풍 값을 쓰지 않습니다**.
- 교보 '인터파크' 열은 무시, 북센은 시트 입력 없음.

## 포털 파서가 깨졌을 때

포털 화면 구조가 바뀌면 `--debug`로 실행해 `debug/` 아래 파일을 확인하고 `portals/*.js`의 파서(`parse*` 함수)를 고치면 됩니다.
파서는 순수 함수라 `test/`에 표 예시를 넣어 검증할 수 있습니다: `npm test`.
교보는 ISBN 열이 없을 경우 도서명으로 매칭하므로, 실제 교보 상품명과 다르면 `config.js`의 `aliases`를 보완하세요.
