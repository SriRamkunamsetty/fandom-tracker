"""Read-only dashboard server (stdlib only): JSON API + single-page UI.
Security posture: binds 127.0.0.1 by default, no auth (put it behind your own auth proxy before exposing it),
CSP + nosniff headers, request bodies capped, all user-derived text inserted with textContent (no innerHTML)."""
import json
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from .fandom import conversation_share, fandom_report

MAX_BODY = 20_000
HEADERS = {"X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store",
           "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:"}


def _json(obj, status=200):
    return status, "application/json", json.dumps(obj, default=str).encode()

class App:
    def __init__(self, conn):
        self.conn, self.lock = conn, threading.Lock()

    def _ids(self):
        return [r["id"] for r in self.conn.execute("SELECT id FROM titles ORDER BY id")]

    def meta(self):
        return {"sample_rows": int(self.conn.execute("SELECT COUNT(*) c FROM comments WHERE is_sample=1").fetchone()["c"])}

    def titles(self):
        share = conversation_share(self.conn, self._ids())
        return [{"id": r["id"], "name": r["name"], "genre": r["genre"], "comments": share[r["id"]]["comments"], "net_sentiment": share[r["id"]]["net_sentiment"]}
                for r in self.conn.execute("SELECT id, name, genre FROM titles ORDER BY id")]

    def route(self, method, raw_path, body):
        if method != "GET":
            return _json({"error": "method not allowed"}, 405)
        p = urlsplit(raw_path).path
        with self.lock:
            if p == "/":
                return 200, "text/html; charset=utf-8", PAGE.encode()
            if p == "/healthz":
                return _json({"ok": True})
            if p == "/api/meta":
                return _json(self.meta())
            if p == "/api/titles":
                return _json(self.titles())
            m = re.fullmatch(r"/api/fandom/(\d+)", p)
            if m:
                tid = int(m[1])
                if tid not in self._ids():
                    return _json({"error": "not found"}, 404)
                return _json(fandom_report(self.conn, tid, [i for i in self._ids() if i != tid]))
        return _json({"error": "not found"}, 404)


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def _run(self, method):
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if n > MAX_BODY:
                    status, ctype, body = _json({"error": "payload too large"}, 413)
                else:
                    status, ctype, body = app.route(method, self.path, self.rfile.read(n) if n else b"")
            except Exception as exc:  # never leak a stack trace to the client
                print(f"error on {self.path}: {exc!r}", file=sys.stderr)
                status, ctype, body = _json({"error": "internal error"}, 500)
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in HEADERS.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self._run("GET")

        def do_POST(self):
            self._run("POST")

        def log_message(self, fmt_, *args):
            pass
    return Handler


