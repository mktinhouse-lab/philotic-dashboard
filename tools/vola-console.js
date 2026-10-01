/* 볼라(vo.la) 누적 클릭수 받아오기 — 브라우저 콘솔용
 * ────────────────────────────────────────────────────────────
 * 왜 사람 손이 필요한가
 *   볼라는 로그인해야 숫자가 보인다. 클라우드 세션은 vo.la 로 나가지도 못한다
 *   (프록시가 CONNECT 403 으로 막는다). CSV 내보내기는 프로 결제 전용이다.
 *   그래서 로그인한 브라우저가 유일한 통로다.
 *
 * 쓰는 법
 *   1) 로그인한 채 https://vo.la/user/links 를 연다
 *   2) F12 → Console. 처음이면 `allow pasting` 을 **직접 타이핑**하고 Enter
 *      (크롬이 붙여넣기를 막아 둔다)
 *   3) 맨 아래 한 줄을 통째로 붙여넣고 Enter → 3~5초
 *   4) 화면이 흰 바탕 목록으로 바뀐다. 그 화면을 캡처해 클로드에게 준다
 *      (원래 화면은 새로고침하면 돌아온다)
 *
 * 왜 캡처인가 — 클립보드는 중간에 캡처를 뜨면 날아가고, 프로그램이 거는 다운로드는
 * 크롬이 막는다. 화면에 띄워서 찍는 게 제일 덜 깨진다.
 *
 * 받는 것은 **링크별 누적 클릭수**다. 일별이 아니다.
 * 그래서 `tools/set_vola_totals.py` 가 `daily` 는 두고 `total` 만 고친다.
 *
 * 긴 스크립트는 붙여넣다 잘려서 실행이 안 된다 — 그래서 한 줄로 유지한다.
 */

(async()=>{const M=new Map();const put=t=>{t=t.replace(/\s+/g,' ').trim();const c=(t.match(/vo\.la\/(\S+)/)||[])[1];const n=(t.match(/(\d[\d,]*)\s+\S*\s*(?:이전|오늘|전)/)||[])[1];if(c)M.set(c,n||'?')};for(let p=1;p<=15;p++){const r=await fetch('/user/links?page='+p);const d=new DOMParser().parseFromString(await r.text(),'text/html');const a=[...d.querySelectorAll('a[href*="/stats"]')];if(!a.length)break;a.forEach(x=>{let b=x;for(let i=0;i<7&&b&&b.textContent.replace(/\s/g,'').length<24;i++)b=b.parentElement;if(b)put(b.textContent)})}const L=[...M];document.body.innerHTML='<pre style="font:700 15px/1.45 monospace;padding:16px;background:#fff;color:#111;column-count:4">총 '+L.length+'\n'+L.map(([k,v])=>k+' '+v).join('\n')+'</pre>'})()
