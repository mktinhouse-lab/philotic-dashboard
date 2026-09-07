'use strict';
// 필로틱 출판 판매 시트 설정. 탭은 gid로 찾으므로 탭 이름이 바뀌어도 동작한다.
module.exports = {
  spreadsheetId: '1d8Cll3n8ZxUtaqF5acSn9FekjsD8_4IuO33KkDklqB8',

  // layout 'new': B=교보(오프) C=교보(온라인) D=교보(법인) E=교보합계(수식) F=예스24 G=알라딘 H=영풍 I=총계(수식)
  // layout 'old': 영풍(H) 열 없음. H=총계(수식) → 절대 쓰지 않는다.
  books: [
    { name: '칼융',       gid: 945888298,  isbn: '9791199903432', layout: 'new', aliases: ['칼 융', '칼융'] },
    { name: '완벽한원시인', gid: 531715772,  isbn: '9791199383074', layout: 'new', aliases: ['완벽한 원시인', '완벽한원시인'] },
    { name: '프로이트',    gid: 1759849039, isbn: '9791199383012', layout: 'new', aliases: ['프로이트'] },
    { name: '강풍',       gid: 60434594,   isbn: '9791199383043', layout: 'new', aliases: ['강풍'] },
    { name: '상향혼',      gid: 1277331930, isbn: '9791199903418', layout: 'new', aliases: ['상향혼'] },
    { name: '라이프코드',   gid: 813674496,  isbn: '9791199383005', layout: 'new', aliases: ['라이프코드', '라이프 코드'] },
    { name: '1조원',      gid: 1713133736, isbn: '9791198713681', layout: 'new', aliases: ['1조원', '1조 원'] },
    { name: '지적생활',    gid: 1248212513, isbn: '9791198713667', layout: 'new', aliases: ['지적생활', '지적 생활'] },
    { name: '무한의부',    gid: 910841241,  isbn: '9791198713636', layout: 'old', aliases: ['무한의 부', '무한의부'] },
    { name: '세네카',      gid: 455940662,  isbn: '9791198713629', layout: 'old', aliases: ['세네카'] },
  ],

  columns: {
    kyoboOff: 'B',
    kyoboOn: 'C',
    kyoboCorp: 'D',
    yes24: 'F',
    aladin: 'G',
    ypbooks: 'H', // layout 'new' 전용
  },
  totalColumn: { new: 'I', old: 'H' },

  portals: {
    yes24: {
      page: 'https://scm.yes24.com/AnalysisManagement/ListSaleAnalysisGoods',
      api: '/api/AnalysisManagement/ListSaleAnalysisGoods',
    },
    aladin: { page: 'https://www.aladin.co.kr/supplier/wStatSalesBook.aspx' },
    kyobo: { page: 'https://scm.kyobobook.co.kr/scm/page.action?pageID=saleStockInfo' },
    ypbooks: { page: 'https://ypscm.ypbooks.co.kr/salehistory/index', searchClickFallback: { x: 82, y: 278 } },
    booxen: { page: 'https://orderbook.booxen.com/' }, // 참고 확인만. 시트 입력 없음.
  },
};