def serve(conn, host="127.0.0.1", port=8000):
    srv = ThreadingHTTPServer((host, port), make_handler(App(conn)))
    print(f"dashboard on http://{host}:{port}  (read-only, no auth)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.server_close()


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FandomWatch</title><style>
:root{--paper:#f2ead8;--panel:#ebe2cb;--ink:#1c1a16;--muted:#6b6455;--rule:#cfc4a8;--accent:#c2410c;--cool:#1f4e5f;--good:#2f6b3a;--bad:#a4261b;
--serif:"Iowan Old Style","Palatino Linotype","Book Antiqua",Georgia,serif;--mono:ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,monospace}
@media (prefers-color-scheme:dark){:root{--paper:#15130f;--panel:#1d1a14;--ink:#ece3cc;--muted:#a39a84;--rule:#3a3528;--accent:#f08a4b;--cool:#7fc0d4;--good:#7fc98a;--bad:#f08478}}
*{box-sizing:border-box}html,body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 var(--serif)}
.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
.banner{background:var(--accent);color:var(--paper);font:600 12px var(--mono);letter-spacing:.08em;text-transform:uppercase;padding:6px 16px;text-align:center}
.wrap{display:grid;grid-template-columns:270px 1fr;min-height:100vh}
aside{border-right:1px solid var(--rule);padding:22px 0}
aside h2{font:600 11px var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin:0 20px 10px}
.slate button{all:unset;display:flex;justify-content:space-between;gap:8px;width:100%;box-sizing:border-box;padding:9px 20px;cursor:pointer;border-left:3px solid transparent;border-bottom:1px solid var(--rule)}
.slate button:hover{background:var(--panel)}.slate button[aria-current=true]{border-left-color:var(--accent);background:var(--panel)}
.slate small{display:block;color:var(--muted);font:11px var(--mono);text-transform:uppercase;letter-spacing:.08em}
main{padding:26px 34px 60px;min-width:0}
.kicker{font:600 11px var(--mono);letter-spacing:.16em;text-transform:uppercase;color:var(--accent)}
h1{font:700 clamp(30px,4.4vw,52px)/1.02 var(--serif);letter-spacing:-.02em;margin:6px 0 18px}
.figs{display:grid;grid-template-columns:repeat(4,1fr);border-top:2px solid var(--ink);border-bottom:1px solid var(--rule);margin-bottom:22px}
.fig{padding:12px 16px;border-right:1px solid var(--rule)}.fig:last-child{border-right:0}
.fig b{display:block;font:600 clamp(20px,2.6vw,32px) var(--mono)}.fig span{font:11px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
nav.tabs{display:flex;gap:22px;border-bottom:1px solid var(--rule);margin-bottom:22px}
nav.tabs button{all:unset;cursor:pointer;padding:8px 0;font:600 12px var(--mono);letter-spacing:.12em;text-transform:uppercase;color:var(--muted);border-bottom:2px solid transparent}
nav.tabs button[aria-selected=true]{color:var(--ink);border-bottom-color:var(--accent)}
.read{font-size:19px;max-width:64ch;margin:0 0 10px}
.badge{display:inline-block;font:600 11px var(--mono);letter-spacing:.06em;padding:3px 8px;border:1px solid currentColor;margin-bottom:18px}.ok{color:var(--good)}.fail{color:var(--bad)}
h3{font:600 11px var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin:26px 0 8px;border-bottom:1px solid var(--rule);padding-bottom:6px}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:7px 10px 7px 0;border-bottom:1px solid var(--rule);vertical-align:top}
th{font:600 11px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}td.n,th.n{text-align:right;font-family:var(--mono);font-variant-numeric:tabular-nums;padding-left:18px}
.dim{color:var(--muted)}.chip{font:600 11px var(--mono);padding:2px 6px;border:1px solid currentColor;text-transform:uppercase}
.bar{display:inline-block;height:8px;background:var(--cool);vertical-align:middle}.bar.neg{background:var(--accent)}
.call{border-left:3px solid var(--accent);background:var(--panel);padding:10px 14px;margin:8px 0}
svg text{font:11px var(--mono);fill:var(--muted)}.scroll{overflow-x:auto}
@media (max-width:820px){.wrap{grid-template-columns:1fr}aside{border-right:0;border-bottom:1px solid var(--rule);padding:12px 0 0}.slate{display:flex;overflow-x:auto}.slate button{flex:0 0 auto;width:auto;border-left:0;border-bottom:3px solid transparent}.slate button[aria-current=true]{border-bottom-color:var(--accent)}.figs{grid-template-columns:1fr 1fr}main{padding:20px 16px}}

.field{display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin:0 0 18px}
select,textarea,button.act{font:14px var(--serif);color:var(--ink);background:var(--panel);border:1px solid var(--rule);padding:6px 10px}
textarea{width:100%;min-height:110px;resize:vertical;line-height:1.5}
button.act{cursor:pointer;font:600 12px var(--mono);letter-spacing:.08em;text-transform:uppercase;background:var(--ink);color:var(--paper);border-color:var(--ink)}
label.f{font:600 11px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--muted);display:flex;flex-direction:column;gap:4px}
mark{background:none;color:inherit;padding:0 3px;border-bottom:2px solid}
mark.ok{border-color:var(--good)}mark.unsupported{border-color:var(--bad);background:color-mix(in srgb,var(--bad) 14%,transparent)}
mark.misattributed{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 16%,transparent)}mark.style{border-color:var(--muted);border-bottom-style:dashed}
.legend{display:flex;gap:16px;flex-wrap:wrap;font:11px var(--mono);color:var(--muted);margin:8px 0 0}
.two{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(0,1fr);gap:28px}@media (max-width:980px){.two{grid-template-columns:1fr}}
.pill{font:600 10px var(--mono);letter-spacing:.08em;text-transform:uppercase;padding:2px 6px;border:1px solid currentColor;margin-left:6px}
tr.sel td{background:var(--panel)}tr.click{cursor:pointer}tr.click:hover td{background:var(--panel)}
.wrap.single{grid-template-columns:1fr}
@media (max-width:820px){.wrap,.wrap.single{grid-template-columns:minmax(0,1fr)}aside,main{min-width:0}.slate{max-width:100vw}.figs{grid-template-columns:1fr 1fr}.fig{border-right:0;border-bottom:1px solid var(--rule)}}main{min-width:0}svg{max-width:100%;height:auto}@media (max-width:820px){th,td{padding:6px 6px 6px 0;font-size:13px}td.n,th.n{padding-left:6px}.bar2{max-width:44px}.chip{font-size:10px}}button.act.off{background:var(--panel);color:var(--ink);border-color:var(--rule)}.bar2{display:inline-block;height:10px;background:var(--cool);vertical-align:middle}.bar2.warn{background:var(--accent)}</style></head><body><div id="banner" class="banner" hidden>Synthetic demo data. Not real platform data.</div><div class="wrap"><aside><h2>The slate</h2><div id="slate" class="slate"></div></aside><main><div class="kicker">Fandom watch</div><h1 id="title">Loading</h1><div id="figs" class="figs"></div><section id="panel"></section></main></div><script>
"use strict";
const $=s=>document.querySelector(s);
function h(tag,attrs,...kids){const e=document.createElement(tag);for(const[k,v]of Object.entries(attrs||{})){if(k==="class")e.className=v;else if(k.startsWith("on"))e.addEventListener(k.slice(2),v);else e.setAttribute(k,v)}
 for(const c of kids.flat(Infinity)){if(c==null||c===false)continue;e.append(c.nodeType?c:document.createTextNode(String(c)))}return e}
