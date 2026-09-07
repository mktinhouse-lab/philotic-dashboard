'use strict';
const fs = require('fs');
const { google } = require('googleapis');
const { cellMatchesDate, sheetLabel } = require('./dates');

/**
 * 구글시트 접근. 서비스 계정 키(JSON) 사용.
 *  - 환경변수 GOOGLE_SERVICE_ACCOUNT_KEY=키파일 경로 (기본 ./service-account.json)
 *  - 시트를 서비스 계정 이메일(client_email)에 '편집자'로 공유해 둘 것.
 */
class SheetClient {
  constructor(spreadsheetId, { keyFile, sheetsApi } = {}) {
    this.spreadsheetId = spreadsheetId;
    this.keyFile = keyFile;
    this.api = sheetsApi || null; // 테스트 주입용
    this.titleByGid = null;
    this.colCache = new Map();
  }

  async init() {
    if (!this.api) {
      const keyFile = this.keyFile || process.env.GOOGLE_SERVICE_ACCOUNT_KEY || 'service-account.json';
      if (!fs.existsSync(keyFile)) {
        throw new Error(`서비스 계정 키 파일이 없습니다: ${keyFile}\n` +
          '  GOOGLE_SERVICE_ACCOUNT_KEY 환경변수로 경로를 지정하거나 scripts/sales-routine/service-account.json 으로 두세요.');
      }
      const auth = new google.auth.GoogleAuth({ keyFile, scopes: ['https://www.googleapis.com/auth/spreadsheets'] });
      this.api = google.sheets({ version: 'v4', auth });
    }
    const meta = await this.api.spreadsheets.get({ spreadsheetId: this.spreadsheetId, fields: 'sheets.properties(sheetId,title)' });
    this.titleByGid = new Map(meta.data.sheets.map((s) => [s.properties.sheetId, s.properties.title]));
    return this;
  }

  titleForGid(gid) {
    const t = this.titleByGid.get(gid);
    if (!t) throw new Error(`gid=${gid} 탭을 찾을 수 없습니다.`);
    return t;
  }

  quote(title) { return `'${title.replace(/'/g, "''")}'`; }

  async columnA(title) {
    if (this.colCache.has(title)) return this.colCache.get(title);
    const res = await this.api.spreadsheets.values.get({
      spreadsheetId: this.spreadsheetId,
      range: `${this.quote(title)}!A1:A3000`,
      valueRenderOption: 'FORMATTED_VALUE',
    });
    const vals = (res.data.values || []).map((r) => (r && r[0] != null ? String(r[0]) : ''));
    this.colCache.set(title, vals);
    return vals;
  }

  /** 날짜에 해당하는 1-based 행 번호. 없으면 null. */
  async findRow(title, date) {
    const col = await this.columnA(title);
    const hits = [];
    col.forEach((v, i) => { if (cellMatchesDate(v, date)) hits.push(i + 1); });
    if (hits.length > 1) throw new Error(`${title}: ${sheetLabel(date)} 행이 ${hits.length}개(${hits.join(',')})입니다. 시트를 확인하세요.`);
    return hits[0] || null;
  }

  /** A~I 표시값 배열 */
  async readRow(title, row) {
    const res = await this.api.spreadsheets.values.get({
      spreadsheetId: this.spreadsheetId,
      range: `${this.quote(title)}!A${row}:I${row}`,
      valueRenderOption: 'FORMATTED_VALUE',
    });
    return (res.data.values && res.data.values[0]) || [];
  }

  /** writes: [{title,row,col,value}] → 한 번의 batchUpdate. 숫자는 RAW로 넣어 숫자 타입 유지. */
  async writeCells(writes) {
    if (!writes.length) return 0;
    const data = writes.map((w) => ({ range: `${this.quote(w.title)}!${w.col}${w.row}`, values: [[w.value]] }));
    await this.api.spreadsheets.values.batchUpdate({
      spreadsheetId: this.spreadsheetId,
      requestBody: { valueInputOption: 'RAW', data },
    });
    return writes.length;
  }
}

module.exports = { SheetClient };
