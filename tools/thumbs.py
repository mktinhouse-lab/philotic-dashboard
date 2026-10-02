#!/usr/bin/env python3
"""대시보드 `thumbs` 블록에 빠진 썸네일을 채운다.

받아오는 곳
  유튜브 : https://i.ytimg.com/vi/<id>/hqdefault.jpg
           막혀 있으면 https://img.youtube.com/vi/<id>/hqdefault.jpg
  인스타 : https://www.instagram.com/p/<shortcode>/ 의 og:image
           비면 https://www.instagram.com/p/<shortcode>/embed/captioned/ 의 display_url
  페북   : https://www.facebook.com/<페이지id>/posts/<글id> 의 og:image
  그림   : scontent*.cdninstagram.com · scontent*.fbcdn.net

인스타·페북은 이 환경에 커넥터가 없어 공개 페이지에서 og:image 를 읽는 수밖에 없다.
그런데 둘 다 보통 브라우저 User-Agent 로 받으면 자바스크립트 껍데기나 로그인 담만 오고
og 메타가 없다. 크롤러 User-Agent(PAGE_UA)로 받아야 서버가 메타를 그려 준다.
페북은 글 번호만으로는 로그인 담이 뜬다. `<페이지id>/posts/<글id>` 꼴이어야 공개로 열린다.
로그인하지 않는다. 그 주소가 환경 허용목록에 없으면(CONNECT tunnel failed) 건너뛰고 보고만 한다.
우회하지 않고, 없는 그림을 지어내지도 않는다.

쓰는 블록은 `thumbs` 하나뿐이다. payload·ytData 등 다른 블록은 건드리지 않는다.
"""

import base64
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

MAX_W = 320          # 가로 320px 안쪽으로 줄인다
MAX_BYTES = 15360    # 한 장 15KB 를 넘기지 않는다 (base64 전 원본 기준)
BLOCK_LIMIT = 12 * 1024 * 1024   # 블록이 이보다 커지면 오래된 것부터 버린다
TIMEOUT = 30
# 공개 페이지는 몰아치면 429 가 난다. 한 장 받을 때마다 이만큼 쉰다.
DELAY = float(os.environ.get("THUMBS_DELAY", "1.2"))
RETRY_429 = (20, 60)   # 429 가 나면 이 초만큼 쉬었다가 다시 해 본다

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

# 인스타·페북 공개 페이지는 이 User-Agent 라야 og 메타를 그려 준다.
PAGE_UA = ("facebookexternalhit/1.1 "
           "(+http://www.facebook.com/externalhit_uatext.php)")

YT_HOSTS = ["https://i.ytimg.com/vi/{id}/hqdefault.jpg",
            "https://img.youtube.com/vi/{id}/hqdefault.jpg"]
IG_PAGES = ["https://www.instagram.com/p/{id}/",
            "https://www.instagram.com/p/{id}/embed/captioned/"]
# payload.fbPage("1분 지혜") 의 페이지 번호. 글 번호만 쓰면 로그인 담이 뜬다.
FB_PAGE_ID = "1003587992847027"
FB_PAGES = ["https://www.facebook.com/%s/posts/{id}" % FB_PAGE_ID]


# ---------------------------------------------------------------- 블록 입출력

def find_block(html, bid):
    """<script id="bid" type="application/json"> ... </script> 의 안쪽 범위."""
    m = re.search(r'<script id="%s" type="application/json">' % re.escape(bid), html)
    if not m:
        raise SystemExit("블록을 찾지 못했다: %s" % bid)
    start = m.end()
    end = html.index("</script>", start)
    return start, end


def read_block(html, bid, required=True):
    """없어도 되는 블록은 required=False — 빈 통을 돌려준다.
    (ytData2 는 두 번째 유튜브 채널을 처음 긁는 날까지 없다)"""
    if not required and ('<script id="%s" type="application/json">' % bid) not in html:
        return {}
    start, end = find_block(html, bid)
    return json.loads(html[start:end])