function sv(tag,attrs,...kids){const e=document.createElementNS("http://www.w3.org/2000/svg",tag);for(const[k,v]of Object.entries(attrs||{}))e.setAttribute(k,v);for(const c of kids.flat(Infinity))if(c!=null)e.append(typeof c==="string"?document.createTextNode(c):c);return e}
const api=async p=>{const r=await fetch(p);if(!r.ok)throw new Error(p+" "+r.status);return r.json()};
const pct=(x,d=0)=>x==null?"n/a":(x*100).toFixed(d)+"%";const big=v=>v>=1e6?(v/1e6).toFixed(2)+"M":v>=1e3?(v/1e3).toFixed(0)+"K":Math.round(v)+"";


const state={titles:[],cur:null};
const sign=x=>(x>0?"+":"")+(x*100).toFixed(0);
function timeline(r){const d=r.daily;if(d.length<2)return h("p",{class:"dim"},"Not enough days to chart yet.");
 const W=760,H=240,L=44,B=26,T=12,R=12,n=d.length,cw=(W-L-R)/n,X=i=>L+(i+.5)*cw;
 const ymax=Math.max(.2,Math.ceil(Math.max(...d.map(x=>x.neg_share))*10)/10),Y=v=>H-B-(v/ymax)*(H-B-T),maxN=Math.max(...d.map(x=>x.n));
 const g=sv("svg",{viewBox:`0 0 ${W} ${H}`,width:"100%",role:"img","aria-label":"Daily negative share of comments with backlash episodes shaded"});
 r.backlash.forEach(b=>{const i0=d.findIndex(x=>x.date===b.start),i1=d.findIndex(x=>x.date===b.end);if(i0>=0&&i1>=0)g.append(sv("rect",{x:L+i0*cw,y:T,width:(i1-i0+1)*cw,height:H-B-T,fill:"var(--accent)",opacity:".16"}),sv("text",{x:L+i0*cw+4,y:T+11,style:"fill:var(--accent)"},"backlash "+b.severity))});
 [0,ymax/2,ymax].forEach(v=>g.append(sv("line",{x1:L,x2:W-R,y1:Y(v),y2:Y(v),stroke:"var(--rule)"}),sv("text",{x:L-6,y:Y(v)+4,"text-anchor":"end"},(v*100).toFixed(0)+"%")));
 d.forEach((x,i)=>{const bh=x.n/maxN*.28*(H-B-T);g.append(sv("rect",{x:X(i)-cw*.32,y:H-B-bh,width:cw*.64,height:bh,fill:"var(--rule)"}));if(i%Math.max(1,Math.round(n/7))===0)g.append(sv("text",{x:X(i),y:H-8,"text-anchor":"middle"},x.date.slice(5)))});
 g.append(sv("polyline",{fill:"none",stroke:"var(--ink)","stroke-width":2,points:d.map((x,i)=>X(i)+","+Y(x.neg_share)).join(" ")}));
 d.forEach((x,i)=>g.append(sv("circle",{cx:X(i),cy:Y(x.neg_share),r:2.5,fill:"var(--ink)"})));
 return h("div",{class:"scroll"},g)}
