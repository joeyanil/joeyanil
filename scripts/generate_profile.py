#!/usr/bin/env python3
"""Builds art/stats-*.svg and art/pacman-*.svg from your real GitHub data.
Run locally:  GH_TOKEN=xxxx python scripts/generate_profile.py
The GitHub Action in .github/workflows/update-profile.yml runs it every day.
Uses only the Python standard library."""
import json, os, sys, math, urllib.request
from datetime import date, datetime, timedelta, timezone

USER = os.environ.get("GH_USER", "joeyanil")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "art")
FS = "'Segoe UI','Helvetica Neue',Arial,sans-serif"
FM = "'Fira Code','SFMono-Regular',Consolas,'Liberation Mono',monospace"

THEMES = {
 "dark": dict(bg1="#070B18", bg2="#101736", a1="#38BDF8", a2="#8B5CF6", text="#E2E8F0", muted="#94A3B8",
              gfill="#FFFFFF", gop=".05", s1="#FFFFFF", s1o=".40", s2="#8B5CF6", s2o=".55", tile=".06",
              lv=["#171E36", "#164E63", "#0E7490", "#38BDF8", "#A78BFA"]),
 "light": dict(bg1="#EEF2FF", bg2="#F8FAFF", a1="#0284C7", a2="#7C3AED", text="#0F172A", muted="#475569",
               gfill="#FFFFFF", gop=".55", s1="#FFFFFF", s1o=".95", s2="#7C3AED", s2o=".30", tile=".7",
               lv=["#E3E8F5", "#BAE6FD", "#7DD3FC", "#38BDF8", "#7C3AED"]),
}

def esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
def num(v): return f"{v:.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)

def kf(pairs, D, init=None):
    init = pairs[0][1] if init is None else init
    pts = [(0.0, init)] + list(pairs) + [(D - 0.03, pairs[-1][1]), (D, init)]
    ts, vs, last = [], [], -1.0
    for i, (t, v) in enumerate(pts):
        if i == 0: t = 0.0
        elif i == len(pts) - 1: t = D
        else: t = min(max(t, last + 0.0005), D - 0.0006)
        ts.append(t); vs.append(v); last = t
    return ";".join(f"{t/D:.5f}" for t in ts), ";".join(num(v) for v in vs)

def anim(attr, pairs, D, init=None):
    kt, vs = kf(pairs, D, init)
    return f'<animate attributeName="{attr}" dur="{D}s" repeatCount="indefinite" keyTimes="{kt}" values="{vs}"/>'

def defs(c):
    return f'''<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c['bg1']}"/><stop offset="1" stop-color="{c['bg2']}"/></linearGradient>
<linearGradient id="acc" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{c['a1']}"/><stop offset="1" stop-color="{c['a2']}"/></linearGradient>
<linearGradient id="gs" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c['s1']}" stop-opacity="{c['s1o']}"/><stop offset=".55" stop-color="{c['s1']}" stop-opacity=".05"/><stop offset="1" stop-color="{c['s2']}" stop-opacity="{c['s2o']}"/></linearGradient>
<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'''