def dump_block(obj):
    """JSON 안의 `</script` 를 `<\\/script` 로 바꿔야 블록이 안 끊긴다."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")) \
               .replace("</script", r"<\/script")


# ---------------------------------------------------------------- 내려받기

def fetch(url, referer=None, ua=UA):
    """(bytes, content_type) 또는 예외."""
    headers = {"User-Agent": ua, "Accept-Language": "ko,en;q=0.8"}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read(), (r.headers.get("Content-Type") or "")


def reachable(url):
    """허용목록에 있는지만 본다. 403/404 라도 연결 자체가 됐으면 열린 것이다."""
    try:
        fetch(url)
        return True, "ok"
    except urllib.error.HTTPError as e:
        return True, "HTTP %s" % e.code
    except Exception as e:
        return False, str(e).strip()[:120]


# ---------------------------------------------------------------- 줄이기

def shrink(raw):
    """가로 MAX_W 안쪽 · MAX_BYTES 안쪽의 JPEG 바이트로 만든다."""
    from PIL import Image

    im = Image.open(io.BytesIO(raw))
    im = im.convert("RGB")
    if im.width > MAX_W:
        im = im.resize((MAX_W, max(1, round(im.height * MAX_W / im.width))),
                       Image.LANCZOS)
    for q in (72, 62, 54, 46, 38, 30, 24):
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=q, optimize=True, progressive=True)
        if buf.tell() <= MAX_BYTES:
            return buf.getvalue()
    # 품질을 끝까지 낮춰도 안 되면 가로를 한 번 더 줄인다
    im = im.resize((MAX_W // 2, max(1, im.height * (MAX_W // 2) // im.width)),
                   Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=40, optimize=True, progressive=True)
    return buf.getvalue()


def as_data_uri(raw):
    return "data:image/jpeg;base64," + base64.b64encode(shrink(raw)).decode("ascii")


# ---------------------------------------------------------------- og:image

OG = re.compile(
    r'<meta[^>]+(?:property|name)=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.I)
OG2 = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:image["\']',
    re.I)


# 임베드 페이지에는 og 가 없고 JSON 조각 안에 그림 주소가 들어 있다.
JSON_SRC = re.compile(
    r'"(?:display_url|thumbnail_src|src)"\s*:\s*"(https:[^"]+?\.(?:jpg|jpeg|webp)[^"]*)"', re.I)
LOGIN_WALL = re.compile(r'login_form|'
                        r'You must log in|\uB85C\uADF8\uC778\uD558\uC5EC', re.I)


def image_src(text):
    """페이지 HTML 에서 그림 주소 하나를 찾는다."""
    m = OG.search(text) or OG2.search(text)
    if m:
        return m.group(1).replace("&amp;", "&")
    m = JSON_SRC.search(text)
    if m:
        return m.group(1).encode().decode("unicode_escape").replace("&amp;", "&")
    return None


def page_image(page_urls):
    """공개 페이지 후보를 차례로 열어 첫 번째로 나오는 그림을 받아 온다."""
    why = []
    for page_url in page_urls:
        html, err = None, "429 가 걷히지 않는다"
        for wait in (0,) + RETRY_429:
            if wait:
                time.sleep(wait)
            try:
                html, _ = fetch(page_url, ua=PAGE_UA)
                break
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    continue          # 몰아쳐서 막힌 것이니 쉬었다 다시
                err = "HTTP %s" % e.code
                break
            except Exception as e:
                err = str(e).strip()[:60]
                break
        if html is None:
            why.append(err)
            continue
        text = html.decode("utf-8", "replace")
        src = image_src(text)
        if not src:
            why.append("로그인 담" if LOGIN_WALL.search(text) else "그림 주소 없음")
            continue
        raw, ctype = fetch(src, referer=page_url, ua=PAGE_UA)
        if "image" not in ctype:
            why.append("그림이 아니다: %s" % ctype[:30])
            continue
        return raw
    raise ValueError(" / ".join(dict.fromkeys(why)) or "열리지 않음")


# ---------------------------------------------------------------- 빠진 것 세기

def wanted(payload, *ytdatas):
    """{종류: {키: 날짜}} — 날짜는 오래된 것부터 버릴 때 쓴다.

    유튜브는 채널이 둘이다(ytData=1분지혜, ytData2=1분수업). 썸네일은 영상 id 로
    저장하니 한 통에 같이 담아도 섞이지 않는다."""
    ig, fb, yt = {}, {}, {}
    for book in (payload.get("books") or {}).values():
        for row in book.get("igPosts") or []:
            if len(row) > 7 and row[7]:
                ig[row[7]] = row[0]
        for row in book.get("fbPosts") or []:
            if len(row) > 7 and row[7]:
                fb[row[7]] = row[0]
    for ytdata in ytdatas:
        for book in (ytdata.get("books") or {}).values():
            for v in book.get("videos") or []:
                if v and v[0]:
                    yt[v[0]] = v[2] if len(v) > 2 else ""
    return {"ig": ig, "fb": fb, "yt": yt}


def prune(thumbs, dates):
    """블록이 한계를 넘으면 오래된 것부터 버린다. 화면은 최근 것만 쓴다."""
    dropped = 0
    while len(dump_block(thumbs).encode("utf-8")) > BLOCK_LIMIT:
        oldest, kind = None, None
        for k in ("ig", "fb", "yt", "ad"):
            for key in thumbs.get(k) or {}:
                d = dates.get(k, {}).get(key, "")   # 모르는 키는 가장 오래된 것으로 본다
                if oldest is None or d < oldest[0]:
                    oldest, kind = (d, key), k
        if oldest is None:
            break
        del thumbs[kind][oldest[1]]
        dropped += 1
    return dropped


# ---------------------------------------------------------------- 본체

def main(path):
    html = open(path, encoding="utf-8").read()
    thumbs = read_block(html, "thumbs")
    need = wanted(read_block(html, "payload"),
                  read_block(html, "ytData"),
                  read_block(html, "ytData2", required=False))

    for k in ("ig", "fb", "yt"):
        thumbs.setdefault(k, {})

    missing = {k: {i: d for i, d in v.items() if i not in thumbs[k]}
               for k, v in need.items()}
    print("빠진 것  인스타 %d · 페북 %d · 유튜브 %d"
          % (len(missing["ig"]), len(missing["fb"]), len(missing["yt"])))

    # 어디가 열렸는지 먼저 본다 -------------------------------------------
    print("\n[망 확인]")
    yt_tmpl = None
    for tmpl in YT_HOSTS:
        host = tmpl.split("/vi/")[0]
        ok, why = reachable(tmpl.format(id="gQzMdQWPkvw"))
        print("  %-34s %s %s" % (host, "열림" if ok else "막힘", why))
        if ok and yt_tmpl is None:
            yt_tmpl = tmpl

    ig_ok, ig_why = reachable("https://www.instagram.com/")
    print("  %-34s %s %s" % ("https://www.instagram.com", "열림" if ig_ok else "막힘", ig_why))
    fb_ok, fb_why = reachable("https://www.facebook.com/")
    print("  %-34s %s %s" % ("https://www.facebook.com", "열림" if fb_ok else "막힘", fb_why))

    # 페북이 인스타보다 잘 받힌다. 하나도 못 받고 끝나지 않게 페북부터 돈다.
    jobs = [("fb", missing["fb"], FB_PAGES if fb_ok else None, False,
             None if fb_ok else "facebook.com 이 막혔다: %s" % fb_why),
            ("ig", missing["ig"], IG_PAGES if ig_ok else None, False,
             None if ig_ok else "instagram.com 이 막혔다: %s" % ig_why),
            ("yt", missing["yt"], [yt_tmpl] if yt_tmpl else None, True,
             None if yt_tmpl else "유튜브 주소가 모두 막혔다")]

    got = {"ig": 0, "fb": 0, "yt": 0}
    skipped = {}
    failed = {"ig": [], "fb": [], "yt": []}

    print("\n[받기]")
    for kind, want, tmpls, direct, reason in jobs:
        if not want:
            continue
        if tmpls is None:
            skipped[kind] = reason
            print("  %s: %d 장 건너뜀 — %s" % (kind, len(want), reason))
            continue
        for n, key in enumerate(sorted(want, key=lambda k: want[k])):
            urls = [t.format(id=key) for t in tmpls]
            if not direct and n:
                time.sleep(DELAY)
            try:
                if direct:                       # 그림 주소를 바로 안다
                    raw, ctype = fetch(urls[0])
                    if "image" not in ctype:
                        raise ValueError("그림이 아니다: %s" % ctype[:40])
                else:                            # 공개 페이지에서 그림 주소를 찾는다
                    raw = page_image(urls)
                thumbs[kind][key] = as_data_uri(raw)
                got[kind] += 1
                print("  %s %s  %s  %.1fKB"
                      % (kind, key, want[key],
                         len(thumbs[kind][key]) * 3 / 4 / 1024))
            except Exception as e:
                failed[kind].append((key, str(e).strip()[:100]))
                print("  %s %s  실패 — %s" % (kind, key, str(e).strip()[:100]))

    total = sum(got.values())
    print("\n새로 받은 것  페북 %d · 인스타 %d · 유튜브 %d  (합 %d)"
          % (got["fb"], got["ig"], got["yt"], total))
    if total == 0:
        print("한 장도 못 받았다. 파일을 고치지 않는다.")
        return 1

    dropped = prune(thumbs, need)
    if dropped:
        print("블록이 한계를 넘어 오래된 것 %d 장을 버렸다." % dropped)

    body = dump_block(thumbs)
    start, end = find_block(html, "thumbs")
    out = html[:start] + body + html[end:]

    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(out)

    # 되읽어 확인한다 ------------------------------------------------------
    check = read_block(open(tmp, encoding="utf-8").read(), "thumbs")
    for k in ("ig", "fb", "yt"):
        if len(check.get(k, {})) != len(thumbs[k]):
            os.unlink(tmp)
            raise SystemExit("되읽기가 어긋났다: %s" % k)
    os.replace(tmp, path)

    print("블록 크기 %.2f MB  (인스타 %d · 유튜브 %d · 페북 %d · 광고 %d)"
          % (len(body.encode("utf-8")) / 1024 / 1024,
             len(check["ig"]), len(check["yt"]), len(check["fb"]),
             len(check.get("ad") or {})))

    print("\n[아직 빠진 것]")
    for kind in ("fb", "ig", "yt"):
        left = [i for i in need[kind] if i not in check.get(kind, {})]
        if not left:
            continue
        why = skipped.get(kind) or "받기 실패 %d 건" % len(failed[kind])
        print("  %s %d 장 — %s" % (kind, len(left), why))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "dash.html"))
