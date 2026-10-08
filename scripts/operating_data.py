#!/usr/bin/env python3
"""Draw the OPERATING DATA panels (flight log, composition, inspection, logbook)
in the same ASD-STE100 manual style as the cover. Writes SVGs to assets/live/.
Env: GH_TOKEN (token with repo + read:user for private data), GH_USER. MOCK=1 for fake data."""
import os, json, random, datetime as dt, urllib.request
from xml.sax.saxutils import escape

USER = os.environ.get("GH_USER", "Lohithnath2910")
OUT = os.environ.get("OUT_DIR", "assets/live")
INK, PAPER, ORANGE, BLUE, YEL, MUTE, GREEN = "#141414", "#efebe1", "#ff4d17", "#2d55e6", "#ffd23f", "#6b665c", "#2bb24c"
SANS = "'Helvetica Neue',Helvetica,Arial,sans-serif"
BLACK = "'Arial Black','Helvetica Neue',Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
STYLE = f"""<style>
.mono{{font-family:{MONO}}} .blk{{font-family:{BLACK};font-weight:900}}
.thin{{fill:none;stroke:{INK};stroke-width:1.2}}
.grow{{transform-box:fill-box;transform-origin:50% 100%;animation:grow .9s cubic-bezier(.6,0,.2,1) both}}
.wipe{{transform-box:fill-box;transform-origin:0 50%;animation:wipe 1s cubic-bezier(.6,0,.2,1) both}}
.f{{animation:fade .5s ease-out both}}
.stamp{{transform-box:fill-box;transform-origin:50% 50%;animation:stamp .35s cubic-bezier(.3,1.6,.5,1) 1.2s both}}
@keyframes grow{{from{{transform:scaleY(0)}}}} @keyframes wipe{{from{{transform:scaleX(0)}}}}
@keyframes fade{{from{{opacity:0}}}} @keyframes stamp{{from{{transform:scale(1.6) rotate(-8deg);opacity:0}}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
</style>"""