# ------------------------------------------------------------------ data
def gql(query):
    req = urllib.request.Request("https://api.github.com/graphql", data=json.dumps({"query": query}).encode(),
                                 headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json", "User-Agent": "profile-art"})
    with urllib.request.urlopen(req, timeout=40) as r: d = json.load(r)
    if d.get("errors"): raise SystemExit(f"GraphQL error: {d['errors']}")
    return d["data"]

CAL = "contributionCalendar{totalContributions weeks{firstDay contributionDays{date contributionCount weekday}}}"

def fetch():
    now = datetime.now(timezone.utc)
    meta = gql('{user(login:"%s"){createdAt followers{totalCount} repositories(ownerAffiliations:OWNER,privacy:PUBLIC){totalCount}}}' % USER)["user"]
    first = int(meta["createdAt"][:4])
    parts = []
    for y in range(first, now.year + 1):
        to = f"{y}-12-31T23:59:59Z" if y < now.year else now.strftime("%Y-%m-%dT%H:%M:%SZ")
        parts.append(f'y{y}:contributionsCollection(from:"{y}-01-01T00:00:00Z",to:"{to}"){{{CAL}}}')
    q = '{user(login:"%s"){%s last:contributionsCollection{%s}}}' % (USER, " ".join(parts), CAL)
    u = gql(q)["user"]
    days = {}
    for k, v in u.items():
        if k.startswith("y"):
            for w in v["contributionCalendar"]["weeks"]:
                for d in w["contributionDays"]: days[d["date"]] = d["contributionCount"]
    weeks = u["last"]["contributionCalendar"]["weeks"]
    langs = {}
    lq = '{user(login:"%s"){repositories(first:100,ownerAffiliations:OWNER,privacy:PUBLIC,isFork:false){nodes{languages(first:6,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}}}}}' % USER
    for repo in gql(lq)["user"]["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            n = e["node"]; langs.setdefault(n["name"], [0, n["color"] or "#8B949E"]); langs[n["name"]][0] += e["size"]
    return dict(meta=meta, days=days, weeks=weeks, langs=langs)

def streaks(days):
    ds = sorted(days); cur = longest = run = 0; prev = None
    for d in ds:
        dt = date.fromisoformat(d)
        run = run + 1 if (days[d] > 0 and prev is not None and (dt - prev).days == 1 and days[prev.isoformat()] > 0) else (1 if days[d] > 0 else 0)
        longest = max(longest, run); prev = dt
    today = date.today(); d = today if days.get(today.isoformat(), 0) > 0 else today - timedelta(days=1)
    while days.get(d.isoformat(), 0) > 0: cur += 1; d -= timedelta(days=1)
    return cur, longest

# ------------------------------------------------------------------ stats dashboard
def stats_svg(name, data):
    c = THEMES[name]; days = data["days"]; total = sum(days.values()); cur, longest = streaks(days)
    tiles = [(f"{total:,}", "Contributions · all time"), (str(cur), "Current streak · days"), (str(longest), "Longest streak · days"),
             (str(data["meta"]["repositories"]["totalCount"]), "Public repositories")]
    tl = ""
    for i, (n, lab) in enumerate(tiles):
        x = 26 + i * 242
        tl += (f'<g><rect x="{x}" y="26" width="222" height="148" rx="18" fill="{c["gfill"]}" fill-opacity="{c["tile"]}" stroke="url(#gs)" stroke-width="1.2"/>'
               f'<text x="{x+111}" y="100" text-anchor="middle" font-family="{FS}" font-size="62" font-weight="800" fill="url(#acc)">{n}</text>'
               f'<text x="{x+111}" y="142" text-anchor="middle" font-family="{FS}" font-size="19" fill="{c["muted"]}">{lab}</text>'
               f'<animate attributeName="opacity" values="0;1" dur=".8s" begin="{i*.12:.2f}s" fill="freeze"/></g>')
    wk = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in data["weeks"]]
    mx = max(max(wk), 1); X0, X1, Y0, Y1 = 36, 964, 246, 372
    pts = [(X0 + (X1 - X0) * i / max(len(wk) - 1, 1), Y1 - (Y1 - Y0) * v / mx) for i, v in enumerate(wk)]
    line = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = line + f" L{X1},{Y1} L{X0},{Y1} Z"
    months = ""; seen = None
    for i, w in enumerate(data["weeks"]):
        m = date.fromisoformat(w["firstDay"]).strftime("%b")
        if m != seen and 3 <= i < len(wk) - 2:
            months += f'<text x="{pts[i][0]:.0f}" y="398" font-family="{FS}" font-size="16" fill="{c["muted"]}">{m}</text>'; seen = m
    D = 10
    draw = anim("stroke-dashoffset", [(0.2, 1), (2.6, 0), (9.0, 0), (9.6, 1)], D, init=1)
    areaop = anim("opacity", [(0.2, 0), (2.6, 1), (9.0, 1), (9.6, 0)], D, init=0)
    lx, ly = pts[-1]
    tot = sum(v[0] for v in data["langs"].values()) or 1
    ls = sorted(data["langs"].items(), key=lambda kv: -kv[1][0])[:5]; bar = ""; leg = ""; x = 26; bw = 948; lx_leg = 26
    for i, (n, (sz, col)) in enumerate(ls):
        w = max(bw * sz / tot, 4)
        bar += f'<rect x="{x:.1f}" y="446" width="{w:.1f}" height="14" fill="{col}"/>'; x += w
        lx2 = lx_leg; lx_leg += 22 + (len(n) + 7) * 10.4 + 34
        leg += f'<circle cx="{lx2+8}" cy="492" r="6" fill="{col}"/><text x="{lx2+22}" y="498" font-family="{FS}" font-size="19" fill="{c["text"]}">{esc(n)} <tspan fill="{c["muted"]}">{100*sz/tot:.1f}%</tspan></text>'
    upd = datetime.now(timezone.utc).strftime("%b %d, %Y")
    return f'''<svg width="1000" height="536" viewBox="0 0 1000 536" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="GitHub stats for {USER}">
<defs>{defs(c)}<linearGradient id="ar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c['a2']}" stop-opacity=".45"/><stop offset="1" stop-color="{c['a1']}" stop-opacity="0"/></linearGradient><clipPath id="r"><rect width="1000" height="536" rx="24"/></clipPath><clipPath id="lb"><rect x="26" y="446" width="948" height="14" rx="7"/></clipPath></defs>
<g clip-path="url(#r)"><rect width="1000" height="536" fill="url(#bg)"/><rect width="1000" height="536" fill="{c['gfill']}" fill-opacity="{c['gop']}"/></g>
<rect x=".75" y=".75" width="998.5" height="534.5" rx="24" fill="none" stroke="url(#gs)" stroke-width="1.5"/>
{tl}
<text x="36" y="226" font-family="{FS}" font-size="20" font-weight="600" fill="{c['text']}">Contribution activity <tspan fill="{c['muted']}" font-weight="400">· last 12 months</tspan></text>
<path d="{area}" fill="url(#ar)">{areaop}</path>
<path d="{line}" fill="none" stroke="url(#acc)" stroke-width="3.2" stroke-linejoin="round" stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="0" filter="url(#glow)">{draw}</path>
<circle cx="{lx:.1f}" cy="{ly:.1f}" r="5" fill="{c['a1']}" filter="url(#glow)"><animate attributeName="r" values="4;8;4" dur="2s" repeatCount="indefinite"/></circle>
{months}
<text x="36" y="432" font-family="{FS}" font-size="20" font-weight="600" fill="{c['text']}">Most used languages <tspan fill="{c['muted']}" font-weight="400">· public repositories</tspan></text>
<g clip-path="url(#lb)">{bar}</g>{leg}
<text x="974" y="524" text-anchor="end" font-family="{FM}" font-size="13" fill="{c['muted']}">updated {upd}</text>
</svg>'''

# ------------------------------------------------------------------ pac-man
def pacman_svg(name, data):
    c = THEMES[name]; weeks = data["weeks"]; P, S, X0, Y0, D, M = 17, 14, 41, 62, 32.0, 24.0
    ncol = len(weeks); counts = [d["contributionCount"] for w in weeks for d in w["contributionDays"] if d["contributionCount"] > 0]
    qs = sorted(counts); q = (lambda f: qs[min(int(len(qs) * f), len(qs) - 1)] if qs else 1)
    def level(n): return 0 if n == 0 else 1 if n <= q(.4) else 2 if n <= q(.7) else 3 if n <= q(.9) else 4
    L = (ncol - 1) * 119 + 102; cells = ""; eaten = 0; months = ""; seen = None
    for ci, w in enumerate(weeks):
        m = date.fromisoformat(w["firstDay"]).strftime("%b")
        if m != seen and 3 <= ci < ncol - 2: months += f'<text x="{X0+ci*P}" y="46" font-family="{FS}" font-size="14" fill="{c["muted"]}">{m}</text>'; seen = m
        for d in w["contributionDays"]:
            r = d["weekday"]; x, y = X0 + ci * P, Y0 + r * P; lv = level(d["contributionCount"])
            s = ci * 119 + (r * P if ci % 2 == 0 else (6 - r) * P); te = s / L * M
            a = ""
            if lv:
                eaten += 1
                a = anim("opacity", [(te - .02, 1), (te + .1, 0), (D - 1.0, 0), (D - .5, 1)], D, init=1)
            cells += f'<rect x="{x}" y="{y}" width="{S}" height="{S}" rx="3.5" fill="{c["lv"][lv]}">{a}</rect>'
    pts = []
    for ci in range(ncol):
        x = X0 + ci * P + S / 2; ya, yb = Y0 + S / 2, Y0 + 6 * P + S / 2
        pts += [(x, ya), (x, yb)] if ci % 2 == 0 else [(x, yb), (x, ya)]
    path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    gd = 1.6
    pk = f'calcMode="linear" keyPoints="0;1;1" keyTimes="0;{M/D:.4f};1"'
    gk = f'calcMode="linear" keyPoints="0;0;1;1" keyTimes="0;{gd/D:.4f};{(M+gd)/D:.4f};1"'
    o, cl = "M0,0 L7.4,-5.2 A9,9 0 1 0 7.4,5.2 Z", "M0,0 L9,-0.6 A9,9 0 1 0 9,0.6 Z"
    fade = lambda t: anim("opacity", [(t + .2, 1), (t + .7, 0), (D - .6, 0), (D - .2, 1)], D, init=1)
    return f'''<svg width="1000" height="228" viewBox="0 0 1000 228" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Pac-Man eating {USER}'s contribution graph">
<defs>{defs(c)}<clipPath id="r"><rect width="1000" height="228" rx="24"/></clipPath></defs>
<g clip-path="url(#r)"><rect width="1000" height="228" fill="url(#bg)"/><rect width="1000" height="228" fill="{c['gfill']}" fill-opacity="{c['gop']}"/></g>
<rect x=".75" y=".75" width="998.5" height="226.5" rx="24" fill="none" stroke="url(#gs)" stroke-width="1.5"/>
{months}{cells}
<g><path d="{o}" fill="#FACC15" filter="url(#glow)"><animate attributeName="d" values="{o};{cl};{o}" dur=".28s" repeatCount="indefinite"/></path><circle cx="1.5" cy="-4.6" r="1.4" fill="#0B1020"/>
<animateMotion dur="{D}s" repeatCount="indefinite" rotate="auto" {pk} path="{path}"/>{fade(M)}</g>
<g><path d="M-9,9 V-1 A9,9 0 0 1 9,-1 V9 L6,6 L3,9 L0,6 L-3,9 L-6,6 Z" fill="#F472B6" filter="url(#glow)"/><circle cx="-3.2" cy="-2" r="2.6" fill="#fff"/><circle cx="3.2" cy="-2" r="2.6" fill="#fff"/><circle cx="-2.4" cy="-2" r="1.2" fill="#0B1020"/><circle cx="4" cy="-2" r="1.2" fill="#0B1020"/>
<animateMotion dur="{D}s" repeatCount="indefinite" {gk} path="{path}"/>{fade(M + gd)}</g>
<text x="41" y="210" font-family="{FS}" font-size="16" fill="{c['muted']}">Pac-Man is eating {eaten} active days from the last 12 months · {sum(data['days'].values()):,} contributions all time</text>
</svg>'''

if __name__ == "__main__":
    if not TOKEN: sys.exit("Set GH_TOKEN (or GITHUB_TOKEN)")
    data = fetch(); os.makedirs(OUT, exist_ok=True)
    for n in THEMES:
        open(os.path.join(OUT, f"stats-{n}.svg"), "w").write(stats_svg(n, data))
        open(os.path.join(OUT, f"pacman-{n}.svg"), "w").write(pacman_svg(n, data))
    print("ok", {k: (v if k != "weeks" and k != "days" else len(v)) for k, v in data.items() if k != "langs"}, list(data["langs"])[:6])
