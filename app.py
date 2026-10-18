"""Instagram link -> Sr. No, Page Name, Profile Link, Followers.

Run:  python3 app.py        (PORT env var optional, default 8000)
Only uses the Python standard library.
"""
import html
import json
import os
import re
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UA = "facebookexternalhit/1.1"


def username_from(link):
    link = link.strip()
    m = re.search(r"instagram\.com/([A-Za-z0-9._]+)", link)
    if m:
        name = m.group(1)
        if name.lower() in {"p", "reel", "reels", "tv", "stories", "explore"}:
            return None  # post/reel link, not a profile link
        return name
    if re.fullmatch(r"@?[A-Za-z0-9._]+", link):
        return link.lstrip("@")
    return None


def meta(page, prop):
    m = re.search(r'<meta property="%s" content="([^"]*)"' % re.escape(prop), page)
    return html.unescape(m.group(1)) if m else ""


def to_number(text):
    """'268K' -> 268000, '1.2M' -> 1200000, '1,234' -> 1234"""
    mult = {"K": 1000, "M": 1000000, "B": 1000000000}
    text = text.replace(",", "")
    if text and text[-1] in mult:
        return int(round(float(text[:-1]) * mult[text[-1]]))
    return int(float(text))


def lookup(link):
    user = username_from(link)
    if not user:
        return {"input": link, "error": "Not a profile link"}
    url = "https://www.instagram.com/%s/" % user
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        page = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")
    except Exception as e:
        return {"input": link, "profile": url, "error": "Fetch failed: %s" % e}
    desc = meta(page, "og:description")
    fm = re.match(r"([\d.,]+[KMB]?)\s+Followers", desc)
    if not fm:
        return {"input": link, "profile": url, "error": "Private, missing or blocked"}
    return {
        "input": link,
        "profile": url,
        "username": user,
        "name": user,
        "followers": to_number(fm.group(1)),
    }


PAGE = """<!doctype html><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Instagram Page Lookup</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#141414;color:#fff;font:15px Helvetica,Arial,sans-serif}
header{padding:18px 4%;background:linear-gradient(#000,#141414)}
header b{color:#e50914;font-size:26px;letter-spacing:2px;text-transform:uppercase}
main{max-width:960px;margin:0 auto;padding:30px 16px 80px}
h2{font-size:30px;margin:10px 0 6px}p{color:#b3b3b3;margin:0 0 14px}
textarea{width:100%;height:130px;background:#333;color:#fff;border:0;border-radius:4px;font:14px monospace;padding:12px}
textarea:focus{outline:2px solid #fff}
button{padding:11px 22px;font-size:15px;font-weight:700;margin:12px 10px 8px 0;cursor:pointer;border:0;border-radius:4px;background:#e50914;color:#fff}
button:hover{background:#f6121d}button+button{background:#6d6d6eb3}button+button:hover{background:#6d6d6e66}
#st{color:#b3b3b3}
table{border-collapse:collapse;width:100%;margin-top:18px}
td,th{padding:12px 14px;text-align:left;border-bottom:1px solid #2b2b2b}
th{color:#e50914;text-transform:uppercase;font-size:12px;letter-spacing:1px}
tbody tr{background:#1f1f1f}tbody tr:hover{background:#2b2b2b}
a{color:#fff}.err{color:#ff6b6b}
footer{position:fixed;bottom:0;left:0;right:0;text-align:center;padding:12px;background:#000;color:#8c8c8c;font-size:13px}
footer b{color:#e50914}
</style>
<header><b>Page Lookup</b></header>
<main>
<h2>Instagram Page Lookup</h2>
<p>Paste one or more Instagram profile links (one per line).</p>
<textarea id=in placeholder="https://www.instagram.com/username/"></textarea><br>
<button onclick=go()>Get details</button><button onclick=copyT()>Copy table</button>
<span id=st></span>
<table id=t hidden><thead><tr><th>Sr. No</th><th>Page Name</th><th>Profile Link</th><th>Followers</th></tr></thead><tbody></tbody></table>
</main>
<footer>Made by <b>Nikhilesh Bhatia</b></footer>
<script>
let rows=[];
async function go(){
 const links=document.getElementById('in').value.split(/\\n/).map(s=>s.trim()).filter(Boolean);
 const st=document.getElementById('st'),tb=document.querySelector('#t tbody');
 tb.innerHTML='';rows=[];document.getElementById('t').hidden=false;
 for(let i=0;i<links.length;i++){
  st.textContent='Fetching '+(i+1)+'/'+links.length+'...';
  const r=await (await fetch('/api?link='+encodeURIComponent(links[i]))).json();
  const tr=document.createElement('tr');
  if(r.error){tr.innerHTML='<td>'+(i+1)+'</td><td class=err colspan=3></td>';tr.lastChild.textContent=links[i]+' - '+r.error;rows.push([i+1,'',links[i],r.error].join('\\t'));}
  else{tr.innerHTML='<td>'+(i+1)+'</td><td></td><td><a target=_blank></a></td><td></td>';
   tr.children[1].textContent=r.name;const a=tr.querySelector('a');a.href=r.profile;a.textContent=r.profile;tr.children[3].textContent=r.followers;
   rows.push([i+1,r.name,r.profile,r.followers].join('\\t'));}
  tb.appendChild(tr);
  await new Promise(s=>setTimeout(s,800));
 }
 st.textContent='Done';
}
function copyT(){navigator.clipboard.writeText(rows.join('\\n'));document.getElementById('st').textContent='Copied - paste into Sheets/Excel';}
</script>"""


class H(BaseHTTPRequestHandler):
    def _send(self, body, ctype):
        b = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/api"):
            from urllib.parse import urlparse, parse_qs
            link = parse_qs(urlparse(self.path).query).get("link", [""])[0]
            self._send(json.dumps(lookup(link)), "application/json")
        else:
            self._send(PAGE, "text/html; charset=utf-8")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print("Running on http://localhost:%d" % port)
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