# ---------------------------------------------------------------- data
def gql(query, variables, token):
    req = urllib.request.Request("https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        out = json.load(r)
    if out.get("errors"):
        raise SystemExit(json.dumps(out["errors"], indent=1))
    return out["data"]

Q = """query($login:String!){ user(login:$login){
  contributionsCollection{ contributionCalendar{ totalContributions weeks{ contributionDays{ date contributionCount } } }
    totalCommitContributions totalPullRequestContributions totalIssueContributions totalPullRequestReviewContributions restrictedContributionsCount }
  pullRequests{ totalCount }
  repositories(first:100, ownerAffiliations:OWNER, isFork:false, orderBy:{field:PUSHED_AT,direction:DESC}){ totalCount
    nodes{ name isPrivate stargazerCount
      languages(first:12, orderBy:{field:SIZE,direction:DESC}){ edges{ size node{ name } } }
      defaultBranchRef{ target{ ... on Commit{ history(first:8){ nodes{ messageHeadline committedDate abbreviatedOid author{ user{ login } } } } } } } } } } }"""

def fetch():
    if os.environ.get("MOCK"):
        return mock()
    token = os.environ["GH_TOKEN"]
    u = gql(Q, {"login": USER}, token)["user"]
    cc = u["contributionsCollection"]
    days = [(d["date"], d["contributionCount"]) for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    langs, log = {}, []
    for r in u["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
        ref = r["defaultBranchRef"]
        if not ref or not ref["target"]:
            continue
        for c in ref["target"]["history"]["nodes"]:
            a = (c["author"] or {}).get("user") or {}
            if a.get("login", "").lower() != USER.lower() or r["name"] == USER:
                continue
            log.append({"date": c["committedDate"][:10], "repo": r["name"], "msg": c["messageHeadline"],
                        "sha": c["abbreviatedOid"], "private": r["isPrivate"]})
    log.sort(key=lambda x: x["date"], reverse=True)
    return {"days": days, "total": cc["contributionCalendar"]["totalContributions"],
            "commits": cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
            "prs": u["pullRequests"]["totalCount"], "repos": u["repositories"]["totalCount"],
            "stars": sum(r["stargazerCount"] for r in u["repositories"]["nodes"]),
            "langs": langs, "log": log[:5]}

def mock():
    random.seed(3)
    end = dt.date(2026, 10, 8); start = end - dt.timedelta(days=end.weekday() + 1 + 52 * 7)
    days = []
    for i in range((end - start).days + 1):
        d = start + dt.timedelta(days=i)
        busy = 0.15 + 0.6 * (i / 370) ** 2
        days.append((d.isoformat(), random.choice([0, 0, 1, 2, 3, 5, 8, 12]) if random.random() < busy else 0))
    return {"days": days, "total": sum(c for _, c in days), "commits": 3270, "prs": 3, "repos": 23, "stars": 0,
            "langs": {"C++": 1.9e6, "Python": 1.7e6, "TypeScript": 5.2e5, "Rust": 2.9e5, "Dart": 3.5e5,
                      "JavaScript": 3.0e5, "HTML": 3.9e5, "Jupyter Notebook": 2.8e5, "Go": 9e4, "CSS": 4e4},
            "log": [{"date": "2026-10-07", "repo": "Inferra", "msg": "feat: stream tokens over websocket to the chat panel", "sha": "a91c2e0", "private": False},
                    {"date": "2026-10-06", "repo": "secret-thing", "msg": "x", "sha": "77b01fd", "private": True},
                    {"date": "2026-10-05", "repo": "BackForge", "msg": "fix: retry failed jobs with backoff", "sha": "3e4d9a1", "private": False},
                    {"date": "2026-10-03", "repo": "canvas", "msg": "refactor renderer loop", "sha": "c0ffee1", "private": False},
                    {"date": "2026-10-01", "repo": "GraphAnchor", "msg": "add graph index persistence and tests for the anchor store", "sha": "9b2a7c3", "private": False}]}

# ---------------------------------------------------------------- helpers
def streaks(days):
    best = (0, -1, -1); run = 0; start = 0
    for i, (_, c) in enumerate(days):
        if c:
            if run == 0: start = i
            run += 1
            if run > best[0]: best = (run, start, i)
        else:
            run = 0
    cur = 0; i = len(days) - 1
    if days[i][1] == 0: i -= 1
    while i >= 0 and days[i][1]:
        cur += 1; i -= 1
    return best, cur

def frame(W, H, fig, title, right, body):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{escape(title)}">
{STYLE}
<rect x="6" y="6" width="{W-6}" height="{H-6}" fill="{INK}"/>
<rect x="0" y="0" width="{W-6}" height="{H-6}" fill="{PAPER}" stroke="{INK}" stroke-width="3"/>
<rect x="0" y="0" width="{W-6}" height="34" fill="{INK}"/>
<text x="18" y="22" class="mono" font-size="11.5" font-weight="700" fill="{YEL}" letter-spacing="1.2">{fig}</text>
<text x="{18 + len(fig) * 7.6 + 14}" y="22" class="mono" font-size="11.5" fill="{PAPER}" letter-spacing="1.2">{escape(title)}</text>
<text x="{W-24}" y="22" text-anchor="end" class="mono" font-size="11.5" fill="{PAPER}" letter-spacing="1.2">{escape(right)}</text>
{body}
</svg>'''

def fmtn(n):
    return f"{n:,}"

def mdate(s):
    d = dt.date.fromisoformat(s); return d.strftime("%d %b %Y").upper()

# ---------------------------------------------------------------- FIG 2 flight log
def flight_log(D):
    days = D["days"]
    first = dt.date.fromisoformat(days[0][0]); off = (first.weekday() + 1) % 7  # sunday = row 0
    W, H = 900, 372; x0, step, cell = 70, 14.6, 11
    nweeks = (len(days) + off + 6) // 7
    weeks = [0] * nweeks
    for i, (_, c) in enumerate(days): weeks[(i + off) // 7] += c
    wmax = max(weeks) or 1; dmax = max(c for _, c in days) or 1
    (lb, ls, le), cur = streaks(days)
    busiest = max(range(len(days)), key=lambda i: days[i][1])
    nz = sorted(c for _, c in days if c)
    q = [nz[int(len(nz) * f)] if nz else 1 for f in (.25, .5, .75)]
    def lvl(c): return 0 if c == 0 else 1 + sum(c > t for t in q)
    body = []
    by, bh = 64, 96
    body.append(f'<text x="{x0-12}" y="{by+8}" text-anchor="end" class="mono" font-size="9" fill="{MUTE}">{wmax}</text>')
    body.append(f'<line x1="{x0-6}" y1="{by}" x2="{x0+nweeks*step}" y2="{by}" stroke="{INK}" stroke-opacity=".15" stroke-dasharray="2 3"/>')
    body.append(f'<text x="{x0-12}" y="{by+bh}" text-anchor="end" class="mono" font-size="9" fill="{MUTE}">0</text>')
    body.append(f'<text x="{x0-12}" y="{by+bh/2+3}" text-anchor="end" class="mono" font-size="8" fill="{MUTE}">/WK</text>')
    for w, v in enumerate(weeks):
        h = bh * v / wmax
        if h <= 0: continue
        col = ORANGE if v == wmax else INK
        body.append(f'<rect x="{x0+w*step:.1f}" y="{by+bh-h:.1f}" width="{cell}" height="{h:.1f}" fill="{col}" class="grow" style="animation-delay:{w*.012:.3f}s"/>')
    body.append(f'<line x1="{x0-6}" y1="{by+bh+.5}" x2="{x0+nweeks*step}" y2="{by+bh+.5}" stroke="{INK}" stroke-width="2"/>')
    gy = by + bh + 16
    fills = [None, (BLUE, .22), (BLUE, .48), (BLUE, .75), (BLUE, 1)]
    for i, (ds, c) in enumerate(days):
        k = i + off; x = x0 + (k // 7) * step; y = gy + (k % 7) * step
        L = lvl(c)
        if L == 0:
            body.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" fill="none" stroke="{INK}" stroke-opacity=".14"/>')
        else:
            body.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" fill="{fills[L][0]}" fill-opacity="{fills[L][1]}"/>')
        if cur and i >= len(days) - cur - (1 if days[-1][1] == 0 else 0) and c:
            body.append(f'<rect x="{x-1.5:.1f}" y="{y-1.5:.1f}" width="{cell+3}" height="{cell+3}" fill="none" stroke="{INK}" stroke-width="1.6" class="f" style="animation-delay:1.4s"/>')
    for r, lab in ((1, "MON"), (3, "WED"), (5, "FRI")):
        body.append(f'<text x="{x0-10}" y="{gy+r*step+9}" text-anchor="end" class="mono" font-size="8.5" fill="{MUTE}">{lab}</text>')
    # months
    seen = set()
    for i, (ds, _) in enumerate(days):
        d = dt.date.fromisoformat(ds)
        if d.day <= 7 and (d.year, d.month) not in seen and (i + off) % 7 == 0:
            seen.add((d.year, d.month)); x = x0 + ((i + off) // 7) * step
            body.append(f'<text x="{x:.1f}" y="{gy+7*step+12}" class="mono" font-size="9" fill="{INK}">{d.strftime("%b").upper()}</text>')
    # busiest day ring + callout A
    k = busiest + off; bx = x0 + (k // 7) * step + cell / 2; byy = gy + (k % 7) * step + cell / 2
    body.append(f'<g class="f" style="animation-delay:1.1s"><circle cx="{bx:.1f}" cy="{byy:.1f}" r="9" fill="none" stroke="{ORANGE}" stroke-width="2.2"/>'
                f'<line x1="{bx:.1f}" y1="{byy-9:.1f}" x2="{bx:.1f}" y2="{by+bh+4}" stroke="{ORANGE}" stroke-width="1.2"/>'
                f'<rect x="{bx-7:.1f}" y="{by+bh+3}" width="14" height="13" fill="{ORANGE}"/><text x="{bx:.1f}" y="{by+bh+13}" text-anchor="middle" class="mono" font-size="9" font-weight="700" fill="{PAPER}">A</text></g>')
    # longest streak dimension line
    dy = gy + 7 * step + 30
    if lb > 1:
        xa = x0 + ((ls + off) // 7) * step; xb = x0 + ((le + off) // 7) * step + cell
        body.append(f'<g class="f" style="animation-delay:1.3s"><line x1="{xa:.1f}" y1="{dy-7}" x2="{xa:.1f}" y2="{dy+5}" class="thin"/><line x1="{xb:.1f}" y1="{dy-7}" x2="{xb:.1f}" y2="{dy+5}" class="thin"/>'
                    f'<line x1="{xa:.1f}" y1="{dy}" x2="{xb:.1f}" y2="{dy}" stroke="{INK}" stroke-width="1.2"/>'
                    f'<path d="M{xa:.1f} {dy} l6 -3 v6 Z M{xb:.1f} {dy} l-6 -3 v6 Z" fill="{INK}"/>'
                    f'<text x="{(xa+xb)/2:.1f}" y="{dy+16}" text-anchor="middle" class="mono" font-size="9.5" font-weight="700" fill="{INK}">B</text></g>')
    # legend
    ly = H - 30
    body.append(f'<line x1="18" y1="{ly-16}" x2="{W-24}" y2="{ly-16}" class="thin"/>')
    leg = [(ORANGE, "A", f"BUSIEST DAY: {days[busiest][1]} ON {mdate(days[busiest][0])}"),
           (INK, "B", f"LONGEST RUN: {lb} DAYS"),
           (None, "C", f"CURRENT RUN: {cur} DAYS")]
    x = 18
    for col, k2, t in leg:
        body.append(f'<rect x="{x}" y="{ly-9}" width="14" height="14" fill="{col or PAPER}" stroke="{INK}" stroke-width="1.6"/><text x="{x+7}" y="{ly+2}" text-anchor="middle" class="mono" font-size="9" font-weight="700" fill="{INK if col is None else PAPER}">{k2}</text>')
        body.append(f'<text x="{x+22}" y="{ly+2}" class="mono" font-size="10" fill="{INK}">{t}</text>')
        x += 32 + len(t) * 6.1 + 18
    lx = W - 24 - 5 * 15 - 40
    body.append(f'<text x="{lx}" y="{ly+2}" text-anchor="end" class="mono" font-size="9" fill="{MUTE}">LESS</text>')
    for j in range(5):
        if j == 0:
            body.append(f'<rect x="{lx+6+j*15}" y="{ly-8}" width="{cell}" height="{cell}" fill="none" stroke="{INK}" stroke-opacity=".25"/>')
        else:
            body.append(f'<rect x="{lx+6+j*15}" y="{ly-8}" width="{cell}" height="{cell}" fill="{BLUE}" fill-opacity="{fills[j][1]}"/>')
    body.append(f'<text x="{lx+6+5*15+2}" y="{ly+2}" class="mono" font-size="9" fill="{MUTE}">MORE</text>')
    return frame(W, H, "FIG. 2", "FLIGHT LOG, LAST 12 MONTHS", f"TOTAL {fmtn(D['total'])} CONTRIBUTIONS", "\n".join(body))

# ---------------------------------------------------------------- FIG 3 composition
def composition(D):
    items = sorted(D["langs"].items(), key=lambda kv: -kv[1])
    tot = sum(v for _, v in items) or 1
    top = [(k, v) for k, v in items if v / tot >= .02][:7]
    rest = tot - sum(v for _, v in top)
    if rest > 0: top.append(("OTHER", rest))
    W = 900; rows = (len(top) + 1) // 2; H = 150 + rows * 26
    pats = f'''<defs>
<pattern id="h1" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="{PAPER}"/><line x1="0" y1="0" x2="0" y2="6" stroke="{INK}" stroke-width="2.4"/></pattern>
<pattern id="h2" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)"><rect width="6" height="6" fill="{PAPER}"/><line x1="0" y1="0" x2="0" y2="6" stroke="{ORANGE}" stroke-width="2.4"/></pattern>
<pattern id="h3" width="6" height="6" patternUnits="userSpaceOnUse"><rect width="6" height="6" fill="{PAPER}"/><circle cx="3" cy="3" r="1.3" fill="{BLUE}"/></pattern>
<pattern id="h4" width="8" height="8" patternUnits="userSpaceOnUse"><rect width="8" height="8" fill="{PAPER}"/><path d="M0 4H8M4 0V8" stroke="{INK}" stroke-width="1"/></pattern>
</defs>'''
    fills = [INK, ORANGE, BLUE, YEL, "url(#h1)", "url(#h2)", "url(#h3)", "url(#h4)"]
    body = [pats]
    x0, x1, by, bh = 24, W - 30, 62, 40
    body.append(f'<text x="{x0}" y="{by-10}" class="mono" font-size="9.5" fill="{MUTE}" letter-spacing=".8">COMPOSITION BY MASS (BYTES OF SOURCE CODE, ALL OWNED REPOSITORIES)</text>')
    x = x0
    for i, (k, v) in enumerate(top):
        w = (x1 - x0) * v / tot
        body.append(f'<rect x="{x:.1f}" y="{by}" width="{w:.1f}" height="{bh}" fill="{fills[i]}" stroke="{INK}" stroke-width="1.5" class="wipe" style="animation-delay:{i*.12:.2f}s"/>')
        if w > 40:
            tc = PAPER if fills[i] in (INK, BLUE) else INK
            if fills[i].startswith("url"): tc = None
            if tc: body.append(f'<text x="{x+8:.1f}" y="{by+25}" class="mono f" font-size="11" font-weight="700" fill="{tc}" style="animation-delay:1s">{v/tot*100:.0f}%</text>')
        x += w
    body.append(f'<rect x="{x0}" y="{by}" width="{x1-x0}" height="{bh}" fill="none" stroke="{INK}" stroke-width="3"/>')
    # scale ticks
    for p in range(0, 101, 10):
        tx = x0 + (x1 - x0) * p / 100
        body.append(f'<line x1="{tx:.1f}" y1="{by+bh}" x2="{tx:.1f}" y2="{by+bh+(7 if p%50==0 else 4)}" stroke="{INK}"/>')
        if p % 50 == 0: body.append(f'<text x="{tx:.1f}" y="{by+bh+18}" text-anchor="middle" class="mono" font-size="8.5" fill="{MUTE}">{p}</text>')
    ty = by + bh + 40; colw = (x1 - x0) / 2
    for i, (k, v) in enumerate(top):
        cx = x0 + (i % 2) * (colw + 10); cy = ty + (i // 2) * 26
        body.append(f'<g class="f" style="animation-delay:{.8+i*.06:.2f}s"><rect x="{cx}" y="{cy-11}" width="14" height="14" fill="{fills[i]}" stroke="{INK}" stroke-width="1.5"/>')
        body.append(f'<text x="{cx+24}" y="{cy}" class="mono" font-size="11" fill="{MUTE}">L-{i+1:02d}</text>')
        body.append(f'<text x="{cx+64}" y="{cy}" class="mono" font-size="11.5" font-weight="700" fill="{INK}">{escape(k.upper())}</text>')
        lead_x = cx + 64 + len(k) * 7.1 + 8
        body.append(f'<line x1="{lead_x:.1f}" y1="{cy-3}" x2="{cx+colw-70:.1f}" y2="{cy-3}" stroke="{INK}" stroke-opacity=".35" stroke-dasharray="1 3"/>')
        body.append(f'<text x="{cx+colw-10:.1f}" y="{cy}" text-anchor="end" class="mono" font-size="11.5" fill="{INK}">{v/tot*100:5.1f} %</text></g>')
    return frame(W, H, "FIG. 3", "MATERIAL COMPOSITION", f"{len(items)} LANGUAGES", "\n".join(body))

# ---------------------------------------------------------------- TABLE 1 inspection
def inspection(D):
    (lb, _, _), cur = streaks(D["days"])
    active = sum(1 for _, c in D["days"] if c)
    busiest = max(c for _, c in D["days"])
    cells = [("CONTRIBUTIONS", fmtn(D["total"]), "LAST 12 MONTHS"), ("COMMITS", fmtn(D["commits"]), "LAST 12 MONTHS"),
             ("PULL REQUESTS", fmtn(D["prs"]), "ALL TIME"), ("REPOSITORIES", fmtn(D["repos"]), "OWNED"),
             ("ACTIVE DAYS", fmtn(active), f"OF {len(D['days'])}"), ("LONGEST RUN", f"{lb}", "DAYS"),
             ("CURRENT RUN", f"{cur}", "DAYS"), ("PEAK DAY", f"{busiest}", "CONTRIBUTIONS")]
    W, H = 900, 300; x0, y0, cw, ch = 24, 52, (900 - 54) / 4, 92
    body = []
    for i, (lab, val, sub) in enumerate(cells):
        x = x0 + (i % 4) * cw; y = y0 + (i // 4) * ch
        body.append(f'<rect x="{x:.1f}" y="{y}" width="{cw:.1f}" height="{ch}" fill="none" stroke="{INK}" stroke-width="1.5"/>')
        body.append(f'<text x="{x+12:.1f}" y="{y+20}" class="mono" font-size="9.5" fill="{MUTE}" letter-spacing=".8">{i+1:02d}  {lab}</text>')
        body.append(f'<text x="{x+12:.1f}" y="{y+62}" class="blk f" font-size="34" fill="{ORANGE if i==6 else INK}" letter-spacing="-1" style="animation-delay:{i*.08:.2f}s">{val}</text>')
        body.append(f'<text x="{x+12:.1f}" y="{y+80}" class="mono" font-size="9" fill="{MUTE}">{sub}</text>')
    today = dt.date.today().strftime("%d %b %Y").upper()
    sx, sy = W - 236, 226
    body.append(f'''<g class="stamp"><g transform="rotate(-8 {sx+95} {sy+30})">
<rect x="{sx}" y="{sy}" width="190" height="58" rx="6" fill="{PAPER}" fill-opacity=".85" stroke="{GREEN}" stroke-width="3"/>
<rect x="{sx+5}" y="{sy+5}" width="180" height="48" rx="4" fill="none" stroke="{GREEN}" stroke-width="1.2"/>
<text x="{sx+95}" y="{sy+29}" text-anchor="middle" class="blk" font-size="18" fill="{GREEN}" letter-spacing="2">INSPECTED</text>
<text x="{sx+95}" y="{sy+45}" text-anchor="middle" class="mono" font-size="10" font-weight="700" fill="{GREEN}">{today} · SERVICEABLE</text></g></g>''')
    return frame(W, H, "TABLE 1", "INSPECTION REPORT", "AUTO-GENERATED DAILY", "\n".join(body))

# ---------------------------------------------------------------- TABLE 2 logbook
def logbook(D):
    rows = D["log"] or [{"date": dt.date.today().isoformat(), "repo": "-", "msg": "NO ENTRIES", "sha": "-", "private": False}]
    W = 900; rh = 34; H = 96 + len(rows) * rh
    cols = [(24, "NO."), (74, "DATE"), (190, "UNIT"), (360, "ACTION"), (W - 110, "REF")]
    body = [f'<rect x="24" y="48" width="{W-54}" height="24" fill="{YEL}" stroke="{INK}" stroke-width="1.5"/>']
    for x, t in cols:
        body.append(f'<text x="{x+8}" y="64" class="mono" font-size="10" font-weight="700" fill="{INK}" letter-spacing=".8">{t}</text>')
    for i, r in enumerate(rows):
        y = 72 + i * rh
        g = [f'<g class="f" style="animation-delay:{.15+i*.15:.2f}s">',
             f'<line x1="24" y1="{y+rh}" x2="{W-30}" y2="{y+rh}" stroke="{INK}" stroke-opacity=".3"/>',
             f'<text x="32" y="{y+21}" class="mono" font-size="11" fill="{MUTE}">{i+1:03d}</text>',
             f'<text x="82" y="{y+21}" class="mono" font-size="11" fill="{INK}">{mdate(r["date"])}</text>']
        if r["private"]:
            g.append(f'<rect x="198" y="{y+10}" width="130" height="14" fill="{INK}"/>')
            g.append(f'<rect x="368" y="{y+10}" width="{180+(i*37)%120}" height="14" fill="{INK}"/>')
            g.append(f'<text x="{368+190+(i*37)%120}" y="{y+21}" class="mono" font-size="9" font-weight="700" fill="{ORANGE}">RESTRICTED</text>')
        else:
            repo = r["repo"] if len(r["repo"]) <= 20 else r["repo"][:19] + "…"
            msg = r["msg"] if len(r["msg"]) <= 54 else r["msg"][:53] + "…"
            g.append(f'<text x="198" y="{y+21}" class="mono" font-size="11" font-weight="700" fill="{BLUE}">{escape(repo.upper())}</text>')
            g.append(f'<text x="368" y="{y+21}" class="mono" font-size="11" fill="{INK}">{escape(msg)}</text>')
        g.append(f'<text x="{W-102}" y="{y+21}" class="mono" font-size="11" fill="{MUTE}">{"■■■■■■■" if r["private"] else escape(r["sha"])}</text></g>')
        body += g
    for x, _ in cols[1:]:
        body.append(f'<line x1="{x}" y1="48" x2="{x}" y2="{72+len(rows)*rh}" stroke="{INK}" stroke-opacity=".3"/>')
    body.append(f'<rect x="24" y="48" width="{W-54}" height="{24+len(rows)*rh}" fill="none" stroke="{INK}" stroke-width="2"/>')
    return frame(W, H, "TABLE 2", "LOGBOOK, LAST ENTRIES", "PRIVATE ENTRIES ARE REDACTED", "\n".join(body))


# ---------------------------------------------------------------- FIG 2A isometric
def isometric(D):
    import math
    days = D["days"]
    first = dt.date.fromisoformat(days[0][0]); off = (first.weekday() + 1) % 7
    dmax = max(c for _, c in days) or 1
    nz = sorted(c for _, c in days if c)
    q = [nz[int(len(nz) * f)] if nz else 1 for f in (.25, .5, .75)]
    def lvl(c): return 0 if c == 0 else 1 + sum(c > t for t in q)
    tops = [None, (BLUE, .25), (BLUE, .5), (BLUE, .78), (BLUE, 1)]
    S = 10.6; C = math.cos(math.radians(30)) * S; SN = .5 * S; HMAX = 96
    W, H = 900, 560; ox, oy = 190, 175
    def P(a, b, h=0): return (ox + (a - b) * C, oy + (a + b) * SN - h)
    def poly(pts): return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    cells = []
    for i, (ds, c) in enumerate(days):
        k = i + off; cells.append((k // 7, k % 7, c, i))
    cells.sort(key=lambda t: (t[0] + t[1], t[0]))
    busiest = len(days) - 1  # today
    tcount = days[-1][1]
    defs = f'''<defs><pattern id="iso-h" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(60)">
<rect width="4" height="4" fill="{PAPER}"/><line x1="0" y1="0" x2="0" y2="4" stroke="{INK}" stroke-width="1"/></pattern></defs>'''
    body = [defs]
    # floor plate
    nweeks = max(t[0] for t in cells) + 1
    fl = [P(-.4, -.4), P(nweeks + .4, -.4), P(nweeks + .4, 7.4), P(-.4, 7.4)]
    body.append(f'<polygon points="{poly(fl)}" fill="none" stroke="{INK}" stroke-width="1.6"/>')
    fl2 = [(x, y + 8) for x, y in fl]
    body.append(f'<path d="M{fl[3][0]:.1f},{fl[3][1]:.1f} L{fl2[3][0]:.1f},{fl2[3][1]:.1f} L{fl2[2][0]:.1f},{fl2[2][1]:.1f} L{fl2[1][0]:.1f},{fl2[1][1]:.1f} L{fl[1][0]:.1f},{fl[1][1]:.1f}" fill="none" stroke="{INK}" stroke-width="1.6"/>')
    body.append(f'<polygon points="{poly([fl[3], fl[2], fl2[2], fl2[3]])}" fill="url(#iso-h)" stroke="{INK}" stroke-width="1.2"/>')
    body.append(f'<polygon points="{poly([fl[2], fl[1], fl2[1], fl2[2]])}" fill="{INK}" stroke="{INK}" stroke-width="1.2"/>')
    g = .14
    for w, d, c, i in cells:
        a0, a1, b0, b1 = w + g, w + 1 - g, d + g, d + 1 - g
        L = lvl(c)
        if L == 0 and i == busiest:
            body.append(f'<polygon points="{poly([P(a0,b0),P(a1,b0),P(a1,b1),P(a0,b1)])}" fill="{ORANGE}" stroke="{INK}" stroke-width="1.2"/>')
            bw, bd, bh = w, d, 0
            continue
        if L == 0:
            body.append(f'<polygon points="{poly([P(a0,b0),P(a1,b0),P(a1,b1),P(a0,b1)])}" fill="none" stroke="{INK}" stroke-opacity=".22" stroke-width=".8"/>')
            continue
        h = 6 + (HMAX - 6) * c / dmax
        top = [P(a0, b0, h), P(a1, b0, h), P(a1, b1, h), P(a0, b1, h)]
        left = [P(a0, b1), P(a1, b1), P(a1, b1, h), P(a0, b1, h)]
        right = [P(a1, b0), P(a1, b1), P(a1, b1, h), P(a1, b0, h)]
        topc, topo = (ORANGE, 1) if i == busiest else tops[L]
        delay = (w * .018)
        body.append(f'<g class="grow" style="animation-delay:{delay:.2f}s">'
                    f'<polygon points="{poly(left)}" fill="url(#iso-h)" stroke="{INK}" stroke-width=".9" stroke-linejoin="round"/>'
                    f'<polygon points="{poly(right)}" fill="{INK}" stroke="{INK}" stroke-width=".9" stroke-linejoin="round"/>'
                    f'<polygon points="{poly(top)}" fill="{PAPER}" stroke="{INK}" stroke-width=".9" stroke-linejoin="round"/>'
                    f'<polygon points="{poly(top)}" fill="{topc}" fill-opacity="{topo}" stroke="{INK}" stroke-width=".9" stroke-linejoin="round"/></g>')
        if i == busiest:
            bw, bd, bh = w, d, h
    # TODAY callout: halo leader from the column top to a box in clear space
    sx, sy = P(bw + .5, bd + .5, bh)
    lx, ly = W - 175, 330
    ex = lx - 18
    path = f"M{sx:.1f},{sy:.1f} L{sx + (ly - sy) * -0.0 + 20:.1f},{ly:.1f} L{lx-12:.1f},{ly:.1f}" if sy > ly else f"M{sx:.1f},{sy:.1f} L{lx-12:.1f},{ly:.1f}"
    body.append(f'<g class="f" style="animation-delay:1.6s">'
                f'<path d="{path}" fill="none" stroke="{PAPER}" stroke-width="6" stroke-linejoin="round" stroke-linecap="round"/>'
                f'<path d="{path}" fill="none" stroke="{INK}" stroke-width="1.6" stroke-linejoin="round"/>'
                f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="4.5" fill="{ORANGE}" stroke="{INK}" stroke-width="1.6"/>'
                f'<rect x="{lx-12}" y="{ly-30}" width="150" height="62" fill="{INK}" transform="translate(4 4)"/>'
                f'<rect x="{lx-12}" y="{ly-30}" width="150" height="62" fill="{ORANGE}" stroke="{INK}" stroke-width="2"/>'
                f'<text x="{lx}" y="{ly-12}" class="mono" font-size="9.5" font-weight="700" fill="{INK}" letter-spacing="1">TODAY · {mdate(days[-1][0])}</text>'
                f'<text x="{lx}" y="{ly+22}" class="blk" font-size="28" fill="{INK}">{tcount}</text>'
                f'<text x="{lx + 8 + len(str(tcount)) * 19}" y="{ly+21}" class="mono" font-size="9.5" font-weight="700" fill="{INK}">CONTRIBUTIONS</text></g>')
    # month ticks along front edge (day 7 side)
    seen = set()
    for i, (ds, _) in enumerate(days):
        dd = dt.date.fromisoformat(ds)
        if dd.day <= 7 and (dd.year, dd.month) not in seen and (i + off) % 7 == 0:
            seen.add((dd.year, dd.month)); w = (i + off) // 7
            x, y = P(w + .5, 7.4); x2, y2 = P(w + .5, 8.6)
            body.append(f'<line x1="{x:.1f}" y1="{y+8:.1f}" x2="{x2:.1f}" y2="{y2+8:.1f}" class="thin"/>')
            body.append(f'<text x="{x2-4:.1f}" y="{y2+22:.1f}" text-anchor="end" class="mono" font-size="9" fill="{INK}">{dd.strftime("%b").upper()}</text>')
    # axis triad
    tx, ty = 95, 470
    def arrow(dx_, dy_, lab, anchor):
        return (f'<line x1="{tx}" y1="{ty}" x2="{tx+dx_:.1f}" y2="{ty+dy_:.1f}" stroke="{INK}" stroke-width="1.6"/>'
                f'<circle cx="{tx+dx_:.1f}" cy="{ty+dy_:.1f}" r="2.5" fill="{INK}"/>'
                f'<text x="{tx+dx_*1.25:.1f}" y="{ty+dy_*1.25+4:.1f}" text-anchor="{anchor}" class="mono" font-size="9" font-weight="700" fill="{INK}">{lab}</text>')
    body.append(arrow(40 * math.cos(math.radians(30)), 20, "X WEEK", "start"))
    body.append(arrow(-40 * math.cos(math.radians(30)), 20, "Y DAY", "end"))
    body.append(arrow(0, -40, "Z COUNT", "middle"))
    body.append(f'<text x="{tx}" y="{ty+52}" text-anchor="middle" class="mono" font-size="8.5" fill="{MUTE}">ISO 30°</text>')
    # notes block
    (lb, _, _), cur = streaks(days)
    nx, ny = W - 290, 70
    notes = [f"1. ONE COLUMN IS ONE DAY.", f"2. COLUMN HEIGHT IS THE COUNT.", f"3. ORANGE: TODAY, {mdate(days[-1][0])}.",
             f"4. TODAY: {tcount} CONTRIBUTIONS.", f"5. LONGEST RUN: {lb} DAYS.", f"6. CURRENT RUN: {cur} DAYS."]
    body.append(f'<text x="{nx}" y="{ny}" class="mono" font-size="10" font-weight="700" fill="{INK}" letter-spacing="1">NOTES</text>')
    body.append(f'<line x1="{nx}" y1="{ny+6}" x2="{W-30}" y2="{ny+6}" class="thin"/>')
    for j, t in enumerate(notes):
        body.append(f'<text x="{nx}" y="{ny+24+j*17}" class="mono" font-size="10" fill="{INK}">{t}</text>')
    return frame(W, H, "FIG. 2", "ISOMETRIC VIEW, LAST 12 MONTHS", f"TOTAL {fmtn(D['total'])} CONTRIBUTIONS", "\n".join(body))

def main():
    D = fetch()
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("isometric", isometric), ("composition", composition), ("inspection", inspection), ("logbook", logbook)):
        with open(os.path.join(OUT, f"{name}.svg"), "w") as f:
            f.write(fn(D))
    print("wrote", OUT)

if __name__ == "__main__":
    main()