function view(r){if(!r.n)return h("p",{class:"dim"},r.note||"No comments ingested for this title.");const s=r.sentiment;
 return h("div",{},
 h("p",{class:"read"},`${r.n} comments. Net sentiment ${sign(r.net_sentiment)} points; negative share ${pct(s.neg,1)} (95% interval ${pct(r.neg_share_ci95[0],1)} to ${pct(r.neg_share_ci95[1],1)}). This title holds ${pct(r.conversation_share,1)} of all tracked comments.`),
 h("div",{style:"display:flex;max-width:520px"},[["pos","var(--cool)"],["neu","var(--rule)"],["neg","var(--accent)"]].map(([k,c])=>h("span",{style:`display:inline-block;height:14px;width:${s[k]*100}%;background:${c}`}))),
 h("p",{class:"dim mono",style:"font-size:12px"},"positive / neutral / negative · classifier: "+r.classifier),
 h("h3",{},"Negative share by day (bars: comment volume)"),timeline(r),
 r.backlash.length?[h("h3",{},"Backlash watch"),r.backlash.map(b=>h("div",{class:"call"},h("span",{class:"chip"},b.severity)," ",`${b.start} to ${b.end}: ${pct(b.peak_neg_share)} negative at peak, ${b.neg_comments} negative comments. Aspects: ${b.top_aspects.join(", ")||"n/a"}.`,b.themes.length?h("div",{class:"dim"},"Recurring terms: "+b.themes.map(t=>t.join(" / ")).join("; ")):null))]:h("p",{class:"dim"},"No backlash episode detected."),
 h("h3",{},"Aspects (sentence-level)"),h("table",{},h("thead",{},h("tr",{},h("th",{},"Aspect"),h("th",{class:"n"},"Mentions"),h("th",{},"Net sentiment"))),
 h("tbody",{},r.aspects.map(a=>h("tr",{},h("td",{},a.aspect),h("td",{class:"n"},a.n),h("td",{},h("span",{class:"bar"+(a.net<0?" neg":""),style:`width:${Math.abs(a.net)*90+2}px`})," ",h("span",{class:"mono dim"},a.net.toFixed(2))))))),
 h("h3",{},"Recurring narratives"),r.narratives.map(n=>h("div",{class:"call"},h("b",{},n.terms.join(" / "))," ",h("span",{class:"dim mono"},`${pct(n.share,1)} of comments`),h("div",{class:"dim"},"“"+n.example+"”"))))}
async function pick(t){state.cur=t;$("#title").textContent=t.name;document.querySelectorAll("#slate button").forEach(b=>b.setAttribute("aria-current",b.dataset.id==t.id));
 const p=$("#panel");p.replaceChildren(h("p",{class:"dim"},"Loading"));
 try{const r=await api("/api/fandom/"+t.id);
 $("#figs").replaceChildren(...(r.n?[["Comments",String(r.n)],["Net sentiment",sign(r.net_sentiment)],["Negative share",pct(r.sentiment.neg,1)],["Conversation share",pct(r.conversation_share,1)]]:[["Comments","0"]]).map(([l,v])=>h("div",{class:"fig"},h("b",{},v),h("span",{},l))));
 p.replaceChildren(view(r))}catch(e){p.replaceChildren(h("div",{class:"call fail"},"Could not load: "+e.message))}}
(async()=>{const m=await api("/api/meta");if(m.sample_rows)$("#banner").hidden=false;state.titles=await api("/api/titles");
 $("#slate").replaceChildren(...state.titles.map(t=>h("button",{"data-id":t.id,onclick:()=>pick(t)},h("span",{},t.name,h("small",{},t.genre||"")),h("span",{class:"mono dim"},t.net_sentiment==null?"":sign(t.net_sentiment)))));
 if(state.titles.length)pick(state.titles[0]);else{$("#title").textContent="No data yet";$("#panel").replaceChildren(h("p",{class:"dim"},"Run `fandomwatch import-comments` or `fandomwatch ingest-youtube`, or start with --demo."))}})();

</script></body></html>"""
